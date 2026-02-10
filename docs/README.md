<p align="center">
  <h1 align="center">🧠 GenAI Platform</h1>
  <p align="center">
    <strong>A Unified Multimodal GenAI Platform</strong><br>
    Integrating GraphRAG, Multi-Agent Systems, and Custom Language Models<br>
    for Intelligent Document Processing &amp; Knowledge Synthesis
  </p>
  <p align="center">
    <img src="https://img.shields.io/badge/Python-3.11+-blue?logo=python&logoColor=white" alt="Python">
    <img src="https://img.shields.io/badge/React-18-61DAFB?logo=react&logoColor=black" alt="React">
    <img src="https://img.shields.io/badge/FastAPI-0.109-009688?logo=fastapi&logoColor=white" alt="FastAPI">
    <img src="https://img.shields.io/badge/Docker-Compose-2496ED?logo=docker&logoColor=white" alt="Docker">
    <img src="https://img.shields.io/badge/License-MIT-green" alt="License">
  </p>
</p>

---

## ✨ What Is This?

GenAI Platform is a **production-grade**, microservices-based AI system that combines five powerful modules into a single unified platform:

| # | Module | What It Does |
|---|--------|-------------|
| 1 | **PDF Chat + GraphRAG** | Upload PDFs → hybrid vector + knowledge-graph retrieval → cited Q&A |
| 2 | **ATS Resume Analyzer** | 6-agent parallel analysis → weighted scoring → improvement suggestions |
| 3 | **Research Assistant** | 7-stage HTN workflow → web search → verification → contradiction detection |
| 4 | **Text-to-SQL** | Natural language → SQL with triple-layer safety → NL result summaries |
| 5 | **Knowledge Graph Engine** | Entity extraction → LLM-based resolution → multi-document graph merging |

> **Beyond the paper.** This implementation exceeds the original research paper's claims with real verification pipelines, entity resolution, Redis caching, production hardening, and comprehensive monitoring.

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                     React Frontend (Vite + TypeScript)              │
│   Dashboard  │  PDF Chat  │  ATS  │  Research  │  SQL  │  KG View  │
└──────────────────────────┬──────────────────────────────────────────┘
                           │ HTTPS + JWT
┌──────────────────────────▼──────────────────────────────────────────┐
│                  API Gateway (FastAPI v2.0)                         │
│   🔒 JWT Auth  │  ⏱️ Rate Limiting  │  🆔 Correlation IDs  │  📊 Logs │
└───┬─────────┬─────────┬─────────┬─────────┬────────────────────────┘
    │         │         │         │         │
    ▼         ▼         ▼         ▼         ▼
 PDF-RAG    ATS       Research   SQL     KG Engine
 Service   Agent      Service  Service  (standalone)
  :8001   Service      :8003   :8004    (in RAG svc)
           :8002
    │         │         │         │         │
    ▼         │         ▼         ▼         ▼
 ┌──────┐    │    ┌──────────┐  │     ┌──────┐
 │Qdrant│    │    │Tavily /  │  │     │Neo4j │
 │vector│    │    │Serper API│  │     │graph │
 └──────┘    │    └──────────┘  │     └──────┘
    │         │         │         │         │
    └─────────┴─────────┴─────────┴─────────┘
                        │
           ┌────────────┼────────────┐
           ▼            ▼            ▼
      PostgreSQL      Redis       Ollama
      (metadata)     (cache)      (LLM)
