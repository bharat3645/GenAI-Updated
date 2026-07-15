"""
API Gateway — Central entry point for the GenAI Platform.

Responsibilities:
  - JWT authentication
  - Reverse proxy routing to downstream services
  - SSE streaming proxy
  - CORS middleware
  - Health check aggregation (pings all services)
  - Rate limiting (slowapi)
  - Structured request logging with correlation IDs
  - KG module proxy routes
"""

from __future__ import annotations

import logging
import time
import uuid as uuid_mod
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from typing import AsyncIterator

import httpx
import redis.asyncio as aioredis
from fastapi import FastAPI, HTTPException, Request, Depends, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from sse_starlette.sse import EventSourceResponse
from starlette.middleware.base import BaseHTTPMiddleware

import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from shared.config import get_settings
from prometheus_fastapi_instrumentator import Instrumentator

# ── Structured Logging ──────────────────────────────────
import json as json_mod

class JSONFormatter(logging.Formatter):
    """Structured JSON log formatter with correlation ID support."""
    def format(self, record):
        log_entry = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if hasattr(record, "correlation_id"):
            log_entry["correlation_id"] = record.correlation_id
        if hasattr(record, "method"):
            log_entry["method"] = record.method
        if hasattr(record, "path"):
            log_entry["path"] = record.path
        if hasattr(record, "status_code"):
            log_entry["status_code"] = record.status_code
        if hasattr(record, "duration_ms"):
            log_entry["duration_ms"] = record.duration_ms
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
        return json_mod.dumps(log_entry)


handler = logging.StreamHandler()
handler.setFormatter(JSONFormatter())
logging.basicConfig(level=logging.INFO, handlers=[handler])
logger = logging.getLogger("api-gateway")

settings = get_settings()

# ── Rate Limiter ──────────────────────────────────────
limiter = Limiter(key_func=get_remote_address, default_limits=["120/minute"])

# ── Service URLs ──────────────────────────────────────
SERVICE_MAP = {
    "rag": "http://pdf-rag-service:8001",
    "ats": "http://ats-agent-service:8002",
    "research": "http://research-service:8003",
    "sql": "http://sql-service:8004",
}

# ── Auth ─────────────────────────────────────────────────
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24 hours


class TokenData(BaseModel):
    user_id: str
    email: str


class LoginRequest(BaseModel):
    email: str
    password: str


class RegisterRequest(BaseModel):
    email: str
    password: str
    display_name: str = ""


def create_access_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.jwt_secret, algorithm=ALGORITHM)


async def get_current_user(request: Request) -> TokenData:
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing Bearer token")
    token = auth_header[7:]
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[ALGORITHM])
        return TokenData(user_id=payload["sub"], email=payload["email"])
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")


# ── Correlation ID Middleware ────────────────────────────

class CorrelationIDMiddleware(BaseHTTPMiddleware):
    """Attach a unique correlation ID to every request for tracing."""
    async def dispatch(self, request: Request, call_next):
        correlation_id = request.headers.get("X-Correlation-ID", str(uuid_mod.uuid4()))
        request.state.correlation_id = correlation_id
        start_time = time.perf_counter()

        response = await call_next(request)

        duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
        response.headers["X-Correlation-ID"] = correlation_id

        # Structured request log
        extra = {
            "correlation_id": correlation_id,
            "method": request.method,
            "path": request.url.path,
            "status_code": response.status_code,
            "duration_ms": duration_ms,
        }
        record = logging.LogRecord(
            name="api-gateway", level=logging.INFO, pathname="", lineno=0,
            msg=f"{request.method} {request.url.path} → {response.status_code} ({duration_ms}ms)",
            args=(), exc_info=None,
        )
        for k, v in extra.items():
            setattr(record, k, v)
        logger.handle(record)

        return response


# ── App Setup ────────────────────────────────────────
http_client: httpx.AsyncClient | None = None
redis_client: aioredis.Redis | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global http_client, redis_client
    http_client = httpx.AsyncClient(timeout=httpx.Timeout(120.0))
    redis_client = aioredis.from_url(settings.redis.url, decode_responses=True)
    yield
    await http_client.aclose()
    await redis_client.aclose()

