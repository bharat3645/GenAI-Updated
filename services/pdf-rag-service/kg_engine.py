"""
Knowledge Graph Engine — Standalone KG construction, entity resolution, and graph merging.

Features:
  - Extract entities and relationships from arbitrary text (not just PDFs)
  - LLM-based entity resolution (merge "Google" / "Google Inc." / "Alphabet")
  - Multi-document graph merging with cross-document entity linking
  - Relationship confidence scoring
  - Entity neighborhood retrieval
  - Graph statistics
"""

from __future__ import annotations

import json
import logging
from typing import Any

from neo4j import AsyncGraphDatabase

from shared.config import Settings
from shared.llm_provider import LLMProvider
from shared.models import (
    ExtractedEntity, ExtractedRelationship, ExtractionResult,
    GraphNode, GraphEdge, GraphResponse,
)

logger = logging.getLogger(__name__)

ENTITY_EXTRACTION_PROMPT = """Analyze the following text and extract all named entities and relationships.

TEXT:
{text}

Return a JSON object with this exact structure:
{{
  "entities": [
    {{"name": "entity name", "type": "Person|Organization|Location|Technology|Concept", "description": "brief description"}}
  ],
  "relationships": [
    {{"source": "entity1 name", "target": "entity2 name", "relationship": "WORKS_FOR|LOCATED_IN|USES|RELATED_TO|PART_OF|CREATED_BY|DEPENDS_ON", "description": "brief description", "confidence": 0.9}}
  ]
}}

Extract ALL entities and meaningful relationships. Be thorough. Assign a confidence score (0.0 to 1.0) to each relationship based on how explicitly it is stated in the text."""

ENTITY_RESOLUTION_PROMPT = """You are an entity resolution specialist. Examine these entity names from a knowledge graph and identify which ones refer to the same real-world entity.

ENTITIES:
{entities}

Group entities that refer to the same real-world thing. For example:
- "Google", "Google Inc.", "Alphabet" → same entity
- "ML", "Machine Learning" → same concept
- "NYC", "New York City", "New York" → same location

Return JSON:
{{
  "merge_groups": [
    {{"canonical": "the best/most complete name", "aliases": ["other", "names", "for", "same", "entity"]}}
  ]
}}

Only group entities you are confident refer to the same thing. When in doubt, keep them separate."""


