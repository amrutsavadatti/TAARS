"""
ChromaDB vector store abstraction.

All operations are namespaced by owner_id — every portfolio owner's chunks
live in their own ChromaDB collection: career_assistant_{owner_id}

Public API:
    vs = get_vector_store()
    vs.upsert_chunks(chunks, embedder)
    results = vs.similarity_search(query_text, embedder, top_k=5)
    vs.delete_by_doc_id(doc_id)
    vs.list_documents()
"""

from __future__ import annotations

import logging
from functools import lru_cache
from typing import TYPE_CHECKING

import chromadb
from chromadb.config import Settings as ChromaSettings

from backend.config import settings

if TYPE_CHECKING:
    from backend.core.chunker import Chunk
    from backend.core.embeddings import Embedder

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Search result dataclass
# ---------------------------------------------------------------------------

class SearchResult:
    def __init__(self, chunk_id: str, text: str, metadata: dict, score: float):
        self.chunk_id = chunk_id
        self.text = text
        self.metadata = metadata
        self.score = score  # cosine distance (lower = more similar)

    def __repr__(self):
        return (
            f"SearchResult(section={self.metadata.get('section')!r}, "
            f"score={self.score:.4f}, text={self.text[:60]!r}...)"
        )


# ---------------------------------------------------------------------------
# VectorStore
# ---------------------------------------------------------------------------

class VectorStore:
    """
    Wraps a ChromaDB persistent client.
    One collection per owner: career_assistant_{owner_id}
    """

    def __init__(self, persist_dir: str, owner_id: str):
        self._owner_id = owner_id
        self._collection_name = f"career_assistant_{owner_id}"

        self._client = chromadb.PersistentClient(
            path=persist_dir,
            settings=ChromaSettings(anonymized_telemetry=False),
        )

        self._collection = self._client.get_or_create_collection(
            name=self._collection_name,
            metadata={"hnsw:space": "cosine"},  # cosine similarity
        )

        logger.info(
            "VectorStore ready — collection: %s, existing chunks: %d",
            self._collection_name,
            self._collection.count(),
        )

    # ------------------------------------------------------------------
    # Upsert
    # ------------------------------------------------------------------

    def upsert_chunks(self, chunks: list[Chunk], embedder: Embedder) -> int:
        """
        Embed and upsert a list of Chunk objects into ChromaDB.
        Uses upsert so re-ingesting a document is safe (idempotent).

        Returns number of chunks upserted.
        """
        if not chunks:
            return 0

        texts = [c.text for c in chunks]
        ids = [c.chunk_id for c in chunks]
        metadatas = [c.metadata for c in chunks]

        logger.info("Embedding %d chunks...", len(chunks))
        embeddings = embedder.embed_documents(texts)

        self._collection.upsert(
            ids=ids,
            documents=texts,
            embeddings=embeddings,
            metadatas=metadatas,
        )

        logger.info("Upserted %d chunks into %s", len(chunks), self._collection_name)
        return len(chunks)

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    def similarity_search(
        self,
        query: str,
        embedder: Embedder,
        top_k: int | None = None,
    ) -> list[SearchResult]:
        """
        Embed the query and return the top_k most similar chunks.
        Results are ordered by similarity (best first).
        Chunks below SIMILARITY_THRESHOLD are filtered out.
        """
        top_k = top_k or settings.retrieval_top_k
        threshold = settings.similarity_threshold

        query_embedding = embedder.embed_query(query)

        results = self._collection.query(
            query_embeddings=[query_embedding],
            n_results=min(top_k, self._collection.count() or 1),
            include=["documents", "metadatas", "distances"],
        )

        search_results: list[SearchResult] = []

        for chunk_id, text, metadata, distance in zip(
            results["ids"][0],
            results["documents"][0],
            results["metadatas"][0],
            results["distances"][0],
        ):
            # ChromaDB cosine distance: 0 = identical, 2 = opposite
            # Convert to similarity: 1 - distance/2  →  range [0, 1]
            similarity = 1.0 - distance / 2.0

            if similarity >= threshold:
                search_results.append(
                    SearchResult(
                        chunk_id=chunk_id,
                        text=text,
                        metadata=metadata,
                        score=similarity,
                    )
                )

        logger.info(
            "Query returned %d/%d results above threshold %.2f",
            len(search_results),
            top_k,
            threshold,
        )
        return search_results

    # ------------------------------------------------------------------
    # Document management
    # ------------------------------------------------------------------

    def delete_by_doc_id(self, doc_id: str) -> int:
        """
        Delete all chunks belonging to a document.
        Chunks store doc_id in metadata — we query by it then delete.
        Returns number of chunks deleted.
        """
        results = self._collection.get(
            where={"doc_id": doc_id},
            include=["metadatas"],
        )
        ids_to_delete = results["ids"]

        if ids_to_delete:
            self._collection.delete(ids=ids_to_delete)
            logger.info(
                "Deleted %d chunks for doc_id=%s", len(ids_to_delete), doc_id
            )

        return len(ids_to_delete)

    def delete_by_source_file(self, source_file: str) -> int:
        """Delete all chunks from a given source filename."""
        results = self._collection.get(
            where={"source_file": source_file},
            include=["metadatas"],
        )
        ids_to_delete = results["ids"]

        if ids_to_delete:
            self._collection.delete(ids=ids_to_delete)
            logger.info(
                "Deleted %d chunks for source_file=%s",
                len(ids_to_delete),
                source_file,
            )

        return len(ids_to_delete)

    def list_documents(self) -> list[dict]:
        """
        Return a deduplicated list of ingested documents with chunk counts.
        """
        results = self._collection.get(include=["metadatas"])
        metadatas = results["metadatas"] or []

        # Group by source_file
        docs: dict[str, dict] = {}
        for meta in metadatas:
            sf = meta.get("source_file", "unknown")
            if sf not in docs:
                docs[sf] = {
                    "source_file": sf,
                    "source_type": meta.get("source_type"),
                    "ingested_at": meta.get("ingested_at"),
                    "chunk_count": 0,
                }
            docs[sf]["chunk_count"] += 1

        return sorted(docs.values(), key=lambda d: d["ingested_at"] or "", reverse=True)

    def count(self) -> int:
        return self._collection.count()


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

@lru_cache(maxsize=1)
def get_vector_store(owner_id: str | None = None) -> VectorStore:
    """
    Returns a cached VectorStore for the given owner.
    Defaults to the configured OWNER_NAME when owner_id is not provided.
    """
    resolved_owner = (owner_id or settings.owner_name).lower().replace(" ", "_")
    return VectorStore(
        persist_dir=settings.chroma_persist_dir,
        owner_id=resolved_owner,
    )
