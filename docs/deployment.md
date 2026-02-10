# Deployment Guide

## Prerequisites

- Docker & Docker Compose v2
- Node.js 18+ (frontend dev only)
- 8GB+ RAM (for Ollama + databases)

## Quick Start (Docker Compose)

```bash
# 1. Clone and configure
git clone <repo-url>
cd GenAI-Platform
cp .env.example .env
# Edit .env with your credentials

# 2. Start all services
docker-compose up -d

# 3. Verify health
curl http://localhost:8000/health

# 4. Start frontend (dev mode)
npm install
npm run dev
```

## Production (Kubernetes)

### Deploy

```bash
# 1. Apply manifests in order
kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/config.yaml
kubectl apply -f k8s/databases.yaml
kubectl apply -f k8s/services.yaml

# 2. Wait for pods
kubectl -n genai-platform get pods -w

# 3. Verify
kubectl -n genai-platform exec deployment/api-gateway -- curl -s localhost:8000/health
```

### Scaling

```bash
# Scale application services (stateless)
kubectl -n genai-platform scale deployment/api-gateway --replicas=3
kubectl -n genai-platform scale deployment/pdf-rag-service --replicas=3

# Database StatefulSets should NOT be scaled without proper clustering setup
```

## Monitoring Stack

```bash
# Start Prometheus + Grafana + exporters
cd monitoring
docker-compose -f docker-compose.monitoring.yml up -d

# Access
# Prometheus: http://localhost:9090
# Grafana:    http://localhost:3001 (admin/genai_grafana_2024)
```

## Build Images

```bash
# Build all services
docker-compose build

# Or build individually
docker build -t genai-platform/api-gateway ./services/api-gateway
docker build -t genai-platform/pdf-rag-service ./services/pdf-rag-service
docker build -t genai-platform/ats-agent-service ./services/ats-agent-service
docker build -t genai-platform/research-service ./services/research-service
docker build -t genai-platform/sql-service ./services/sql-service
```

## Ollama Model Setup

```bash
# Pull required models (inside Ollama container or host)
ollama pull llama3
ollama pull nomic-embed-text
```

## Database Initialization

The `init_db.sql` script runs automatically on first PostgreSQL start (via Docker entrypoint). It creates all necessary tables:
- `users` — Authentication
- `pdf_documents` — Document metadata
- `research_tasks` — Research task tracking
- `sql_queries` — Query audit log
