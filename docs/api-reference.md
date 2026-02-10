# API Reference

All endpoints are accessed through the API Gateway at `http://localhost:8000`.

## Authentication

### POST `/api/auth/register`
Register a new user account.

**Rate limit:** 10/minute

```json
// Request
{ "email": "user@example.com", "password": "secret", "display_name": "John" }

// Response
{ "token": "eyJ...", "user_id": "uuid", "email": "user@example.com" }
```

### POST `/api/auth/login`
Authenticate and receive JWT token.

**Rate limit:** 30/minute

```json
// Request
{ "email": "user@example.com", "password": "secret" }

// Response
{ "token": "eyJ...", "user_id": "uuid", "email": "user@example.com" }
```

> All endpoints below require `Authorization: Bearer <token>` header.

---

## PDF RAG (Module 1)

### POST `/api/rag/ingest`
Upload and process a PDF document.

- **Content-Type:** `multipart/form-data`
- **Fields:** `file` (PDF), `user_id` (optional)

### POST `/api/rag/query`
```json
{ "query": "What is...", "document_ids": ["uuid"], "top_k": 5, "use_graph": true }
```

### POST `/api/rag/query/stream`
Same request as `/query`, returns Server-Sent Events (SSE).

### GET `/api/rag/graph/{doc_id}`
Returns knowledge graph nodes and edges for visualization.

---

## ATS Analyzer (Module 2)

### POST `/api/ats/analyze`
```json
{ "resume_text": "Resume content...", "job_description": "Optional JD..." }
```

### POST `/api/ats/analyze/stream`
Same request, returns SSE with stage-by-stage progress.

### GET `/api/ats/report/{task_id}`
Retrieve a completed ATS analysis report.

---

## Research Assistant (Module 3)

### POST `/api/research/start`
```json
{ "query": "Research topic...", "depth": "standard" }
```

**Depth options:** `quick`, `standard`, `deep`

### GET `/api/research/status/{task_id}/stream`
SSE stream with stage-by-stage progress.

### GET `/api/research/report/{task_id}`
Retrieve completed research report with sources and contradictions.

---

## Text-to-SQL (Module 4)

### POST `/api/sql/generate`
```json
{ "query": "Show me the top 10 users by sign-up date" }
```

### POST `/api/sql/execute`
```json
{ "sql": "SELECT * FROM users ORDER BY created_at DESC LIMIT 10;" }
```

### GET `/api/sql/schema`
Returns the full database schema (tables, columns, types, FKs).

---

## Knowledge Graph (Module 5)

### POST `/api/kg/extract`
```json
{ "text": "Arbitrary text to extract knowledge from...", "source_label": "meeting_notes" }
```

### POST `/api/kg/merge`
```json
{ "document_ids": ["uuid1", "uuid2"], "resolve_entities": true }
```

### GET `/api/kg/entity/{entity_name}?hops=2`
Returns the N-hop neighborhood subgraph around an entity.

### GET `/api/kg/stats?doc_id=optional`
Returns entity and relationship counts by type.

---

## Platform

### GET `/health`
Aggregated health check for all services. Returns `ok` or `degraded` status.

### GET `/api/stats`
Returns aggregate platform usage counts (documents, reports, queries).
