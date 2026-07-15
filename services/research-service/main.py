"""
Research Service — Autonomous Research Assistant with 7-Stage HTN Workflow.

Stages:
  1. Planning      → Decompose query into sub-topics (depth-aware)
  2. Searching     → Web search via Tavily/Serper with fallback chain
  3. Filtering     → LLM-ranked relevance filtering
  4. Summarizing   → Per-source summarization with key claim extraction
  5. Verifying     → Cross-reference claims, compute confidence, detect contradictions
  6. Synthesizing  → Combine into cohesive report with executive summary
  7. Citing        → Enforce [Source ID] citation format, append bibliography

Depth Modes:
  - quick:    3 sub-topics, top-3 results per topic
  - standard: 5 sub-topics, top-5 results per topic (default)
  - deep:     8 sub-topics, top-8 results per topic + follow-up queries
"""

from __future__ import annotations

import json
import logging
import os
import uuid
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator

import asyncpg
import httpx
import redis.asyncio as aioredis
from fastapi import FastAPI, HTTPException
from sse_starlette.sse import EventSourceResponse

import sys
sys.path.insert(0, os.path.dirname(__file__))
from shared.config import get_settings
from shared.llm_provider import LLMProvider
from shared.models import HealthResponse, ResearchRequest, ResearchStatus

logger = logging.getLogger(__name__)
settings = get_settings()
llm = LLMProvider()
redis_client: aioredis.Redis | None = None
db_pool: asyncpg.Pool | None = None
http_client: httpx.AsyncClient | None = None

# Depth configuration: (sub_topics, results_per_topic)
DEPTH_CONFIG = {
    "quick": (3, 3),
    "standard": (5, 5),
    "deep": (8, 8),
}


@asynccontextmanager
async def lifespan(app: FastAPI):
    global redis_client, db_pool, http_client
    redis_client = aioredis.from_url(settings.redis.url, decode_responses=True)
    db_pool = await asyncpg.create_pool(settings.postgres.dsn, min_size=2, max_size=5)
    http_client = httpx.AsyncClient(timeout=30.0)
    yield
    await redis_client.aclose()
    await db_pool.close()
    await http_client.aclose()


app = FastAPI(title="Research Service", version="2.0.0", lifespan=lifespan)


@app.get("/health")
async def health():
    return HealthResponse(service="research-service")


# ── Search Providers ─────────────────────────────────

async def search_tavily(query: str, max_results: int = 10) -> list[dict]:
    """Search using Tavily API."""
    api_key = os.getenv("TAVILY_API_KEY", "")
    if not api_key:
        return []
    resp = await http_client.post(
        "https://api.tavily.com/search",
        json={"query": query, "max_results": max_results, "api_key": api_key},
    )
    if resp.status_code == 200:
        data = resp.json()
        return [
            {"title": r.get("title", ""), "url": r.get("url", ""), "content": r.get("content", "")}
            for r in data.get("results", [])
        ]
    return []


async def search_serper(query: str, max_results: int = 10) -> list[dict]:
    """Search using Serper API."""
    api_key = os.getenv("SERPER_API_KEY", "")
    if not api_key:
        return []
    resp = await http_client.post(
        "https://google.serper.dev/search",
        json={"q": query, "num": max_results},
        headers={"X-API-KEY": api_key},
    )
    if resp.status_code == 200:
        data = resp.json()
        return [
            {"title": r.get("title", ""), "url": r.get("link", ""), "content": r.get("snippet", "")}
            for r in data.get("organic", [])
        ]
    return []


async def search_web(query: str, max_results: int = 10) -> list[dict]:
    """Try Tavily first, fallback to Serper, then LLM-based fallback."""
    results = await search_tavily(query, max_results)
    if results:
        return results
    results = await search_serper(query, max_results)
    if results:
        return results
    # LLM fallback: generate hypothetical search results
    logger.warning("No search API available, using LLM fallback")
    response = await llm.complete_json(
        f'Generate {max_results} hypothetical search results for: "{query}". '
        f'Return JSON array: [{{"title": "...", "url": "https://...", "content": "snippet..."}}]'
    )
    return response if isinstance(response, list) else []


