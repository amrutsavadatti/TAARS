"""
Ingestion pipeline — orchestrates the full flow for a single file:

  parse → chunk → embed → upsert to ChromaDB → save raw to blob store

Usage:
    result = ingest_file(file_path, owner_id)
    print(result.chunks_created, result.doc_id)
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from pathlib import Path

from backend.core.chunker import chunk_document
from backend.core.embeddings import get_embedder
from backend.ingestion.parser import parse_file
from backend.storage.vector_store import get_vector_store

logger = logging.getLogger(__name__)


@dataclass
class IngestionResult:
    doc_id: str
    source_file: str
    chunks_created: int
    owner_id: str


def ingest_file(file_path: str | Path, owner_id: str) -> IngestionResult:
    """
    Full ingestion pipeline for a single file.

    Steps:
      1. Parse  — extract text + metadata
      2. Chunk  — split into retrieval-ready pieces
      3. Embed  — generate vectors for each chunk
      4. Upsert — store in ChromaDB under owner's collection
      5. Blob   — copy raw file to data/uploads/{owner_id}/

    Args:
        file_path: Path to the file on disk.
        owner_id:  Portfolio owner identifier.

    Returns:
        IngestionResult with doc_id and chunk count.
    """
    file_path = Path(file_path)
    doc_id = str(uuid.uuid4())

    logger.info("Ingesting %s for owner=%s (doc_id=%s)", file_path.name, owner_id, doc_id)

    # 1. Parse
    logger.info("[1/4] Parsing %s", file_path.name)
    parsed = parse_file(file_path, owner_id)

    # 2. Chunk
    logger.info("[2/4] Chunking — %d pages/sections", parsed.page_count)
    chunks = chunk_document(parsed)

    # Attach doc_id to every chunk's metadata so we can delete by doc later
    for chunk in chunks:
        chunk.metadata["doc_id"] = doc_id

    logger.info("[2/4] Produced %d chunks", len(chunks))

    # 3 + 4. Embed and upsert into ChromaDB
    logger.info("[3/4] Embedding and upserting to ChromaDB")
    embedder = get_embedder()
    vs = get_vector_store(owner_id)
    vs.upsert_chunks(chunks, embedder)

    # 5. Save raw file to blob store
    logger.info("[4/4] Saving raw file to blob store")
    _save_to_blob(file_path, owner_id, doc_id)

    logger.info(
        "Ingestion complete — doc_id=%s, chunks=%d", doc_id, len(chunks)
    )

    return IngestionResult(
        doc_id=doc_id,
        source_file=file_path.name,
        chunks_created=len(chunks),
        owner_id=owner_id,
    )


def _save_to_blob(file_path: Path, owner_id: str, doc_id: str) -> Path:
    """
    Copy the raw file to data/uploads/{owner_id}/{doc_id}_{filename}.
    Creates the directory if it doesn't exist.
    """
    import shutil
    from backend.config import settings

    blob_dir = Path(settings.chroma_persist_dir).parent / "uploads" / owner_id
    blob_dir.mkdir(parents=True, exist_ok=True)

    dest = blob_dir / f"{doc_id}_{file_path.name}"
    shutil.copy2(file_path, dest)

    logger.info("Raw file saved to %s", dest)
    return dest