```

---

## 🚀 Quick Start

### Prerequisites

- **Docker** & Docker Compose v2
- **Node.js** 18+ (for frontend development)
- **8 GB+ RAM** (Ollama + databases)

### 1. Clone & Configure

```bash
git clone https://github.com/your-org/GenAI-Platform.git
cd GenAI-Platform
cp .env.example .env
# Edit .env — set JWT_SECRET and optional API keys
```

### 2. Start All Services

```bash
docker-compose up -d
```

### 3. Verify Health

```bash
curl http://localhost:8000/health
# { "status": "ok", "services": { "gateway": "ok", "rag": "ok", ... } }
```

### 4. Start Frontend

```bash
npm install
npm run dev
# → http://localhost:5173
```

### 5. Pull LLM Models

```bash
docker exec -it ollama ollama pull llama3
docker exec -it ollama ollama pull nomic-embed-text
```

---

## 📚 Documentation

| Document | Description |
|----------|-------------|
| **[Architecture](docs/architecture.md)** | Service topology, data flows, technology stack |
| **[Module 1: PDF + GraphRAG](docs/module-1-pdf-graphrag.md)** | Ingestion pipeline, hybrid retrieval, Redis caching |
| **[Module 2: ATS Analyzer](docs/module-2-ats-analyzer.md)** | 6-agent architecture, parallel execution, scoring |
| **[Module 3: Research Assistant](docs/module-3-research-assistant.md)** | HTN pipeline, verification, contradiction detection |
| **[Module 4: Text-to-SQL](docs/module-4-text-to-sql.md)** | Triple-layer safety, query explanation, NL summaries |
| **[Module 5: Knowledge Graph](docs/module-5-knowledge-graph.md)** | Entity resolution, multi-doc merging, graph queries |
| **[API Reference](docs/api-reference.md)** | All endpoints with request/response schemas |
| **[Deployment Guide](docs/deployment.md)** | Docker, Kubernetes, monitoring setup |
| **[Configuration](docs/configuration.md)** | Environment variables, tuning parameters |

---

## 🔑 Key Features

### 🔍 Hybrid GraphRAG Retrieval
- Vector similarity (Qdrant) + Knowledge graph traversal (Neo4j)
- Redis embedding cache with 1-hour TTL (60–80% fewer LLM calls)
- Streaming responses via Server-Sent Events

### 🤖 Multi-Agent ATS Analysis
- 6 specialized agents with Coordinator-Worker pattern
- Parallel execution via `asyncio.gather()` (~75% faster)
- Programmatic 40/30/30 weighted scoring

### 📊 Verified Research Reports
- 7-stage HTN workflow: Plan → Search → Filter → Summarize → Verify → Cite → Executive Summary
- LLM cross-referencing with per-source confidence scores
- Automatic contradiction detection across sources
- 3 depth modes: `quick`, `standard`, `deep`

### 🛡️ Safe Text-to-SQL
- **Layer 1:** AST parse via `sqlglot` (SELECT-only enforcement)
- **Layer 2:** Regex blocklist (blocks INSERT, UPDATE, DELETE, DROP, etc.)
- **Layer 3:** LIMIT 1000 injection
- Plain-English query explanation + NL result summarization

### 🕸️ Standalone Knowledge Graph
- Entity extraction from arbitrary text (not just PDFs)
- LLM-based entity resolution ("Google" = "Alphabet" = "Google Inc.")
- Multi-document graph merging with cross-document entity linking
- Confidence-scored relationships

### 🏭 Production-Ready
- JWT authentication with bcrypt hashing
- Rate limiting (slowapi): 120/min global, 10/min registration
- Correlation ID middleware for distributed tracing
- Structured JSON logging with request metrics
- Kubernetes manifests with health probes and resource limits
- Prometheus + Grafana monitoring stack

---

## 🛠️ Technology Stack

| Layer | Technology | Version |
|-------|-----------|---------|
| **Frontend** | React + TypeScript + Vite | React 18 |
| **Gateway** | FastAPI + slowapi + python-jose | FastAPI 0.109 |
| **Services** | FastAPI + LiteLLM + httpx | Python 3.11+ |
| **Vector DB** | Qdrant | Latest |
| **Graph DB** | Neo4j Community | 5.x |
| **RDBMS** | PostgreSQL | 15 |
| **Cache** | Redis | 7 |
| **LLM Runtime** | Ollama (via LiteLLM abstraction) | Latest |
| **NL Search** | Tavily / Serper | API |
| **Orchestration** | Docker Compose / Kubernetes | v2 / 1.28+ |
| **Monitoring** | Prometheus + Grafana | Latest |

---

## 📁 Project Structure

```
GenAI-Platform/
├── services/
│   ├── api-gateway/          # Central proxy, auth, rate limiting
│   ├── pdf-rag-service/      # PDF ingestion, hybrid retrieval, KG engine
│   ├── ats-agent-service/    # 6-agent resume analyzer
│   ├── research-service/     # HTN research with verification
│   ├── sql-service/          # Text-to-SQL with safety layers
│   └── shared/               # Config, models, LLM provider, init SQL
├── src/                      # React frontend
├── docs/                     # Comprehensive documentation (10 guides)
├── k8s/                      # Kubernetes manifests
├── monitoring/               # Prometheus + Grafana configs
├── docker-compose.yml        # Local development orchestration
└── .env.example              # Configuration template
```

---

## 📄 License

MIT License — see [LICENSE](LICENSE) for details.