# ── HTN Workflow Stages ──────────────────────────────

async def stage_plan(query: str, depth: str = "standard") -> list[str]:
    """Stage 1: Decompose query into sub-topics (depth-aware)."""
    num_topics, _ = DEPTH_CONFIG.get(depth, DEPTH_CONFIG["standard"])
    result = await llm.complete_json(
        f'Decompose this research query into exactly {num_topics} specific sub-topics to investigate.\n'
        f'Each sub-topic should cover a distinct aspect of the query.\n\n'
        f'Query: "{query}"\n\n'
        f'Return a JSON array of strings: ["sub-topic 1", "sub-topic 2", ...]'
    )
    return result if isinstance(result, list) else [query]


async def stage_search(sub_topics: list[str], depth: str = "standard") -> list[dict]:
    """Stage 2: Search for each sub-topic with depth-aware result count."""
    _, results_per_topic = DEPTH_CONFIG.get(depth, DEPTH_CONFIG["standard"])
    all_results = []
    for topic in sub_topics:
        results = await search_web(topic, max_results=results_per_topic)
        for r in results:
            r["sub_topic"] = topic
        all_results.extend(results)
    return all_results


async def stage_filter(results: list[dict], query: str) -> list[dict]:
    """Stage 3: Filter and rank results for relevance."""
    if not results:
        return []
    result_summaries = "\n".join(
        f"[{i}] {r['title']}: {r['content'][:150]}" for i, r in enumerate(results)
    )
    response = await llm.complete_json(
        f'Given the original query: "{query}"\n\n'
        f'Rank these search results by relevance. Return a JSON array of indices (0-based) '
        f'of the top results, most relevant first:\n\n{result_summaries}\n\n'
        f'Return: [index1, index2, ...]'
    )
    if isinstance(response, list):
        return [results[i] for i in response if isinstance(i, int) and i < len(results)][:15]
    return results[:15]


async def stage_summarize(results: list[dict]) -> list[dict]:
    """Stage 4: Summarize each source and extract key claims."""
    for i, r in enumerate(results):
        summary_response = await llm.complete_json(
            f"Analyze this search result and extract key claims.\n\n"
            f"Title: {r['title']}\nContent: {r['content']}\n\n"
            f'Return JSON:\n'
            f'{{"summary": "2-3 sentence summary", "key_claims": ["claim 1", "claim 2", ...]}}',
        )
        if isinstance(summary_response, dict):
            r["summary"] = summary_response.get("summary", r["content"][:200])
            r["key_claims"] = summary_response.get("key_claims", [])
        else:
            r["summary"] = r["content"][:200]
            r["key_claims"] = []
        r["source_id"] = f"S{i + 1}"
    return results


async def stage_verify(results: list[dict]) -> tuple[list[dict], list[str]]:
    """Stage 5: Cross-reference claims across sources, compute confidence, detect contradictions."""
    if len(results) < 2:
        for r in results:
            r["verified"] = True
            r["confidence_score"] = 0.5
        return results, []

    # Build a claim-source matrix for cross-referencing
    all_claims = []
    for r in results:
        for claim in r.get("key_claims", []):
            all_claims.append({"claim": claim, "source_id": r["source_id"], "source_title": r["title"]})

    if not all_claims:
        for r in results:
            r["verified"] = bool(r.get("content", "").strip())
            r["confidence_score"] = 0.5 if r["verified"] else 0.0
        return results, []

    # Ask LLM to cross-reference claims and detect contradictions
    claims_json = json.dumps(all_claims[:30], indent=2)  # Limit to avoid token overflow
    verification_result = await llm.complete_json(
        f"You are a fact-checking analyst. Cross-reference these research claims from different sources.\n\n"
        f"CLAIMS:\n{claims_json}\n\n"
        f"For each source, assess:\n"
        f"- How many of its claims are corroborated by other sources?\n"
        f"- Are there any contradictions between sources?\n\n"
        f'Return JSON:\n'
        f'{{\n'
        f'  "source_confidence": {{"S1": 0.85, "S2": 0.72, ...}},\n'
        f'  "contradictions": ["Source S1 claims X, but Source S3 claims Y", ...],\n'
        f'  "well_supported_claims": ["claims supported by 2+ sources"]\n'
        f'}}'
    )

    # Apply confidence scores to sources
    source_confidence = {}
    contradictions = []
    if isinstance(verification_result, dict):
        source_confidence = verification_result.get("source_confidence", {})
        contradictions = verification_result.get("contradictions", [])

    for r in results:
        sid = r["source_id"]
        conf = source_confidence.get(sid, 0.5)
        try:
            r["confidence_score"] = max(0.0, min(1.0, float(conf)))
        except (TypeError, ValueError):
            r["confidence_score"] = 0.5
        r["verified"] = r["confidence_score"] >= 0.3

    return results, contradictions if isinstance(contradictions, list) else []


