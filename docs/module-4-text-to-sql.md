# Module 4: Text-to-SQL

## Overview

Converts natural language questions into safe, executable PostgreSQL queries with **triple-layer safety validation**, plain-English query explanations, and natural-language result summarization.

## Safety Architecture

```
Natural Language Question
        │
        ▼
   LLM Generation (schema-aware)
        │
        ▼
   ┌─────────────────────┐
   │ Layer 1: AST Parse  │  sqlglot — enforce SELECT only
   │ Layer 2: Regex      │  Block INSERT/UPDATE/DELETE/DROP/etc.
   │ Layer 3: LIMIT      │  Inject or cap at 1000 rows
   └─────────┬───────────┘
             │
             ▼
   Read-Only Transaction Execution
        │
        ▼
   NL Result Summary (LLM-generated)
```

## Features

| Feature | Description |
|---------|-------------|
| Schema introspection | Auto-reads `information_schema` for table/column/FK context |
| Query explanation | Plain-English explanation of what the SQL does |
| Result summarization | LLM summarizes query results for non-technical users |
| Safety validation | 3-layer pipeline: AST → regex → LIMIT enforcement |
| Read-only execution | All queries run inside `readonly=True` transactions |

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/generate` | NL → SQL with safety validation + explanation |
| POST | `/execute` | Execute validated SQL with NL summary |
| GET | `/schema` | Return full database schema |

## Generate Response

```json
{
  "natural_language": "Show me the top 10 users",
  "generated_sql": "SELECT * FROM users ORDER BY created_at DESC LIMIT 10;",
  "explanation": "This query retrieves the 10 most recently created user records...",
  "safe": true,
  "safety_details": {
    "ast": {"passed": true},
    "regex": {"passed": true},
    "limit": {"passed": true}
  }
}