class KGEngine:
    """Standalone Knowledge Graph Engine for entity extraction, resolution, and merging."""

    def __init__(self, settings: Settings):
        self._settings = settings
        self._llm = LLMProvider()
        self._neo4j_driver = None

    async def initialize(self):
        """Connect to Neo4j."""
        self._neo4j_driver = AsyncGraphDatabase.driver(
            self._settings.neo4j.uri,
            auth=(self._settings.neo4j.user, self._settings.neo4j.password),
        )

    async def close(self):
        if self._neo4j_driver:
            await self._neo4j_driver.close()

    # ── Core Extraction ────────────────────────────────────────

    async def extract_entities(self, text: str, source_label: str = "user_input") -> ExtractionResult:
        """Extract entities and relationships from arbitrary text.

        This is the standalone API — works with any text, not just PDF chunks.
        """
        all_entities: dict[str, ExtractedEntity] = {}
        all_relationships: list[ExtractedRelationship] = []

        # Split text into manageable segments (~2000 chars each)
        segments = self._split_text(text, max_chars=2000)

        for segment in segments:
            prompt = ENTITY_EXTRACTION_PROMPT.format(text=segment)
            try:
                result = await self._llm.complete_json(prompt)

                for ent in result.get("entities", []):
                    entity = ExtractedEntity(
                        name=ent["name"],
                        type=ent.get("type", "Concept"),
                        description=ent.get("description", ""),
                    )
                    all_entities[entity.name.lower()] = entity

                for rel in result.get("relationships", []):
                    confidence = 1.0
                    try:
                        confidence = max(0.0, min(1.0, float(rel.get("confidence", 1.0))))
                    except (TypeError, ValueError):
                        pass
                    all_relationships.append(
                        ExtractedRelationship(
                            source=rel["source"],
                            target=rel["target"],
                            relationship=rel.get("relationship", "RELATED_TO"),
                            description=rel.get("description", ""),
                            confidence=confidence,
                        )
                    )
            except Exception as e:
                logger.warning(f"Entity extraction failed for segment: {e}")
                continue

        return ExtractionResult(
            entities=list(all_entities.values()),
            relationships=all_relationships,
        )

    async def extract_and_store(
        self, text: str, doc_id: str, source_label: str = "user_input"
    ) -> ExtractionResult:
        """Extract entities from text and store in Neo4j."""
        extraction = await self.extract_entities(text, source_label)
        await self.store_graph(extraction, doc_id)
        return extraction

    # ── Entity Resolution ──────────────────────────────────────

    async def resolve_entities(self, doc_id: str | None = None) -> dict[str, Any]:
        """Identify and merge duplicate entities using LLM-based similarity.

        If doc_id is provided, only resolve within that document.
        Otherwise, resolve across the entire graph.
        """
        # Fetch all entity names from Neo4j
        async with self._neo4j_driver.session() as session:
            if doc_id:
                result = await session.run(
                    "MATCH (e:Entity {doc_id: $doc_id}) RETURN e.name AS name, e.type AS type",
                    doc_id=doc_id,
                )
            else:
                result = await session.run(
                    "MATCH (e:Entity) RETURN DISTINCT e.name AS name, e.type AS type"
                )
            records = [record async for record in result]

        if len(records) < 2:
            return {"merged_count": 0, "merge_groups": []}

        # Group by type for more efficient resolution
        type_groups: dict[str, list[str]] = {}
        for r in records:
            etype = r["type"] or "Concept"
            type_groups.setdefault(etype, []).append(r["name"])

        all_merge_groups = []
        total_merged = 0

        for etype, names in type_groups.items():
            if len(names) < 2:
                continue

            entities_json = json.dumps(
                [{"name": n, "type": etype} for n in names], indent=2
            )
            resolution_result = await self._llm.complete_json(
                ENTITY_RESOLUTION_PROMPT.format(entities=entities_json)
            )

            merge_groups = []
            if isinstance(resolution_result, dict):
                merge_groups = resolution_result.get("merge_groups", [])

            for group in merge_groups:
                canonical = group.get("canonical", "")
                aliases = group.get("aliases", [])
                if not canonical or not aliases:
                    continue

                # Merge in Neo4j: redirect all edges from aliases to canonical
                async with self._neo4j_driver.session() as session:
                    for alias in aliases:
                        # Transfer incoming relationships
                        await session.run(
                            """
                            MATCH (alias:Entity {name: $alias})-[r]-(other:Entity)
                            WHERE other.name <> $canonical
                            WITH alias, other, type(r) AS rtype, properties(r) AS rprops
                            MATCH (canon:Entity {name: $canonical})
                            MERGE (canon)-[:RELATES_TO {type: rprops.type, description: rprops.description}]->(other)
                            """,
                            alias=alias, canonical=canonical,
                        )
                        # Delete the alias node
                        await session.run(
                            "MATCH (alias:Entity {name: $alias}) DETACH DELETE alias",
                            alias=alias,
                        )
                        total_merged += 1

                all_merge_groups.append(group)

        return {"merged_count": total_merged, "merge_groups": all_merge_groups}

    # ── Multi-Document Merging ─────────────────────────────────

    async def merge_documents(self, document_ids: list[str], resolve: bool = True) -> dict[str, Any]:
        """Merge knowledge graphs across multiple documents.

        1. Find entities that appear in multiple documents
        2. Create cross-document edges
        3. Optionally run entity resolution
        """
        if len(document_ids) < 2:
            return {"cross_links_created": 0}

        cross_links_created = 0
        async with self._neo4j_driver.session() as session:
            # Find entities with the same name across different documents
            result = await session.run(
                """
                MATCH (e1:Entity), (e2:Entity)
                WHERE e1.name = e2.name
                  AND e1.doc_id <> e2.doc_id
                  AND e1.doc_id IN $doc_ids
                  AND e2.doc_id IN $doc_ids
                  AND id(e1) < id(e2)
                RETURN e1.name AS name, e1.doc_id AS doc1, e2.doc_id AS doc2
                """,
                doc_ids=document_ids,
            )
            matches = [record async for record in result]

            # Create cross-document links
            for match in matches:
                await session.run(
                    """
                    MATCH (e1:Entity {name: $name, doc_id: $doc1})
                    MATCH (e2:Entity {name: $name, doc_id: $doc2})
                    MERGE (e1)-[:CROSS_DOC_LINK]->(e2)
                    """,
                    name=match["name"], doc1=match["doc1"], doc2=match["doc2"],
                )
                cross_links_created += 1

        resolution_result = {}
        if resolve and cross_links_created > 0:
            resolution_result = await self.resolve_entities()

        return {
            "cross_links_created": cross_links_created,
            "resolution": resolution_result,
        }

    # ── Graph Storage ──────────────────────────────────────────

    async def store_graph(self, extraction: ExtractionResult, doc_id: str):
        """Store entities as nodes and relationships as edges in Neo4j."""
        async with self._neo4j_driver.session() as session:
            for entity in extraction.entities:
                await session.run(
                    """
                    MERGE (e:Entity {name: $name, doc_id: $doc_id})
                    SET e.type = $type, e.description = $description
                    """,
                    name=entity.name,
                    doc_id=doc_id,
                    type=entity.type.value if hasattr(entity.type, "value") else entity.type,
                    description=entity.description,
                )

            for rel in extraction.relationships:
                await session.run(
                    """
                    MATCH (a:Entity {name: $source, doc_id: $doc_id})
                    MATCH (b:Entity {name: $target, doc_id: $doc_id})
                    MERGE (a)-[r:RELATES_TO {type: $rel_type}]->(b)
                    SET r.description = $description, r.confidence = $confidence
                    """,
                    source=rel.source,
                    target=rel.target,
                    doc_id=doc_id,
                    rel_type=rel.relationship,
                    description=rel.description,
                    confidence=rel.confidence,
                )

    # ── Entity Neighborhood ────────────────────────────────────

    async def get_entity_neighborhood(
        self, entity_id: str, hops: int = 2
    ) -> GraphResponse:
        """Retrieve the subgraph around a specific entity."""
        async with self._neo4j_driver.session() as session:
            result = await session.run(
                f"""
                MATCH path = (start:Entity {{name: $name}})-[*1..{hops}]-(connected:Entity)
                WITH start, connected, relationships(path) AS rels
                RETURN start, connected, rels
                """,
                name=entity_id,
            )
            records = [record async for record in result]

        nodes_map: dict[str, GraphNode] = {}
        edges: list[GraphEdge] = []

        for record in records:
            start = record["start"]
            connected = record["connected"]

            for node_data in [start, connected]:
                name = node_data["name"]
                if name not in nodes_map:
                    nodes_map[name] = GraphNode(
                        id=name,
                        label=name,
                        type=node_data.get("type", "Concept"),
                        properties={
                            "description": node_data.get("description", ""),
                            "doc_id": node_data.get("doc_id", ""),
                        },
                    )

            for rel in record["rels"]:
                edges.append(GraphEdge(
                    source=start["name"],
                    target=connected["name"],
                    label=rel.get("type", "RELATES_TO"),
                    confidence=rel.get("confidence", 1.0),
                ))

        return GraphResponse(nodes=list(nodes_map.values()), edges=edges)

    # ── Graph Statistics ───────────────────────────────────────

    async def get_stats(self, doc_id: str | None = None) -> dict[str, Any]:
        """Get knowledge graph statistics."""
        async with self._neo4j_driver.session() as session:
            if doc_id:
                node_result = await session.run(
                    "MATCH (e:Entity {doc_id: $doc_id}) RETURN count(e) AS cnt, e.type AS type",
                    doc_id=doc_id,
                )
                edge_result = await session.run(
                    """
                    MATCH (a:Entity {doc_id: $doc_id})-[r]->(b:Entity {doc_id: $doc_id})
                    RETURN count(r) AS cnt, r.type AS type
                    """,
                    doc_id=doc_id,
                )
            else:
                node_result = await session.run(
                    "MATCH (e:Entity) RETURN count(e) AS cnt, e.type AS type"
                )
                edge_result = await session.run(
                    "MATCH ()-[r]->() RETURN count(r) AS cnt, r.type AS type"
                )

            node_records = [r async for r in node_result]
            edge_records = [r async for r in edge_result]

        entity_types: dict[str, int] = {}
        node_count = 0
        for r in node_records:
            entity_types[r["type"] or "Unknown"] = r["cnt"]
            node_count += r["cnt"]

        rel_types: dict[str, int] = {}
        edge_count = 0
        for r in edge_records:
            rel_types[r["type"] or "RELATES_TO"] = r["cnt"]
            edge_count += r["cnt"]

        return {
            "node_count": node_count,
            "edge_count": edge_count,
            "entity_types": entity_types,
            "relationship_types": rel_types,
        }

    # ── Internal Helpers ───────────────────────────────────────

    @staticmethod
    def _split_text(text: str, max_chars: int = 2000) -> list[str]:
        """Split text into segments for processing."""
        if len(text) <= max_chars:
            return [text]

        segments = []
        paragraphs = text.split("\n\n")
        current = ""

        for para in paragraphs:
            if len(current) + len(para) + 2 > max_chars and current:
                segments.append(current.strip())
                current = para
            else:
                current = current + "\n\n" + para if current else para

        if current.strip():
            segments.append(current.strip())

        return segments
