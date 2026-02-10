# System Architecture

## Overview

The GenAI Platform follows a **microservices architecture** with 5 independent services behind a central API Gateway. Each service owns its domain logic and communicates only through the gateway.

## Service Topology

```
                          ┌──────────────┐
                          │   Frontend   │
                          │  (React/Vite)│
                          └──────┬───────┘
                                 │ HTTPS
                          ┌──────▼───────┐
                          │ API Gateway  │
                          │  :8000       │
                          │ ─ JWT Auth   │
                          │ ─ Rate Limit │
                          │ ─ Logging    │
                          └──┬──┬──┬──┬──┘
              ┌──────────────┘  │  │  └──────────────┐
              ▼                 ▼  ▼                  ▼
     ┌────────────┐   ┌────────┐ ┌────────┐   ┌──────────┐
     │ PDF-RAG    │   │  ATS   │ │Research│   │   SQL    │
     │ :8001      │   │ :8002  │ │ :8003  │   │  :8004   │
     │ + KG Engine│   │6 agents│ │7 stages│   │3-layer   │
     └────┬───────┘   └────────┘ └───┬────┘   └────┬─────┘
          │                          │              │
    ┌─────┼─────────────────────────┼──────────────┘
    │     │                         │
    ▼     ▼                         ▼
 Qdrant  Neo4j                  Tavily/Serper
(vector) (graph)                (web search)
    │     │                         │
    └─────┼─────────────────────────┘
          │
    ┌─────▼─────┐   ┌───────┐   ┌────────┐
    │PostgreSQL │   │ Redis │   │ Ollama │
    │  (state)  │   │(cache)│   │ (LLM)  │
    └───────────┘   └───────┘   └────────┘
```

## Data Flow

### PDF Ingestion Pipeline
1. User uploads PDF → API Gateway → PDF-RAG Service
2. PyMuPDF extracts text → tiktoken chunks (512 tokens, 50 overlap)
3. LLM generates embeddings → stored in Qdrant
4. KG Engine extracts entities/relationships → stored in Neo4j
5. Metadata stored in PostgreSQL

### Query Pipeline (Hybrid Retrieval)
1. Query embedding generated (checked against Redis cache first)
2. **Vector path**: Qdrant cosine similarity → top-K chunks
3. **Graph path**: LLM extracts entities → 2-hop Neo4j traversal
4. Both contexts merged → LLM synthesizes final answer

### Multi-Agent Execution (ATS)
1. Coordinator Agent plans execution strategy
2. 4 analysis agents run in **parallel** (`asyncio.gather`):
   - Keyword Agent, Format Agent, Content Agent, Job Match Agent
3. Improvement Agent generates rewrite suggestions
4. Programmatic 40/30/30 scoring applied

## Technology Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| Frontend | React + TypeScript + Vite | SPA with streaming support |
| Gateway | FastAPI + slowapi + jose | Auth, rate limiting, proxy |
| Services | FastAPI + LiteLLM | Domain-specific microservices |
| Vector DB | Qdrant | Embedding similarity search |
| Graph DB | Neo4j | Knowledge graph storage |
| RDBMS | PostgreSQL 15 | State, users, metadata |
| Cache | Redis 7 | Embedding cache, sessions |
| LLM | Ollama (LiteLLM abstraction) | Text generation, embeddings |
| Search | Tavily / Serper | Web search for research |

## Security

- **JWT authentication** via API Gateway (bcrypt password hashing)
- **Rate limiting**: 120 req/min global, 10/min registration, 30/min login
- **SQL safety**: Triple-layer validation (AST parse, regex blocklist, LIMIT enforcement)
- **Read-only transactions** for all SQL query execution
- **Correlation IDs** for distributed request tracing
