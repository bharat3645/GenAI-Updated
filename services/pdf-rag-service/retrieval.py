"""
Hybrid Retrieval — Vector Search + Graph Traversal.

Vector Path:  Query Qdrant for top-K chunks by cosine similarity (Redis-cached embeddings)
Graph Path:   Extract entities from query → 2-hop subgraph from Neo4j
Synthesis:    Merge both contexts → LLM generates final answer
"""

from __future__ import annotations

import hashlib
import json
import logging
from typing import Any, AsyncIterator

import redis.asyncio as aioredis

from neo4j import AsyncGraphDatabase
from qdrant_client import AsyncQdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue

from shared.config import Settings
from shared.llm_provider import LLMProvider
from shared.models import (
    QueryResponse, ChunkSource, GraphTriple,
    GraphResponse, GraphNode, GraphEdge,
)

logger = logging.getLogger(__name__)

SYNTHESIS_SYSTEM_PROMPT = """You are an intelligent document assistant. Answer the user's question 
using ONLY the provided context. If the context doesn't contain enough information, say so.

Cite specific parts of the context in your answer. Be precise and thorough."""

SYNTHESIS_PROMPT = """## Vector Search Context (most semantically similar chunks):
{vector_context}

## Knowledge Graph Context (related entities and relationships):
{graph_context}

## User Question:
{query}

Provide a comprehensive answer based on the above context."""

ENTITY_EXTRACT_PROMPT = """Extract the key entities (people, organizations, locations, technologies, concepts) 
from this query. Return a JSON array of strings.

Query: {query}

Return ONLY a JSON array like: ["entity1", "entity2"]"""