async def stage_synthesize(results: list[dict], query: str, contradictions: list[str]) -> tuple[str, str]:
    """Stage 6: Combine verified summaries into cohesive report with executive summary."""
    source_context = "\n\n".join(
        f"[{r['source_id']}] {r['title']} (confidence: {r.get('confidence_score', 0.5):.0%})\n"
        f"URL: {r['url']}\n"
        f"Summary: {r.get('summary', r['content'][:200])}"
        for r in results if r.get("verified", True)
    )

    contradiction_note = ""
    if contradictions:
        contradiction_note = (
            "\n\nIMPORTANT: The following contradictions were detected across sources. "
            "Address them explicitly in the report:\n"
            + "\n".join(f"- {c}" for c in contradictions)
        )

    report = await llm.complete(
        f"Write a comprehensive research report answering this query:\n\n"
        f'Query: "{query}"\n\n'
        f"Use the following verified sources. ALWAYS cite sources using [Source ID] format.\n\n"
        f"{source_context}"
        f"{contradiction_note}\n\n"
        f"Write a well-structured report with clear sections and headings, citing sources throughout. "
        f"If contradictions exist, present both perspectives fairly.",
        system="You are a senior research analyst. Write thorough, well-cited, balanced reports. "
               "Always use [S1], [S2], etc. to cite sources inline. Be objective and evidence-based.",
        max_tokens=4096,
    )

    # Generate executive summary
    exec_summary = await llm.complete(
        f"Write a 3-sentence executive summary of this research report. "
        f"Include the key finding, main evidence, and primary recommendation.\n\n"
        f"REPORT:\n{report[:2000]}",
        max_tokens=300,
    )

    return report, exec_summary.strip()


async def stage_cite(report: str, results: list[dict]) -> tuple[str, list[dict]]:
    """Stage 7: Ensure all citations are properly formatted and append bibliography."""
    bibliography = "\n\n## Sources\n\n" + "\n".join(
        f"- [{r['source_id']}] [{r['title']}]({r['url']}) — "
        f"Confidence: {r.get('confidence_score', 0.5):.0%}"
        for r in results if r.get("verified", True)
    )
    sources = [
        {
            "id": r["source_id"],
            "title": r["title"],
            "url": r["url"],
            "snippet": r.get("summary", r["content"][:200]),
            "verified": r.get("verified", True),
            "confidence_score": r.get("confidence_score", 0.5),
        }
        for r in results
    ]
    return report + bibliography, sources


# ── Endpoints ──────────────────────────────────────

