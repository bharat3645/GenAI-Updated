"""Centralized configuration from environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass, field


@dataclass(frozen=True)
class OllamaConfig:
    base_url: str = field(default_factory=lambda: os.getenv("OLLAMA_BASE_URL", "http://ollama:11434"))
    model: str = field(default_factory=lambda: os.getenv("OLLAMA_MODEL", "llama3"))
    embed_model: str = field(default_factory=lambda: os.getenv("OLLAMA_EMBED_MODEL", "nomic-embed-text"))


@dataclass(frozen=True)
class PostgresConfig:
    host: str = field(default_factory=lambda: os.getenv("POSTGRES_HOST", "postgres"))
    port: int = field(default_factory=lambda: int(os.getenv("POSTGRES_PORT", "5432")))
    user: str = field(default_factory=lambda: os.getenv("POSTGRES_USER", "genai"))
    password: str = field(default_factory=lambda: os.getenv("POSTGRES_PASSWORD", "genai_secret_2024"))
    db: str = field(default_factory=lambda: os.getenv("POSTGRES_DB", "genai_platform"))

    @property
    def dsn(self) -> str:
        return f"postgresql://{self.user}:{self.password}@{self.host}:{self.port}/{self.db}"

    @property
    def async_dsn(self) -> str:
        return f"postgresql+asyncpg://{self.user}:{self.password}@{self.host}:{self.port}/{self.db}"


@dataclass(frozen=True)
class RedisConfig:
    url: str = field(default_factory=lambda: os.getenv("REDIS_URL", "redis://redis:6379/0"))


@dataclass(frozen=True)
class QdrantConfig:
    host: str = field(default_factory=lambda: os.getenv("QDRANT_HOST", "qdrant"))
    port: int = field(default_factory=lambda: int(os.getenv("QDRANT_PORT", "6333")))
    collection: str = field(default_factory=lambda: os.getenv("QDRANT_COLLECTION", "pdf_chunks"))


@dataclass(frozen=True)
class Neo4jConfig:
    uri: str = field(default_factory=lambda: os.getenv("NEO4J_URI", "bolt://neo4j:7687"))
    user: str = field(default_factory=lambda: os.getenv("NEO4J_USER", "neo4j"))
    password: str = field(default_factory=lambda: os.getenv("NEO4J_PASSWORD", "neo4j_secret_2024"))


@dataclass(frozen=True)
class Settings:
    ollama: OllamaConfig = field(default_factory=OllamaConfig)
    postgres: PostgresConfig = field(default_factory=PostgresConfig)
    redis: RedisConfig = field(default_factory=RedisConfig)
    qdrant: QdrantConfig = field(default_factory=QdrantConfig)
    neo4j: Neo4jConfig = field(default_factory=Neo4jConfig)
    jwt_secret: str = field(default_factory=lambda: os.getenv("JWT_SECRET", "change-me"))


def get_settings() -> Settings:
    """Return a singleton-ish settings object."""
    return Settings()