class HybridRetriever:
    """Combines vector search and graph traversal for retrieval.

    Features Redis-based embedding cache to avoid redundant LLM calls.
    """

    def __init__(self, settings: Settings, redis_client: aioredis.Redis | None = None):
        self._settings = settings
        self._llm = LLMProvider()
        self._qdrant: AsyncQdrantClient | None = None
        self._neo4j_driver = None
        self._redis = redis_client

    async def initialize(self):
        self._qdrant = AsyncQdrantClient(
            host=self._settings.qdrant.host,
            port=self._settings.qdrant.port,
        )
        self._neo4j_driver = AsyncGraphDatabase.driver(
            self._settings.neo4j.uri,
            auth=(self._settings.neo4j.user, self._settings.neo4j.password),
        )
        # Connect Redis if not injected
        if self._redis is None:
            self._redis = aioredis.from_url(self._settings.redis.url, decode_responses=True)

    async def close(self):
        if self._qdrant:
            await self._qdrant.close()
        if self._neo4j_driver:
            await self._neo4j_driver.close()

    # ── Public API ──────────────────────────────────────────────

    async def query(
        self,
        query: str,
        document_ids: list[str],
        top_k: int = 5,
        use_graph: bool = True,
    ) -> dict[str, Any]:
        """Full hybrid retrieval + synthesis."""
        # Vector path
        vector_results = await self._vector_search(query, document_ids, top_k)

        # Graph path
        graph_triples = []
        if use_graph:
            graph_triples = await self._graph_search(query, document_ids)

        # Synthesize
        answer = await self._synthesize(query, vector_results, graph_triples)

        return {
            "answer": answer,
            "sources": [
                {
                    "chunk_id": r["id"],
                    "content": r["content"][:200],
                    "score": r["score"],
                    "document_id": r["document_id"],
                }
                for r in vector_results
            ],
            "graph_context": [
                {"subject": t["subject"], "predicate": t["predicate"], "obj": t["object"]}
                for t in graph_triples
            ],
        }

    async def query_stream(
        self,
        query: str,
        document_ids: list[str],
        top_k: int = 5,
        use_graph: bool = True,
    ) -> AsyncIterator[str]:
        """Streaming hybrid retrieval — yields tokens."""
        vector_results = await self._vector_search(query, document_ids, top_k)
        graph_triples = []
        if use_graph:
            graph_triples = await self._graph_search(query, document_ids)

        prompt = self._build_synthesis_prompt(query, vector_results, graph_triples)

        async for token in self._llm.complete_stream(
            prompt, system=SYNTHESIS_SYSTEM_PROMPT
        ):
            yield token

    async def get_document_graph(self, doc_id: str) -> dict[str, Any]:
        """Return the full knowledge graph for a document (for visualization)."""
        nodes = []
        edges = []

        async with self._neo4j_driver.session() as session:
            # Get all entities for this document
            result = await session.run(
                """
                MATCH (e:Entity {doc_id: $doc_id})
                RETURN e.name AS name, e.type AS type, e.description AS description, 
                       elementId(e) AS id
                """,
                doc_id=doc_id,
            )
            entity_map = {}
            async for record in result:
                node_id = record["id"]
                entity_map[record["name"]] = node_id
                nodes.append({
                    "id": node_id,
                    "label": record["name"],
                    "type": record["type"] or "Concept",
                    "properties": {"description": record["description"] or ""},
                })

            # Get all relationships
            result = await session.run(
                """
                MATCH (a:Entity {doc_id: $doc_id})-[r:RELATES_TO]->(b:Entity {doc_id: $doc_id})
                RETURN a.name AS source, b.name AS target, r.type AS type, 
                       r.description AS description
                """,
                doc_id=doc_id,
            )
            async for record in result:
                source_id = entity_map.get(record["source"], record["source"])
                target_id = entity_map.get(record["target"], record["target"])
                edges.append({
                    "source": source_id,
                    "target": target_id,
                    "label": record["type"] or "RELATED_TO",
                })

        return {"nodes": nodes, "edges": edges}

    # ── Vector Search ───────────────────────────────────────────

    async def _vector_search(
        self, query: str, document_ids: list[str], top_k: int
    ) -> list[dict[str, Any]]:
        """Search Qdrant for top-K similar chunks. Uses Redis embedding cache."""
        # Cache key based on query content hash
        cache_key = f"emb:{hashlib.sha256(query.encode()).hexdigest()[:16]}"
        cached = None
        if self._redis:
            try:
                cached = await self._redis.get(cache_key)
            except Exception:
                pass

        if cached:
            query_embedding = json.loads(cached)
            logger.debug(f"Embedding cache HIT for query: {query[:50]}")
        else:
            query_embedding = await self._llm.embed_single(query)
            # Cache for 1 hour
            if self._redis:
                try:
                    await self._redis.setex(cache_key, 3600, json.dumps(query_embedding))
                    logger.debug(f"Embedding cached for query: {query[:50]}")
                except Exception:
                    pass

        # Build filter for specific documents
        search_filter = None
        if document_ids:
            search_filter = Filter(
                should=[
                    FieldCondition(key="document_id", match=MatchValue(value=did))
                    for did in document_ids
                ]
            )

        results = await self._qdrant.search(
            collection_name=self._settings.qdrant.collection,
            query_vector=query_embedding,
            query_filter=search_filter,
            limit=top_k,
        )

        return [
            {
                "id": str(hit.id),
                "content": hit.payload.get("content", ""),
                "score": hit.score,
                "document_id": hit.payload.get("document_id", ""),
                "chunk_index": hit.payload.get("chunk_index", 0),
            }
            for hit in results
        ]

    # ── Graph Search ────────────────────────────────────────────

    async def _graph_search(
        self, query: str, document_ids: list[str]
    ) -> list[dict[str, str]]:
        """Extract entities from query, then 2-hop traversal in Neo4j."""
        # Use LLM to extract entities from the query
        try:
            entities = await self._llm.complete_json(
                ENTITY_EXTRACT_PROMPT.format(query=query)
            )
            if not isinstance(entities, list):
                entities = []
        except Exception:
            logger.warning("Entity extraction from query failed, skipping graph search")
            return []

        if not entities:
            return []

        triples = []
        async with self._neo4j_driver.session() as session:
            for entity_name in entities[:5]:  # Limit to 5 entities
                # 2-hop neighborhood
                result = await session.run(
                    """
                    MATCH (e:Entity)
                    WHERE toLower(e.name) CONTAINS toLower($name)
                    MATCH path = (e)-[*1..2]-(connected)
                    WHERE connected:Entity
                    UNWIND relationships(path) AS r
                    WITH startNode(r) AS src, endNode(r) AS tgt, r
                    RETURN DISTINCT src.name AS subject, r.type AS predicate, tgt.name AS object
                    LIMIT 20
                    """,
                    name=entity_name,
                )
                async for record in result:
                    triples.append({
                        "subject": record["subject"],
                        "predicate": record["predicate"] or "RELATED_TO",
                        "object": record["object"],
                    })

        return triples

    # ── Synthesis ───────────────────────────────────────────────

    def _build_synthesis_prompt(
        self,
        query: str,
        vector_results: list[dict],
        graph_triples: list[dict],
    ) -> str:
        vector_ctx = "\n\n".join(
            f"[Chunk {i+1} | Score: {r['score']:.3f}]\n{r['content']}"
            for i, r in enumerate(vector_results)
        )
        graph_ctx = "\n".join(
            f"- {t['subject']} → {t['predicate']} → {t['object']}"
            for t in graph_triples
        ) or "No graph context available."

        return SYNTHESIS_PROMPT.format(
            vector_context=vector_ctx,
            graph_context=graph_ctx,
            query=query,
        )

    async def _synthesize(
        self,
        query: str,
        vector_results: list[dict],
        graph_triples: list[dict],
    ) -> str:
        prompt = self._build_synthesis_prompt(query, vector_results, graph_triples)
        return await self._llm.complete(prompt, system=SYNTHESIS_SYSTEM_PROMPT)
