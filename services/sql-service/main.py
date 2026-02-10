"""
SQL Service — Text-to-SQL with Triple-Layer Safety.

Features:
  - Schema-aware SQL generation (introspects PostgreSQL information_schema)
  - Layer 1: AST parse via sqlglot (enforce SELECT-only)
  - Layer 2: Regex allowlist blocking DML/DDL
  - Layer 3: LIMIT 1000 enforcement
  - Query explanation in plain English
  - Natural-language result summarization
"""

from __future__ import annotations

import json
import logging
import os
import re
from contextlib import asynccontextmanager
from typing import Any

import asyncpg
from fastapi import FastAPI, HTTPException

import sys
sys.path.insert(0, os.path.dirname(__file__))
from shared.config import get_settings
from shared.llm_provider import LLMProvider
from shared.models import (
    HealthResponse,
    SQLGenerateRequest, SQLGenerateResponse,
    SQLExecuteRequest, SQLExecuteResponse,
    SchemaResponse, SchemaTable, SchemaColumn,
)

logger = logging.getLogger(__name__)
settings = get_settings()
llm = LLMProvider()
db_pool: asyncpg.Pool | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global db_pool
    db_pool = await asyncpg.create_pool(settings.postgres.dsn, min_size=2, max_size=10)
    yield
    await db_pool.close()


app = FastAPI(title="SQL Service", version="1.0.0", lifespan=lifespan)


@app.get("/health")
async def health():
    return HealthResponse(service="sql-service")


# ── Schema Serialization ───────────────────────────────────────

async def get_schema_context() -> str:
    """Introspect PostgreSQL information_schema and serialize for LLM prompt."""
    async with db_pool.acquire() as conn:
        # Get tables
        tables = await conn.fetch(
            """
            SELECT table_name FROM information_schema.tables
            WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
            ORDER BY table_name
            """
        )

        schema_parts = []
        for table in tables:
            table_name = table["table_name"]

            # Get columns
            columns = await conn.fetch(
                """
                SELECT column_name, data_type, is_nullable, column_default
                FROM information_schema.columns
                WHERE table_schema = 'public' AND table_name = $1
                ORDER BY ordinal_position
                """,
                table_name,
            )

            # Get primary keys
            pks = await conn.fetch(
                """
                SELECT kcu.column_name
                FROM information_schema.table_constraints tc
                JOIN information_schema.key_column_usage kcu
                    ON tc.constraint_name = kcu.constraint_name
                WHERE tc.table_schema = 'public'
                    AND tc.table_name = $1
                    AND tc.constraint_type = 'PRIMARY KEY'
                """,
                table_name,
            )
            pk_cols = {r["column_name"] for r in pks}

            # Get foreign keys
            fks = await conn.fetch(
                """
                SELECT
                    kcu.column_name,
                    ccu.table_name AS foreign_table,
                    ccu.column_name AS foreign_column
                FROM information_schema.table_constraints tc
                JOIN information_schema.key_column_usage kcu
                    ON tc.constraint_name = kcu.constraint_name
                JOIN information_schema.constraint_column_usage ccu
                    ON tc.constraint_name = ccu.constraint_name
                WHERE tc.table_schema = 'public'
                    AND tc.table_name = $1
                    AND tc.constraint_type = 'FOREIGN KEY'
                """,
                table_name,
            )

            col_strs = []
            for col in columns:
                pk = " [PK]" if col["column_name"] in pk_cols else ""
                nullable = "" if col["is_nullable"] == "YES" else " NOT NULL"
                col_strs.append(f"    {col['column_name']} {col['data_type']}{pk}{nullable}")

            fk_strs = [
                f"    FK: {fk['column_name']} → {fk['foreign_table']}.{fk['foreign_column']}"
                for fk in fks
            ]

            schema_parts.append(
                f"TABLE {table_name}:\n" + "\n".join(col_strs) +
                ("\n" + "\n".join(fk_strs) if fk_strs else "")
            )

        return "\n\n".join(schema_parts)


# ── Triple-Layer Safety ────────────────────────────────────────

BLOCKED_PATTERNS = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|TRUNCATE|CREATE|GRANT|REVOKE|EXEC|EXECUTE|MERGE)\b",
    re.IGNORECASE,
)


def validate_sql_safety(sql: str) -> dict[str, Any]:
    """
    Triple-layer SQL safety validation:
      Layer 1: AST parse (sqlglot) — must be SELECT
      Layer 2: Regex blocklist — no DML/DDL keywords
      Layer 3: LIMIT enforcement — must have LIMIT ≤ 1000
    """
    result = {"safe": True, "layers": {}, "modified_sql": sql}

    # ── Layer 1: AST Parse ──────────────────────────────────
    try:
        import sqlglot
        parsed = sqlglot.parse(sql)
        if not parsed:
            result["safe"] = False
            result["layers"]["ast"] = {"passed": False, "reason": "Failed to parse SQL"}
            return result

        for statement in parsed:
            if statement is None:
                continue
            stmt_type = type(statement).__name__
            if stmt_type != "Select":
                result["safe"] = False
                result["layers"]["ast"] = {
                    "passed": False,
                    "reason": f"Only SELECT statements allowed, got: {stmt_type}",
                }
                return result

        result["layers"]["ast"] = {"passed": True}
    except Exception as e:
        result["safe"] = False
        result["layers"]["ast"] = {"passed": False, "reason": f"Parse error: {str(e)}"}
        return result

    # ── Layer 2: Regex Blocklist ────────────────────────────
    match = BLOCKED_PATTERNS.search(sql)
    if match:
        result["safe"] = False
        result["layers"]["regex"] = {
            "passed": False,
            "reason": f"Blocked keyword found: {match.group()}",
        }
        return result
    result["layers"]["regex"] = {"passed": True}

    # ── Layer 3: LIMIT Enforcement ──────────────────────────
    has_limit = re.search(r"\bLIMIT\s+(\d+)\b", sql, re.IGNORECASE)
    if has_limit:
        limit_val = int(has_limit.group(1))
        if limit_val > 1000:
            # Replace with LIMIT 1000
            result["modified_sql"] = re.sub(
                r"\bLIMIT\s+\d+\b", "LIMIT 1000", sql, flags=re.IGNORECASE
            )
            result["layers"]["limit"] = {"passed": True, "note": "Limit capped to 1000"}
        else:
            result["layers"]["limit"] = {"passed": True}
    else:
        result["modified_sql"] = sql.rstrip().rstrip(";") + " LIMIT 1000"
        result["layers"]["limit"] = {"passed": True, "note": "LIMIT 1000 injected"}

    return result


