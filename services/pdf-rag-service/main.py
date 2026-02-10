"""
PDF RAG Service — GraphRAG + Vector Search for intelligent document Q&A.

Endpoints:
  POST /ingest            — Upload and process PDF → chunks, embeddings, knowledge graph
  POST /query             — Hybrid retrieval (vector + graph) → synthesized answer
  GET  /graph/{doc_id}    — Return knowledge graph for visualization
  POST /kg/extract        — Extract KG from arbitrary text (standalone Module 5)
  POST /kg/merge          — Merge graphs across documents with entity resolution
  GET  /kg/entity/{name}  — Entity neighborhood subgraph
  GET  /kg/stats          — Knowledge graph statistics
"""

from __future__ import annotations

import logging
import os
import tempfile
import uuid
from contextlib import asynccontextmanager

import asyncpg
from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.responses import JSONResponse
from sse_starlette.sse import EventSourceResponse

import sys
sys.path.insert(0, os.path.dirname(__file__))
from shared.config import get_settings
from shared.models import (
    QueryRequest, QueryResponse, GraphResponse, GraphNode, GraphEdge,
    ChunkSource, GraphTriple, HealthResponse,
    KGExtractRequest, KGMergeRequest, KGStatsResponse,
)
from ingestion import PDFIngestionPipeline
from retrieval import HybridRetriever

logger = logging.getLogger(__name__)
settings = get_settings()

db_pool: asyncpg.Pool | None = None
ingestion: PDFIngestionPipeline | None = None
retriever: HybridRetriever | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global db_pool, ingestion, retriever
    db_pool = await asyncpg.create_pool(settings.postgres.dsn, min_size=2, max_size=10)
    ingestion = PDFIngestionPipeline(settings)
    retriever = HybridRetriever(settings)
    await ingestion.initialize()
    await retriever.initialize()
    yield
    await db_pool.close()
    await ingestion.close()
    await retriever.close()


app = FastAPI(title="PDF RAG Service", version="1.0.0", lifespan=lifespan)


@app.get("/health")
async def health():
    return HealthResponse(service="pdf-rag-service")


@app.post("/ingest")
async def ingest_pdf(
    file: UploadFile = File(...),
    user_id: str = Form("anonymous"),
):
    """Process an uploaded PDF: extract text, chunk, embed, build graph."""
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted")

    # Save uploaded file to temp location
    doc_id = str(uuid.uuid4())
    tmp_dir = tempfile.mkdtemp()
    tmp_path = os.path.join(tmp_dir, file.filename)

    content = await file.read()
    with open(tmp_path, "wb") as f:
        f.write(content)

    try:
        result = await ingestion.process(
            pdf_path=tmp_path,
            doc_id=doc_id,
            user_id=user_id,
            filename=file.filename,
        )

        # Store metadata in PostgreSQL
        async with db_pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO pdf_documents (id, user_id, filename, file_path, file_size, chunk_count, entity_count, processed)
                VALUES ($1, $2::uuid, $3, $4, $5, $6, $7, TRUE)
                """,
                uuid.UUID(doc_id),
                uuid.UUID(user_id) if user_id != "anonymous" else None,
                file.filename,
                tmp_path,
                len(content),
                result["chunk_count"],
                result["entity_count"],
            )

        return {
            "document_id": doc_id,
            "filename": file.filename,
            "chunk_count": result["chunk_count"],
            "entity_count": result["entity_count"],
            "relationship_count": result["relationship_count"],
            "message": f"Successfully processed {file.filename}",
        }
    except Exception as e:
        logger.exception("Ingestion failed")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


@app.post("/query")
async def query(req: QueryRequest):
    """Hybrid retrieval: vector search + graph traversal → synthesized answer."""
    try:
        result = await retriever.query(
            query=req.query,
            document_ids=req.document_ids,
            top_k=req.top_k,
            use_graph=req.use_graph,
        )
        return result
    except Exception as e:
        logger.exception("Query failed")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/query/stream")
async def query_stream(req: QueryRequest):
    """Streaming version of the query endpoint using SSE."""
    async def event_generator():
        async for token in retriever.query_stream(
            query=req.query,
            document_ids=req.document_ids,
            top_k=req.top_k,
            use_graph=req.use_graph,
        ):
            yield {"data": token}

    return EventSourceResponse(event_generator())


@app.get("/graph/{doc_id}")
async def get_graph(doc_id: str):
    """Return knowledge graph nodes and edges for visualization."""
    try:
        graph = await retriever.get_document_graph(doc_id)
        return graph
    except Exception as e:
        logger.exception("Graph retrieval failed")
        raise HTTPException(status_code=500, detail=str(e))


# ── Knowledge Graph Standalone Endpoints (Module 5) ────────────

@app.post("/kg/extract")
async def kg_extract(req: KGExtractRequest):
    """Extract a knowledge graph from arbitrary text (not just PDFs)."""
    try:
        extraction = await ingestion.kg_engine.extract_entities(
            text=req.text, source_label=req.source_label
        )
        return {
            "entity_count": len(extraction.entities),
            "relationship_count": len(extraction.relationships),
            "entities": [
                {"name": e.name, "type": e.type.value if hasattr(e.type, 'value') else e.type, "description": e.description}
                for e in extraction.entities
            ],
            "relationships": [
                {"source": r.source, "target": r.target, "relationship": r.relationship,
                 "description": r.description, "confidence": r.confidence}
                for r in extraction.relationships
            ],
        }
    except Exception as e:
        logger.exception("KG extraction failed")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/kg/merge")
async def kg_merge(req: KGMergeRequest):
    """Merge knowledge graphs across multiple documents with optional entity resolution."""
    try:
        result = await ingestion.kg_engine.merge_documents(
            document_ids=req.document_ids, resolve=req.resolve_entities
        )
        return result
    except Exception as e:
        logger.exception("KG merge failed")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/kg/entity/{entity_name}")
async def kg_entity_neighborhood(entity_name: str, hops: int = 2):
    """Retrieve the subgraph neighborhood around a specific entity."""
    try:
        graph = await ingestion.kg_engine.get_entity_neighborhood(entity_name, hops=hops)
        return graph
    except Exception as e:
        logger.exception("Entity neighborhood retrieval failed")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/kg/stats")
async def kg_stats(doc_id: str | None = None):
    """Get knowledge graph statistics (optionally filtered by document)."""
    try:
        stats = await ingestion.kg_engine.get_stats(doc_id=doc_id)
        return KGStatsResponse(**stats)
    except Exception as e:
        logger.exception("KG stats retrieval failed")
        raise HTTPException(status_code=500, detail=str(e))
