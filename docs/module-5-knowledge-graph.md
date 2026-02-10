# Module 5: Knowledge Graph Engine

## Overview

A **standalone Knowledge Graph engine** (`kg_engine.py`) that extracts entities and relationships from arbitrary text (not just PDFs), performs LLM-based entity resolution, merges graphs across documents, and provides confidence-scored relationships.

## Capabilities

| Feature | Description |
|---------|-------------|
| Entity extraction | LLM extracts named entities (Person, Org, Location, Tech, Concept) |
| Relationship extraction | Identifies typed relationships with confidence scores |
| Entity resolution | LLM-based deduplication ("Google" = "Google Inc." = "Alphabet") |
| Multi-doc merging | Cross-document entity linking and graph unification |
| Neighborhood queries | Retrieve N-hop subgraph around any entity |
| Graph statistics | Entity/relationship counts by type |

## Architecture

```
                    ┌─────────────────┐
                    │   KG Engine     │
                    │  (kg_engine.py) │
                    └────────┬────────┘
                             │
        ┌────────────────────┼────────────────────┐
        ▼                    ▼                     ▼
  Extract & Store    Entity Resolution    Multi-Doc Merge
        │                    │                     │
        ▼                    ▼                     ▼
     Neo4j            Merge aliases        Cross-doc links
  (graph store)      in Neo4j graph       + resolution
```

## Entity Resolution Process

1. Fetch all entities from Neo4j (optionally filtered by document)
2. Group entities by type for efficient processing
3. LLM identifies aliases (e.g., "NYC" = "New York City")
4. Canonical name selected, alias nodes merged in Neo4j
5. All relationships redirected to canonical entity

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/kg/extract` | Extract KG from arbitrary text |
| POST | `/kg/merge` | Merge graphs across documents |
| GET | `/kg/entity/{name}` | Get entity neighborhood subgraph |
| GET | `/kg/stats` | Graph statistics (counts by type) |

## Integration

The KG Engine is embedded within the PDF-RAG service but is fully standalone — it can process any text input, not just PDF-extracted content. The `PDFIngestionPipeline` delegates all graph operations to the KG Engine via `extract_and_store()`.
