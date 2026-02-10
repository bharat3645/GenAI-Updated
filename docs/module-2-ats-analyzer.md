# Module 2: ATS Resume Analyzer

## Overview

A **6-agent multi-agent system** that provides comprehensive resume analysis with parallel execution. The system uses a Coordinator-Worker pattern where a planning agent decomposes the task, 4 analysis agents run concurrently, and an Improvement agent generates actionable suggestions.

## Agent Architecture

```
                    ┌──────────────────┐
                    │  Coordinator     │
                    │  Agent           │
                    │  (plans strategy)│
                    └────────┬─────────┘
                             │
            ┌────────┬───────┼────────┬──────────┐
            ▼        ▼       ▼        ▼          │
       ┌────────┐┌────────┐┌────────┐┌──────────┐│
       │Keyword ││Format  ││Content ││Job Match ││
       │Agent   ││Agent   ││Agent   ││Agent     ││
       │        ││        ││        ││          ││
       └────┬───┘└───┬────┘└───┬────┘└────┬─────┘│
            │        │         │          │      │
            └────────┴─────────┴──────────┘      │
                        │                         │
                        ▼                         │
                 ┌──────────────┐                 │
                 │ Improvement  │◀────────────────┘
                 │ Agent        │
                 │ (suggestions)│
                 └──────────────┘
```

## Scoring System

Programmatic weighted scoring (not LLM-generated):

| Component | Weight | Measures |
|-----------|--------|----------|
| Keyword Match | 40% | ATS keyword optimization |
| Formatting | 30% | Structure, readability, length |
| Content Quality | 30% | Impact, quantification, relevance |

## Parallel Execution

All 4 analysis agents run simultaneously via `asyncio.gather()`, reducing total analysis time by ~75% compared to sequential execution.

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/analyze` | Full resume analysis (blocking) |
| POST | `/analyze/stream` | Streaming analysis (SSE) |
| GET | `/report/{task_id}` | Retrieve completed report |

## Request Schema

```json
{
  "resume_text": "Full resume content...",
  "job_description": "Optional job description for matching..."
}
```

Response includes: keyword analysis, format analysis, content analysis, job match score, improvement suggestions with specific rewrites, and overall weighted score.
