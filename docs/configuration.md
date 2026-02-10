# Configuration Reference

All configuration is via environment variables. Copy `.env.example` to `.env` and customize.

## LLM Provider

| Variable | Default | Description |
|----------|---------|-------------|
| `OLLAMA_BASE_URL` | `http://ollama:11434` | Ollama API endpoint |
| `OLLAMA_MODEL` | `llama3` | Model for text generation |
| `OLLAMA_EMBED_MODEL` | `nomic-embed-text` | Model for embeddings |

## PostgreSQL

| Variable | Default | Description |
|----------|---------|-------------|
| `POSTGRES_USER` | `genai` | Database user |
| `POSTGRES_PASSWORD` | `genai_secret_2024` | Database password |
| `POSTGRES_DB` | `genai_platform` | Database name |
| `POSTGRES_HOST` | `postgres` | Host (container name) |
| `POSTGRES_PORT` | `5432` | Port |
| `DATABASE_URL` | (composed) | Full connection string |

## Redis

| Variable | Default | Description |
|----------|---------|-------------|
| `REDIS_URL` | `redis://redis:6379/0` | Redis connection URL |

Used for: embedding cache (1h TTL), session storage.

## Qdrant (Vector DB)

| Variable | Default | Description |
|----------|---------|-------------|
| `QDRANT_HOST` | `qdrant` | Qdrant host |
| `QDRANT_PORT` | `6333` | Qdrant HTTP port |
| `QDRANT_COLLECTION` | `pdf_chunks` | Collection name |

## Neo4j (Graph DB)

| Variable | Default | Description |
|----------|---------|-------------|
| `NEO4J_URI` | `bolt://neo4j:7687` | Neo4j Bolt URI |
| `NEO4J_USER` | `neo4j` | Neo4j username |
| `NEO4J_PASSWORD` | `neo4j_secret_2024` | Neo4j password |

## Security

| Variable | Default | Description |
|----------|---------|-------------|
| `JWT_SECRET` | (change me) | 64-char random string for JWT signing |

## Search APIs (Research Assistant)

| Variable | Default | Description |
|----------|---------|-------------|
| `TAVILY_API_KEY` | (empty) | Tavily search API key (preferred) |
| `SERPER_API_KEY` | (empty) | Serper search API key (fallback) |

At least one search API key is required for the Research Assistant. Tavily is preferred; Serper is used as fallback.

## Service Ports

| Variable | Default | Description |
|----------|---------|-------------|
| `GATEWAY_PORT` | `8000` | API Gateway |
| `RAG_SERVICE_PORT` | `8001` | PDF RAG Service |
| `ATS_SERVICE_PORT` | `8002` | ATS Agent Service |
| `RESEARCH_SERVICE_PORT` | `8003` | Research Service |
| `SQL_SERVICE_PORT` | `8004` | SQL Service |

## Rate Limits

Configured in `api-gateway/main.py`:

| Endpoint | Limit |
|----------|-------|
| Global default | 120/minute |
| `/api/auth/register` | 10/minute |
| `/api/auth/login` | 30/minute |

## Tuning Parameters

| Parameter | Location | Default | Description |
|-----------|----------|---------|-------------|
| Chunk size | `ingestion.py` | 512 tokens | Token count per chunk |
| Chunk overlap | `ingestion.py` | 50 tokens | Overlap between chunks |
| Embedding cache TTL | `retrieval.py` | 3600s (1h) | Redis cache duration |
| JWT expiry | `main.py` (gateway) | 24 hours | Token lifetime |
| Query top-K | Request param | 5 | Default retrieval results |
| SQL row limit | `main.py` (sql) | 1000 | Maximum rows returned |
