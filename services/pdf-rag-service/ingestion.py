"""
PDF Ingestion Pipeline.

1. Extract text from PDF (PyMuPDF)
2. Chunk into 512-token segments with 50-token overlap (tiktoken)
3. Generate embeddings via LLM provider
4. Store chunks + embeddings in Qdrant
5. Extract entities/relationships via KG Engine
6. Store knowledge graph in Neo4j (via KG Engine)
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

import fitz  # PyMuPDF
import tiktoken
from qdrant_client import AsyncQdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams

from shared.config import Settings
from shared.llm_provider import LLMProvider
from kg_engine import KGEngine

logger = logging.getLogger(__name__)

CHUNK_SIZE = 512       # tokens
CHUNK_OVERLAP = 50     # tokens


class PDFIngestionPipeline:
    """Orchestrates the full ingestion pipeline: PDF → chunks → embeddings → graph."""

    def __init__(self, settings: Settings):
        self._settings = settings
        self._llm = LLMProvider()
        self._qdrant: AsyncQdrantClient | None = None
        self._kg_engine = KGEngine(settings)
        self._tokenizer = tiktoken.get_encoding("cl100k_base")

    async def initialize(self):
        """Connect to Qdrant and Neo4j (via KG Engine)."""
        self._qdrant = AsyncQdrantClient(
            host=self._settings.qdrant.host,
            port=self._settings.qdrant.port,
        )
        # Ensure collection exists
        collections = await self._qdrant.get_collections()
        collection_names = [c.name for c in collections.collections]
        if self._settings.qdrant.collection not in collection_names:
            await self._qdrant.create_collection(
                collection_name=self._settings.qdrant.collection,
                vectors_config=VectorParams(size=768, distance=Distance.COSINE),
            )

        await self._kg_engine.initialize()

    async def close(self):
        if self._qdrant:
            await self._qdrant.close()
        await self._kg_engine.close()

    @property
    def kg_engine(self) -> KGEngine:
        """Expose the KG Engine for direct access by API endpoints."""
        return self._kg_engine

    # ── Public API ─────────────────────────────────

    async def process(
        self,
        pdf_path: str,
        doc_id: str,
        user_id: str,
        filename: str,
    ) -> dict[str, Any]:
        """Full ingestion pipeline. Returns stats."""
        # Step 1: Extract text
        pages = self._extract_text(pdf_path)
        full_text = "\n\n".join(pages)
        logger.info(f"Extracted {len(pages)} pages from {filename}")

        # Step 2: Chunk
        chunks = self._chunk_text(full_text)
        logger.info(f"Created {len(chunks)} chunks")

        # Step 3: Generate embeddings & store in Qdrant
        await self._store_embeddings(chunks, doc_id)
        logger.info(f"Stored {len(chunks)} embeddings in Qdrant")

        # Step 4 & 5: Extract entities and store graph (via KG Engine)
        extraction = await self._kg_engine.extract_and_store(full_text, doc_id, source_label=filename)
        logger.info(
            f"Extracted {len(extraction.entities)} entities, "
            f"{len(extraction.relationships)} relationships (via KG Engine)"
        )

        return {
            "chunk_count": len(chunks),
            "entity_count": len(extraction.entities),
            "relationship_count": len(extraction.relationships),
        }

    # ── Step 1: Text Extraction ────────────────────────

    def _extract_text(self, pdf_path: str) -> list[str]:
        """Extract text from each page of a PDF."""
        doc = fitz.open(pdf_path)
        pages = []
        for page in doc:
            text = page.get_text("text")
            if text.strip():
                pages.append(text.strip())
        doc.close()
        return pages

    # ── Step 2: Chunking ──────────────────────────────

    def _chunk_text(self, text: str) -> list[str]:
        """Chunk text into CHUNK_SIZE-token segments with CHUNK_OVERLAP overlap."""
        tokens = self._tokenizer.encode(text)
        chunks = []
        start = 0

        while start < len(tokens):
            end = start + CHUNK_SIZE
            chunk_tokens = tokens[start:end]
            chunk_text = self._tokenizer.decode(chunk_tokens)
            chunks.append(chunk_text)
            start += CHUNK_SIZE - CHUNK_OVERLAP

        return chunks

    # ── Step 3: Embeddings → Qdrant ───────────────────────

    async def _store_embeddings(self, chunks: list[str], doc_id: str):
        """Generate embeddings and upsert into Qdrant."""
        batch_size = 10
        for i in range(0, len(chunks), batch_size):
            batch = chunks[i : i + batch_size]
            embeddings = await self._llm.embed(batch)

            points = [
                PointStruct(
                    id=str(uuid.uuid4()),
                    vector=embedding,
                    payload={
                        "document_id": doc_id,
                        "chunk_index": i + j,
                        "content": chunk,
                    },
                )
                for j, (chunk, embedding) in enumerate(zip(batch, embeddings))
            ]

            await self._qdrant.upsert(
                collection_name=self._settings.qdrant.collection,
                points=points,
            )