app = FastAPI(
    title="GenAI Platform — API Gateway",
    version="2.0.0",
    lifespan=lifespan,
)

# ── Prometheus Instrumentation ────────────────────────────
Instrumentator().instrument(app).expose(app)

# Add middleware (order matters — last added runs first)
app.add_middleware(CorrelationIDMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Rate limiter integration
app.state.limiter = limiter

@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    return JSONResponse(
        status_code=429,
        content={"detail": "Rate limit exceeded. Please slow down.", "retry_after": str(exc.detail)},
    )


# ── Aggregated Health Check ────────────────────────────

@app.get("/health")
async def health():
    """Aggregated health check — pings all downstream services."""
    statuses = {"gateway": "ok"}
    all_ok = True
    for name, url in SERVICE_MAP.items():
        try:
            resp = await http_client.get(f"{url}/health", timeout=3.0)
            statuses[name] = "ok" if resp.status_code == 200 else "degraded"
            if resp.status_code != 200:
                all_ok = False
        except Exception:
            statuses[name] = "unavailable"
            all_ok = False
    return {
        "status": "ok" if all_ok else "degraded",
        "services": statuses,
        "timestamp": datetime.utcnow().isoformat(),
    }


# ── Auth Endpoints ────────────────────────────────────

@app.post("/api/auth/register")
@limiter.limit("10/minute")
async def register(request: Request, req: RegisterRequest):
    # MOCK AUTH: Bypass DB and return generic token
    token = create_access_token({"sub": "mock-user-id", "email": req.email})
    return {"token": token, "user_id": "mock-user-id", "email": req.email}


@app.post("/api/auth/login")
@limiter.limit("30/minute")
async def login(request: Request, req: LoginRequest):
    # MOCK AUTH: Always succeed with generic token
    token = create_access_token({"sub": "mock-user-id", "email": req.email})
    return {"token": token, "user_id": "mock-user-id", "email": req.email}


# ── Proxy helpers ─────────────────────────────────────

async def _proxy(service: str, path: str, request: Request, method: str = "GET") -> JSONResponse:
    """Forward a request to a downstream service."""
    base = SERVICE_MAP.get(service)
    if not base:
        raise HTTPException(status_code=404, detail=f"Unknown service: {service}")

    url = f"{base}{path}"
    headers = {k: v for k, v in request.headers.items() if k.lower() not in ("host", "content-length")}
    # Forward correlation ID
    if hasattr(request.state, "correlation_id"):
        headers["X-Correlation-ID"] = request.state.correlation_id

    if method == "GET":
        resp = await http_client.get(url, headers=headers, params=dict(request.query_params))
    else:
        body = await request.body()
        resp = await http_client.request(method, url, headers=headers, content=body)

    return JSONResponse(status_code=resp.status_code, content=resp.json())


async def _proxy_stream(service: str, path: str, request: Request) -> EventSourceResponse:
    """Proxy an SSE stream from a downstream service."""
    base = SERVICE_MAP.get(service)
    if not base:
        raise HTTPException(status_code=404, detail=f"Unknown service: {service}")

    url = f"{base}{path}"
    headers = {k: v for k, v in request.headers.items() if k.lower() not in ("host", "content-length")}
    if hasattr(request.state, "correlation_id"):
        headers["X-Correlation-ID"] = request.state.correlation_id
    body = await request.body()

    async def event_generator() -> AsyncIterator[dict]:
        async with http_client.stream("POST", url, headers=headers, content=body) as resp:
            async for line in resp.aiter_lines():
                if line.startswith("data:"):
                    yield {"data": line[5:].strip()}

    return EventSourceResponse(event_generator())


# ── RAG Routes ──────────────────────────────────────

@app.post("/api/rag/ingest")
async def rag_ingest(request: Request, _user: TokenData = Depends(get_current_user)):
    return await _proxy("rag", "/ingest", request, method="POST")


@app.post("/api/rag/query")
async def rag_query(request: Request, _user: TokenData = Depends(get_current_user)):
    return await _proxy("rag", "/query", request, method="POST")


@app.post("/api/rag/query/stream")
async def rag_query_stream(request: Request, _user: TokenData = Depends(get_current_user)):
    return await _proxy_stream("rag", "/query/stream", request)


@app.get("/api/rag/graph/{doc_id}")
async def rag_graph(doc_id: str, request: Request, _user: TokenData = Depends(get_current_user)):
    return await _proxy("rag", f"/graph/{doc_id}", request)


# ── KG Routes (Module 5 — Standalone Knowledge Graph) ──────────────

@app.post("/api/kg/extract")
async def kg_extract(request: Request, _user: TokenData = Depends(get_current_user)):
    return await _proxy("rag", "/kg/extract", request, method="POST")


@app.post("/api/kg/merge")
async def kg_merge(request: Request, _user: TokenData = Depends(get_current_user)):
    return await _proxy("rag", "/kg/merge", request, method="POST")


@app.get("/api/kg/entity/{entity_name}")
async def kg_entity(entity_name: str, request: Request, _user: TokenData = Depends(get_current_user)):
    return await _proxy("rag", f"/kg/entity/{entity_name}", request)


@app.get("/api/kg/stats")
async def kg_stats(request: Request, _user: TokenData = Depends(get_current_user)):
    return await _proxy("rag", "/kg/stats", request)


# ── ATS Routes ──────────────────────────────────────

@app.post("/api/ats/analyze")
async def ats_analyze(request: Request, _user: TokenData = Depends(get_current_user)):
    return await _proxy("ats", "/analyze", request, method="POST")


@app.post("/api/ats/analyze/stream")
async def ats_analyze_stream(request: Request, _user: TokenData = Depends(get_current_user)):
    return await _proxy_stream("ats", "/analyze/stream", request)


@app.get("/api/ats/report/{task_id}")
async def ats_report(task_id: str, request: Request, _user: TokenData = Depends(get_current_user)):
    return await _proxy("ats", f"/report/{task_id}", request)


# ── Research Routes ─────────────────────────────────

@app.post("/api/research/start")
async def research_start(request: Request, _user: TokenData = Depends(get_current_user)):
    return await _proxy("research", "/research", request, method="POST")


@app.get("/api/research/status/{task_id}")
async def research_status(task_id: str, request: Request, _user: TokenData = Depends(get_current_user)):
    return await _proxy("research", f"/status/{task_id}", request)


@app.get("/api/research/status/{task_id}/stream")
async def research_status_stream(task_id: str, request: Request, _user: TokenData = Depends(get_current_user)):
    return await _proxy_stream("research", f"/status/{task_id}/stream", request)


@app.get("/api/research/report/{task_id}")
async def research_report(task_id: str, request: Request, _user: TokenData = Depends(get_current_user)):
    return await _proxy("research", f"/report/{task_id}", request)


# ── SQL Routes ──────────────────────────────────────

@app.post("/api/sql/generate")
async def sql_generate(request: Request, _user: TokenData = Depends(get_current_user)):
    return await _proxy("sql", "/generate", request, method="POST")


@app.post("/api/sql/execute")
async def sql_execute(request: Request, _user: TokenData = Depends(get_current_user)):
    return await _proxy("sql", "/execute", request, method="POST")


@app.get("/api/sql/schema")
async def sql_schema(request: Request, _user: TokenData = Depends(get_current_user)):
    return await _proxy("sql", "/schema", request)


# ── Stats ──────────────────────────────────────────────

@app.get("/api/stats")
async def platform_stats(_user: TokenData = Depends(get_current_user)):
    """Return aggregate platform usage stats for the dashboard."""
    import asyncpg
    conn = await asyncpg.connect(settings.postgres.dsn)
    try:
        docs = await conn.fetchval("SELECT COUNT(*) FROM pdf_documents") or 0
        reports = await conn.fetchval("SELECT COUNT(*) FROM research_tasks") or 0
        queries = await conn.fetchval("SELECT COUNT(*) FROM sql_queries") or 0
        return {"documents": docs, "reports": reports, "queries": queries}
    except Exception:
        return {"documents": 0, "reports": 0, "queries": 0}
    finally:
        await conn.close()
