# Module 1: PDF Chat + GraphRAG

## Overview

The PDF Chat module combines **vector-based retrieval** with **knowledge graph traversal** for intelligent document question-answering. This hybrid approach (GraphRAG) provides both semantic similarity matching and structured relationship reasoning.

## Components

| File | Purpose |
|------|---------|
| `services/pdf-rag-service/main.py` | FastAPI endpoints for ingest, query, graph, and KG |
| `services/pdf-rag-service/ingestion.py` | PDF → chunks → embeddings → KG pipeline |
| `services/pdf-rag-service/retrieval.py` | Hybrid vector + graph retrieval with Redis cache |
| `services/pdf-rag-service/kg_engine.py` | Standalone Knowledge Graph engine |

## Ingestion Pipeline

```
PDF Upload
    │
    ▼
Text Extraction (PyMuPDF)
    │
    ▼
Chunking (512 tokens, 50 overlap via tiktoken)
    │
    ├──▶ Embeddings → Qdrant (vector store)
    │
    └──▶ KG Engine → Entity/Relationship extraction → Neo4j
```

## Retrieval Strategy

1. **Embedding cache check** — SHA256 hash of query → Redis (1-hour TTL)
2. **Vector search** — Qdrant cosine similarity, top-K chunks
3. **Graph search** — LLM extracts entities from query → 2-hop Neo4j traversal
4. **Synthesis** — Both contexts merged, LLM generates cited answer

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/ingest` | Upload and process a PDF |
| POST | `/query` | Hybrid retrieval query |
| POST | `/query/stream` | Streaming query (SSE) |
| GET | `/graph/{doc_id}` | Get document knowledge graph |

## Configuration

- `QDRANT_HOST`, `QDRANT_PORT`, `QDRANT_COLLECTION` — Vector store
- `NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD` — Graph database
- Chunk size and overlap configurable in `ingestion.py` constants
