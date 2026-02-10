# Module 3: Autonomous Research Assistant

## Overview

A **7-stage Hierarchical Task Network (HTN)** workflow that autonomously researches any topic using web search, cross-references claims across sources, detects contradictions, and produces cited research reports with executive summaries.

## HTN Pipeline

```
Query ──▶ Planning ──▶ Searching ──▶ Filtering ──▶ Summarizing
                                                       │
Executive Summary ◀── Citing ◀── Synthesizing ◀── Verifying
```

## Depth Modes

| Mode | Sub-topics | Results/Topic | Use Case |
|------|-----------|---------------|----------|
| `quick` | 3 | 3 | Fast overview |
| `standard` | 5 | 5 | Balanced depth (default) |
| `deep` | 8 | 8 | Thorough investigation |

## Key Features

### Real Verification (Stage 5)
- LLM cross-references claims across all sources
- Computes per-source **confidence scores** (0.0 – 1.0)
- Sources below 0.3 confidence are excluded from synthesis

### Contradiction Detection
- Identifies conflicting claims between sources
- Contradictions are explicitly addressed in the final report
- Returned as a separate array in the API response

### Executive Summary
- Auto-generated 3-sentence summary after synthesis
- Includes key finding, main evidence, and primary recommendation

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/research` | Start research (blocking, returns full report) |
| GET | `/status/{id}/stream` | SSE stream with stage-by-stage progress |
| GET | `/report/{id}` | Retrieve completed report |

## Search Provider Chain

1. **Tavily** (preferred) → 2. **Serper** (fallback) → 3. **LLM** (hypothetical results)
