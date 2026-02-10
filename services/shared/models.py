"""Shared Pydantic models used across services."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


# ── Common ──────────────────────────────────────────────────────

class HealthResponse(BaseModel):
    status: str = "ok"
    service: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class ErrorResponse(BaseModel):
    error: str
    detail: str | None = None


# ── PDF RAG Models ──────────────────────────────────────────────

class IngestRequest(BaseModel):
    """Sent when PDFs are uploaded for processing."""
    document_ids: list[str] = Field(default_factory=list)
    filenames: list[str] = Field(default_factory=list)


class IngestResponse(BaseModel):
    document_id: str
    filename: str
    chunk_count: int
    entity_count: int
    relationship_count: int


class QueryRequest(BaseModel):
    query: str
    document_ids: list[str] = Field(default_factory=list)
    top_k: int = 5
    use_graph: bool = True


class QueryResponse(BaseModel):
    answer: str
    sources: list[ChunkSource] = Field(default_factory=list)
    graph_context: list[GraphTriple] = Field(default_factory=list)


class ChunkSource(BaseModel):
    chunk_id: str
    content: str
    score: float
    document_id: str


class GraphTriple(BaseModel):
    subject: str
    predicate: str
    obj: str  # 'object' is a Python builtin


class GraphNode(BaseModel):
    id: str
    label: str
    type: str
    properties: dict[str, Any] = Field(default_factory=dict)


class GraphEdge(BaseModel):
    source: str
    target: str
    label: str
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)


class GraphResponse(BaseModel):
    nodes: list[GraphNode] = Field(default_factory=list)
    edges: list[GraphEdge] = Field(default_factory=list)


# ── Entity Extraction ───────────────────────────────────────────

class EntityType(str, Enum):
    PERSON = "Person"
    ORGANIZATION = "Organization"
    LOCATION = "Location"
    TECHNOLOGY = "Technology"
    CONCEPT = "Concept"


class ExtractedEntity(BaseModel):
    name: str
    type: EntityType
    description: str = ""


class ExtractedRelationship(BaseModel):
    source: str
    target: str
    relationship: str
    description: str = ""
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)


class ExtractionResult(BaseModel):
    entities: list[ExtractedEntity] = Field(default_factory=list)
    relationships: list[ExtractedRelationship] = Field(default_factory=list)


# ── ATS Models ──────────────────────────────────────────────────

class ATSAnalyzeRequest(BaseModel):
    resume_text: str
    job_description: str = ""


class ATSScoreBreakdown(BaseModel):
    keyword_relevance: float = Field(ge=0, le=100)
    formatting_compliance: float = Field(ge=0, le=100)
    content_quality: float = Field(ge=0, le=100)
    job_match: float = Field(default=0, ge=0, le=100)
    weighted_score: float = Field(ge=0, le=100)


class ImprovementSuggestion(BaseModel):
    """A specific rewrite suggestion for a weak resume bullet point."""
    original: str
    suggested_rewrite: str
    reason: str = ""


class ATSReport(BaseModel):
    score: int = Field(ge=0, le=100)
    breakdown: ATSScoreBreakdown
    keywords_found: list[str] = Field(default_factory=list)
    keywords_missing: list[str] = Field(default_factory=list)
    formatting_issues: list[str] = Field(default_factory=list)
    content_suggestions: list[str] = Field(default_factory=list)
    action_verbs_found: list[str] = Field(default_factory=list)
    quantifiable_metrics: list[str] = Field(default_factory=list)
    job_match_details: list[str] = Field(default_factory=list)
    improvement_suggestions: list[ImprovementSuggestion] = Field(default_factory=list)
    summary: str = ""


# ── Research Models ─────────────────────────────────────────────

class ResearchStatus(str, Enum):
    PLANNING = "planning"
    SEARCHING = "searching"
    FILTERING = "filtering"
    SUMMARIZING = "summarizing"
    VERIFYING = "verifying"
    SYNTHESIZING = "synthesizing"
    CITING = "citing"
    COMPLETED = "completed"
    FAILED = "failed"


class ResearchRequest(BaseModel):
    query: str
    depth: str = "standard"  # "quick" | "standard" | "deep"


class ResearchSource(BaseModel):
    id: str
    title: str
    url: str
    snippet: str
    verified: bool = False
    confidence_score: float = Field(default=0.0, ge=0.0, le=1.0)


class ResearchReport(BaseModel):
    task_id: str
    query: str
    status: ResearchStatus
    report: str = ""
    executive_summary: str = ""
    sources: list[ResearchSource] = Field(default_factory=list)
    contradictions: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)


# ── SQL Models ──────────────────────────────────────────────────

class SQLGenerateRequest(BaseModel):
    query: str
    schema_context: str = ""  # optional override


class SQLGenerateResponse(BaseModel):
    natural_language: str
    generated_sql: str
    explanation: str = ""  # Plain-English explanation of the SQL
    safe: bool
    safety_details: dict[str, Any] = Field(default_factory=dict)


class SQLExecuteRequest(BaseModel):
    sql: str


class SQLExecuteResponse(BaseModel):
    columns: list[str] = Field(default_factory=list)
    rows: list[list[Any]] = Field(default_factory=list)
    row_count: int = 0
    truncated: bool = False
    result_summary: str = ""  # NL summary of query results


class SchemaTable(BaseModel):
    name: str
    columns: list[SchemaColumn] = Field(default_factory=list)
    foreign_keys: list[str] = Field(default_factory=list)


class SchemaColumn(BaseModel):
    name: str
    type: str
    nullable: bool = True
    is_primary: bool = False


class SchemaResponse(BaseModel):
    tables: list[SchemaTable] = Field(default_factory=list)


# ── Knowledge Graph Models ──────────────────────────────────────

class KGExtractRequest(BaseModel):
    """Extract a knowledge graph from raw text."""
    text: str
    source_label: str = "user_input"


class KGMergeRequest(BaseModel):
    """Merge knowledge graphs across multiple documents."""
    document_ids: list[str]
    resolve_entities: bool = True


class KGStatsResponse(BaseModel):
    node_count: int = 0
    edge_count: int = 0
    entity_types: dict[str, int] = Field(default_factory=dict)
    relationship_types: dict[str, int] = Field(default_factory=dict)


# Fix forward references
QueryResponse.model_rebuild()