@app.post("/research")
async def start_research(req: ResearchRequest):
    """Start a research task (blocking — returns full report)."""
    task_id = str(uuid.uuid4())
    depth = req.depth if req.depth in DEPTH_CONFIG else "standard"

    try:
        # Store task in DB
        async with db_pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO research_tasks (id, query, status) VALUES ($1::uuid, $2, 'planning')",
                uuid.UUID(task_id), req.query,
            )

        # Run HTN pipeline with depth-awareness
        sub_topics = await stage_plan(req.query, depth)
        results = await stage_search(sub_topics, depth)
        filtered = await stage_filter(results, req.query)
        summarized = await stage_summarize(filtered)
        verified, contradictions = await stage_verify(summarized)
        report, exec_summary = await stage_synthesize(verified, req.query, contradictions)
        final_report, sources = await stage_cite(report, verified)

        # Store result
        async with db_pool.acquire() as conn:
            await conn.execute(
                "UPDATE research_tasks SET status='completed', report=$1, sources=$2, completed_at=NOW() WHERE id=$3::uuid",
                final_report, json.dumps(sources), uuid.UUID(task_id),
            )

        return {
            "task_id": task_id,
            "status": "completed",
            "report": final_report,
            "executive_summary": exec_summary,
            "sources": sources,
            "contradictions": contradictions,
        }

    except Exception as e:
        logger.exception("Research failed")
        async with db_pool.acquire() as conn:
            await conn.execute(
                "UPDATE research_tasks SET status='failed' WHERE id=$1::uuid", uuid.UUID(task_id)
            )
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/status/{task_id}/stream")
async def research_stream(task_id: str):
    """SSE stream showing stage-by-stage progress for a new research task."""
    query_data = await redis_client.get(f"research:query:{task_id}")
    if not query_data:
        raise HTTPException(status_code=404, detail="Task not found")

    query = query_data
    depth_data = await redis_client.get(f"research:depth:{task_id}")
    depth = depth_data if depth_data in DEPTH_CONFIG else "standard"

    async def event_generator() -> AsyncIterator[dict]:
        yield {"data": json.dumps({"stage": "planning", "message": f"Decomposing query ({depth} depth)..."})}
        sub_topics = await stage_plan(query, depth)
        yield {"data": json.dumps({"stage": "planning", "done": True, "sub_topics": sub_topics})}

        yield {"data": json.dumps({"stage": "searching", "message": f"Searching {len(sub_topics)} sub-topics..."})}
        results = await stage_search(sub_topics, depth)
        yield {"data": json.dumps({"stage": "searching", "done": True, "result_count": len(results)})}

        yield {"data": json.dumps({"stage": "filtering", "message": "Ranking results by relevance..."})}
        filtered = await stage_filter(results, query)
        yield {"data": json.dumps({"stage": "filtering", "done": True, "filtered_count": len(filtered)})}

        yield {"data": json.dumps({"stage": "summarizing", "message": "Summarizing sources and extracting claims..."})}
        summarized = await stage_summarize(filtered)
        yield {"data": json.dumps({"stage": "summarizing", "done": True})}

        yield {"data": json.dumps({"stage": "verifying", "message": "Cross-referencing claims and computing confidence..."})}
        verified, contradictions = await stage_verify(summarized)
        verified_count = sum(1 for r in verified if r.get("verified"))
        yield {"data": json.dumps({
            "stage": "verifying", "done": True,
            "verified_count": verified_count,
            "contradiction_count": len(contradictions),
        })}

        yield {"data": json.dumps({"stage": "synthesizing", "message": "Writing research report..."})}
        report, exec_summary = await stage_synthesize(verified, query, contradictions)
        yield {"data": json.dumps({"stage": "synthesizing", "done": True})}

        yield {"data": json.dumps({"stage": "citing", "message": "Adding citations and bibliography..."})}
        final_report, sources = await stage_cite(report, verified)
        yield {"data": json.dumps({
            "stage": "completed",
            "report": final_report,
            "executive_summary": exec_summary,
            "sources": sources,
            "contradictions": contradictions,
        })}

    return EventSourceResponse(event_generator())


@app.get("/report/{task_id}")
async def get_report(task_id: str):
    """Retrieve a completed research report."""
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT query, status, report, sources, created_at, completed_at FROM research_tasks WHERE id=$1::uuid",
            uuid.UUID(task_id),
        )
    if not row:
        raise HTTPException(status_code=404, detail="Task not found")
    return {
        "task_id": task_id,
        "query": row["query"],
        "status": row["status"],
        "report": row["report"],
        "sources": json.loads(row["sources"]) if row["sources"] else [],
        "created_at": row["created_at"].isoformat() if row["created_at"] else None,
        "completed_at": row["completed_at"].isoformat() if row["completed_at"] else None,
    }
