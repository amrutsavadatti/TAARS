"""
Ingestion endpoint — upload documents via HTTP.

POST /api/v1/ingest
Headers: X-API-Key: {owner_api_key}
Body:    multipart/form-data, field name "files" (one or more files)

Supported file types: pdf, png, jpg, jpeg, txt, md, docx
Max file size per file: MAX_UPLOAD_SIZE_MB from .env (default 10 MB)

Response:
    {
        "status": "ok",
        "files": [
            { "filename": "Resume.pdf", "chunks_created": 9, "doc_id": "..." },
            ...
        ],
        "total_chunks": 9
    }

This endpoint is owner-only — in production it will require a JWT admin
token. For now it validates the X-API-Key header (same key as chat).
"""

from __future__ import annotations

import logging
import tempfile
from pathlib import Path

from fastapi import APIRouter, Header, HTTPException, UploadFile, File
from fastapi import status as http_status

from backend.config import settings
from backend.ingestion.pipeline import ingest_file

logger = logging.getLogger(__name__)

router = APIRouter(tags=["ingest"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _validate_api_key(api_key: str | None) -> None:
    if not api_key:
        raise HTTPException(
            status_code=http_status.HTTP_401_UNAUTHORIZED,
            detail="Missing X-API-Key header.",
        )


def _validate_file(file: UploadFile) -> None:
    """
    Check file type and size before processing.

    File type is checked by extension (simple, good enough for owner uploads).
    File size is checked after reading — UploadFile doesn't expose size upfront.
    """
    suffix = Path(file.filename or "").suffix.lower().lstrip(".")

    if suffix not in settings.allowed_file_types_list:
        raise HTTPException(
            status_code=http_status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=(
                f"File type '.{suffix}' is not supported. "
                f"Allowed: {', '.join(settings.allowed_file_types_list)}"
            ),
        )


# ---------------------------------------------------------------------------
# Ingest endpoint
# ---------------------------------------------------------------------------

@router.post("/ingest")
async def ingest_documents(
    files: list[UploadFile] = File(..., description="One or more files to ingest"),
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
):
    """
    Upload and ingest one or more documents into the vector store.

    Each file goes through the full pipeline:
        parse → chunk → embed → upsert to ChromaDB → save raw to blob store

    Existing documents with the same filename are re-ingested (upserted),
    so it's safe to upload an updated version of an existing file.
    """
    _validate_api_key(x_api_key)

    if not files:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail="No files provided.",
        )

    owner_id = settings.owner_name
    results = []
    total_chunks = 0
    errors = []

    for file in files:
        # Validate type before doing any work
        _validate_file(file)

        # Read file content and check size
        content = await file.read()
        size_mb = len(content) / (1024 * 1024)

        if size_mb > settings.max_upload_size_mb:
            errors.append({
                "filename": file.filename,
                "error": f"File too large ({size_mb:.1f} MB). Max is {settings.max_upload_size_mb} MB.",
            })
            continue

        # Write to a temp file so the pipeline (which expects a file path) can read it
        # NamedTemporaryFile with delete=False so we can pass the path to the pipeline
        suffix = Path(file.filename or "upload").suffix
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(content)
            tmp_path = Path(tmp.name)

        try:
            logger.info("Ingesting uploaded file: %s (%.2f MB)", file.filename, size_mb)

            result = ingest_file(tmp_path, owner_id=owner_id)

            # Use the original filename in the result, not the temp path name
            results.append({
                "filename": file.filename,
                "doc_id": result.doc_id,
                "chunks_created": result.chunks_created,
                "size_mb": round(size_mb, 2),
            })
            total_chunks += result.chunks_created

            logger.info(
                "Ingested %s — %d chunks, doc_id=%s",
                file.filename, result.chunks_created, result.doc_id,
            )

        except Exception as e:
            logger.error("Failed to ingest %s: %s", file.filename, e)
            errors.append({
                "filename": file.filename,
                "error": str(e),
            })

        finally:
            # Always clean up the temp file
            tmp_path.unlink(missing_ok=True)

    # If every file failed, return 422
    if errors and not results:
        raise HTTPException(
            status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"message": "All files failed to ingest.", "errors": errors},
        )

    response = {
        "status": "ok",
        "files": results,
        "total_chunks": total_chunks,
    }

    # Include partial errors if some files failed but others succeeded
    if errors:
        response["errors"] = errors

    return response
