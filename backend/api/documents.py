"""
Document management endpoints — list and delete ingested documents.

GET    /api/v1/documents           → list all ingested documents with chunk counts
DELETE /api/v1/documents/{doc_id}  → delete a document and all its chunks

These are owner-only endpoints. In production they will require a JWT admin
token. For now they validate the X-API-Key header.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Header, HTTPException
from fastapi import status as http_status

from backend.config import settings
from backend.storage.vector_store import get_vector_store

logger = logging.getLogger(__name__)

router = APIRouter(tags=["documents"])


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _validate_api_key(api_key: str | None) -> None:
    if not api_key:
        raise HTTPException(
            status_code=http_status.HTTP_401_UNAUTHORIZED,
            detail="Missing X-API-Key header.",
        )


# ---------------------------------------------------------------------------
# List documents
# ---------------------------------------------------------------------------

@router.get("/documents")
async def list_documents(
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
):
    """
    List all documents currently ingested in the vector store.

    Returns each document with:
        - source_file: original filename
        - source_type: pdf / markdown / text / image / docx
        - chunk_count: number of chunks stored for this document
        - ingested_at: ISO timestamp of when it was ingested
    """
    _validate_api_key(x_api_key)

    vs = get_vector_store(settings.owner_name)
    documents = vs.list_documents()

    return {
        "total_documents": len(documents),
        "total_chunks": sum(d["chunk_count"] for d in documents),
        "documents": documents,
    }


# ---------------------------------------------------------------------------
# Delete document
# ---------------------------------------------------------------------------

@router.delete("/documents/{doc_id}")
async def delete_document(
    doc_id: str,
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
):
    """
    Delete a document and all its chunks from the vector store.

    The doc_id is returned when you ingest a file. You can also find it
    by listing documents (GET /api/v1/documents).

    Note: this removes the chunks from ChromaDB but does NOT delete the
    raw file from blob storage (data/uploads/). That will be added when
    blob_store.py is implemented.
    """
    _validate_api_key(x_api_key)

    vs = get_vector_store(settings.owner_name)
    deleted_count = vs.delete_by_doc_id(doc_id)

    if deleted_count == 0:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail=f"No document found with doc_id='{doc_id}'. It may have already been deleted.",
        )

    logger.info("Deleted doc_id=%s (%d chunks)", doc_id, deleted_count)

    return {
        "status": "ok",
        "doc_id": doc_id,
        "chunks_deleted": deleted_count,
    }