# ── SQL Generation ──────────────────────────────────────────────

SQL_GEN_PROMPT = """You are a PostgreSQL expert. Generate a SQL query for the user's question.

DATABASE SCHEMA:
{schema}

RULES:
1. Only generate SELECT queries
2. Always include a LIMIT clause (max 1000)
3. Use proper PostgreSQL syntax
4. Use table aliases for readability
5. Only reference tables and columns that exist in the schema above

USER QUESTION:
{query}

Return ONLY the SQL query, no explanation, no markdown."""


@app.post("/generate")
async def generate_sql(req: SQLGenerateRequest):
    """Generate SQL from natural language with safety validation and explanation."""
    # Get schema context
    schema = req.schema_context or await get_schema_context()

    # Generate SQL via LLM
    prompt = SQL_GEN_PROMPT.format(schema=schema, query=req.query)
    generated = await llm.complete(prompt, temperature=0.1)

    # Clean up markdown fences if present
    generated = generated.strip()
    if generated.startswith("```"):
        lines = generated.split("\n")
        generated = "\n".join(lines[1:-1] if len(lines) > 2 else lines)
    generated = generated.strip().rstrip(";") + ";"

    # Validate safety
    safety = validate_sql_safety(generated)

    # Generate plain-English explanation of the SQL
    explanation = await llm.complete(
        f"Explain this SQL query in simple, non-technical language. "
        f"Describe what data it retrieves and any filters or sorting applied.\n\n"
        f"SQL: {safety['modified_sql']}\n\n"
        f"Original question: {req.query}",
        max_tokens=200,
    )

    return SQLGenerateResponse(
        natural_language=req.query,
        generated_sql=safety["modified_sql"],
        safe=safety["safe"],
        safety_details=safety["layers"],
        explanation=explanation.strip(),
    )


@app.post("/execute")
async def execute_sql(req: SQLExecuteRequest):
    """Execute a validated SQL query."""
    # Re-validate before execution
    safety = validate_sql_safety(req.sql)
    if not safety["safe"]:
        raise HTTPException(
            status_code=400,
            detail=f"Query failed safety validation: {json.dumps(safety['layers'])}",
        )

    try:
        async with db_pool.acquire() as conn:
            # Use a read-only transaction for extra safety
            async with conn.transaction(readonly=True):
                rows = await conn.fetch(safety["modified_sql"])

            if not rows:
                return SQLExecuteResponse(columns=[], rows=[], row_count=0, result_summary="No results found.")

            columns = list(rows[0].keys())
            result_rows = [[_serialize_value(row[col]) for col in columns] for row in rows]

            # Generate NL summary of the results
            preview = json.dumps(
                [dict(zip(columns, row)) for row in result_rows[:5]], indent=2, default=str
            )
            summary = await llm.complete(
                f"Summarize these query results in 2-3 sentences for a non-technical user. "
                f"Mention key numbers and patterns.\n\n"
                f"Query: {req.sql}\n"
                f"Columns: {columns}\n"
                f"Total rows: {len(result_rows)}\n"
                f"Sample data (first 5 rows):\n{preview}",
                max_tokens=200,
            )

            return SQLExecuteResponse(
                columns=columns,
                rows=result_rows,
                row_count=len(result_rows),
                truncated=len(result_rows) >= 1000,
                result_summary=summary.strip(),
            )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Query execution error: {str(e)}")


def _serialize_value(val: Any) -> Any:
    """Convert database values to JSON-serializable types."""
    if val is None:
        return None
    if isinstance(val, (int, float, str, bool)):
        return val
    return str(val)


@app.get("/schema")
async def get_schema():
    """Return the full database schema."""
    async with db_pool.acquire() as conn:
        tables_raw = await conn.fetch(
            "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public' AND table_type = 'BASE TABLE'"
        )

        tables = []
        for t in tables_raw:
            table_name = t["table_name"]
            cols = await conn.fetch(
                "SELECT column_name, data_type, is_nullable FROM information_schema.columns "
                "WHERE table_schema = 'public' AND table_name = $1 ORDER BY ordinal_position",
                table_name,
            )
            tables.append(SchemaTable(
                name=table_name,
                columns=[
                    SchemaColumn(
                        name=c["column_name"],
                        type=c["data_type"],
                        nullable=c["is_nullable"] == "YES",
                    )
                    for c in cols
                ],
            ))

        return SchemaResponse(tables=tables)
