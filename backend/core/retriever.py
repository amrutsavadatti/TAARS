"""
Retriever — two-stage retrieval pipeline.

Stage 1 — Vector search (fast, approximate):
    Embed the query → find top-K nearest chunks in ChromaDB by cosine similarity.
    Controlled by RETRIEVAL_TOP_K in .env (default 5).

Stage 2 — Cross-encoder rerank (slower, more accurate):
    Feed (question, chunk) pairs to a local cross-encoder model.
    It reads both together and gives a true relevance score.
    Keep only top RERANK_TOP_N results (default 3).
    Drop anything below SIMILARITY_THRESHOLD (default 0.65).

Why two stages?
    Vector search is fast enough to scan thousands of chunks but gives
    approximate scores. The cross-encoder is much more accurate but too
    slow to run on the whole corpus — so we only run it on the K candidates
    the vector search already narrowed down.

Public API:
    retriever = Retriever()
    results = retriever.retrieve("What is Amrut's tech stack?")
    # → list of RankedChunk, best first. Empty list = no relevant content found.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from backend.config import settings
from backend.core.embeddings import get_embedder
from backend.storage.vector_store import get_vector_store

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Result dataclass — what the RAG engine receives from the retriever
# ---------------------------------------------------------------------------

@dataclass
class RankedChunk:
    text: str           # the chunk text that will be injected into the prompt
    score: float        # cross-encoder relevance score (higher = more relevant)
    metadata: dict      # source_file, section, owner_id, etc.

    def __repr__(self):
        section = self.metadata.get("section", "?")
        return f"RankedChunk(section={section!r}, score={self.score:.3f}, text={self.text[:60]!r}...)"


# ---------------------------------------------------------------------------
# Retriever
# ---------------------------------------------------------------------------

class Retriever:
    """
    Stateless retriever — safe to instantiate once and reuse across requests.
    Both the embedder and cross-encoder model are loaded lazily on first use
    and then cached in memory.
    """

    def __init__(self, owner_id: str | None = None):
        self._owner_id = owner_id or settings.owner_name
        self._cross_encoder = None   # loaded lazily on first retrieve() call

    # ------------------------------------------------------------------
    # Cross-encoder: load once, reuse forever
    # ------------------------------------------------------------------

    def _get_cross_encoder(self):
        """
        Load the cross-encoder model the first time it's needed.
        sentence-transformers downloads the model weights on first run
        (~90 MB), then caches them locally. Fully free, runs on CPU.
        """
        if self._cross_encoder is None:
            from sentence_transformers import CrossEncoder
            logger.info("Loading cross-encoder model: %s", settings.rerank_model)
            self._cross_encoder = CrossEncoder(settings.rerank_model)
            logger.info("Cross-encoder loaded.")
        return self._cross_encoder

    # ------------------------------------------------------------------
    # Main retrieval method
    # ------------------------------------------------------------------

    def retrieve(
        self,
        query: str,
        top_k: int | None = None,
        rerank_top_n: int | None = None,
        threshold: float | None = None,
    ) -> list[RankedChunk]:
        """
        Full two-stage retrieval for a query string.

        Args:
            query:        The visitor's question.
            top_k:        How many candidates to pull from ChromaDB.
                          Defaults to RETRIEVAL_TOP_K from .env.
            rerank_top_n: How many to keep after reranking.
                          Defaults to RERANK_TOP_N from .env.
            threshold:    Minimum cross-encoder score to keep a chunk.
                          Defaults to SIMILARITY_THRESHOLD from .env.

        Returns:
            Sorted list of RankedChunk (best first).
            Empty list means no relevant content was found — the caller
            should return a canned "I don't know" response instead of
            calling the LLM.
        """
        top_k = top_k or settings.retrieval_top_k
        rerank_top_n = rerank_top_n or settings.rerank_top_n
        threshold = threshold if threshold is not None else settings.similarity_threshold

        logger.info(
            "Retrieving for query=%r  top_k=%d  rerank_top_n=%d  threshold=%.2f",
            query[:80], top_k, rerank_top_n, threshold,
        )

        # ------------------------------------------------------------------
        # Stage 1 — Vector search
        # ------------------------------------------------------------------
        embedder = get_embedder()
        vs = get_vector_store(self._owner_id)
        vector_results = vs.similarity_search(query, embedder, top_k=top_k)

        if not vector_results:
            logger.info("Vector search returned 0 results above threshold.")
            return []

        logger.info("Vector search: %d candidates", len(vector_results))

        # ------------------------------------------------------------------
        # Stage 2 — Cross-encoder reranking (optional)
        # ------------------------------------------------------------------
        # The ms-marco cross-encoder is trained on web search data and scores
        # poorly on resume/career text. For small corpora (<50 chunks), vector
        # similarity alone retrieves well. Enable reranking (ENABLE_RERANKING=true)
        # only when using a domain-appropriate model in production.
        if settings.enable_reranking:
            import math
            cross_encoder = self._get_cross_encoder()
            pairs = [(query, r.text) for r in vector_results]
            raw_scores = cross_encoder.predict(pairs)
            # Sigmoid normalises raw logits → [0, 1]
            scores = [1 / (1 + math.exp(-s)) for s in raw_scores]
            scored = sorted(zip(scores, vector_results), key=lambda x: x[0], reverse=True)
            logger.info("Cross-encoder reranking applied.")
        else:
            # Use vector similarity scores directly (cosine, already [0, 1])
            scored = sorted(
                [(r.score, r) for r in vector_results],
                key=lambda x: x[0],
                reverse=True,
            )
            logger.info("Using vector similarity scores (reranking disabled).")

        # ------------------------------------------------------------------
        # Filter: keep top N above threshold
        # ------------------------------------------------------------------
        ranked: list[RankedChunk] = []
        for score, vr in scored[:rerank_top_n]:
            if score < threshold:
                logger.info(
                    "Dropping chunk (score=%.3f < threshold=%.2f): %r",
                    score, threshold, vr.text[:60],
                )
                continue
            ranked.append(RankedChunk(text=vr.text, score=score, metadata=vr.metadata))

        logger.info(
            "Reranking complete: %d/%d chunks kept above threshold %.2f",
            len(ranked), len(vector_results), threshold,
        )

        return ranked


# ---------------------------------------------------------------------------
# Convenience function — used by rag_engine.py
# ---------------------------------------------------------------------------

def get_retriever(owner_id: str | None = None) -> Retriever:
    """Return a Retriever for the given owner (defaults to config OWNER_NAME)."""
    return Retriever(owner_id=owner_id)
