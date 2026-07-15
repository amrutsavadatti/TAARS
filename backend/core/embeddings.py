"""
Embedding generation with two backends:

  openai     → OpenAI text-embedding-3-small (recommended, ~$0.02/1M tokens)
  huggingface → all-MiniLM-L6-v2 run locally on CPU (fully free fallback)

Controlled by EMBEDDING_PROVIDER in .env.

Public API:
    embedder = get_embedder()
    vector: list[float]       = embedder.embed_query("What is Amrut's tech stack?")
    vectors: list[list[float]] = embedder.embed_documents(["chunk 1", "chunk 2"])
"""

from __future__ import annotations

import logging
from functools import lru_cache
from typing import Protocol

from backend.config import settings

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Protocol — both backends expose the same interface
# ---------------------------------------------------------------------------

class Embedder(Protocol):
    def embed_query(self, text: str) -> list[float]: ...
    def embed_documents(self, texts: list[str]) -> list[list[float]]: ...


# ---------------------------------------------------------------------------
# OpenAI backend
# ---------------------------------------------------------------------------

class OpenAIEmbedder:
    """
    Thin wrapper around LangChain's OpenAIEmbeddings so we keep one
    consistent interface regardless of provider.
    """

    def __init__(self, model: str, api_key: str):
        from langchain_openai import OpenAIEmbeddings

        self._embeddings = OpenAIEmbeddings(
            model=model,
            openai_api_key=api_key,
        )
        logger.info("OpenAI embedder initialised — model: %s", model)

    def embed_query(self, text: str) -> list[float]:
        return self._embeddings.embed_query(text)

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return self._embeddings.embed_documents(texts)


# ---------------------------------------------------------------------------
# HuggingFace local backend (free fallback)
# ---------------------------------------------------------------------------

class HuggingFaceEmbedder:
    """
    Runs all-MiniLM-L6-v2 locally via sentence-transformers.
    No API key or internet needed after first model download.
    384-dimensional vectors vs 1536 for text-embedding-3-small.
    """

    def __init__(self, model: str):
        try:
            from langchain_huggingface import HuggingFaceEmbeddings
        except ImportError as exc:
            raise RuntimeError(
                "EMBEDDING_PROVIDER=huggingface requires optional local embedding "
                "dependencies. Install 'sentence-transformers' in your environment "
                "or use EMBEDDING_PROVIDER=openai."
            ) from exc

        self._embeddings = HuggingFaceEmbeddings(
            model_name=model,
            model_kwargs={"device": "cpu"},
            encode_kwargs={"normalize_embeddings": True},
        )
        logger.info("HuggingFace embedder initialised — model: %s", model)

    def embed_query(self, text: str) -> list[float]:
        return self._embeddings.embed_query(text)

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return self._embeddings.embed_documents(texts)


# ---------------------------------------------------------------------------
# Factory — call this everywhere instead of instantiating directly
# ---------------------------------------------------------------------------

@lru_cache(maxsize=1)
def get_embedder() -> Embedder:
    """
    Returns a cached embedder instance based on EMBEDDING_PROVIDER in config.
    The @lru_cache ensures the model/client is only loaded once per process.
    """
    provider = settings.embedding_provider.lower()

    if provider == "openai":
        if not settings.llm_api_key or settings.llm_api_key == "sk-...":
            raise ValueError(
                "LLM_API_KEY is not set. Add your OpenAI key to .env "
                "or switch EMBEDDING_PROVIDER=huggingface for local embeddings."
            )
        return OpenAIEmbedder(
            model=settings.embedding_model,
            api_key=settings.llm_api_key,
        )

    if provider == "huggingface":
        return HuggingFaceEmbedder(model=settings.embedding_model)

    raise ValueError(
        f"Unknown EMBEDDING_PROVIDER '{provider}'. Use 'openai' or 'huggingface'."
    )
