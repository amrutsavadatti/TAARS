"""
Top-level parser router.

Detects file type from extension and dispatches to the correct parser.
All parsers return a ParsedDocument with a consistent structure.

Usage:
    doc = parse_file("/path/to/resume.pdf", owner_id="amrut")
"""

from pathlib import Path

from backend.ingestion.models import ParsedDocument

# Supported extensions → parser mapping
_PDF_EXTENSIONS = {".pdf"}
_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".gif"}
_TEXT_EXTENSIONS = {".txt", ".md"}
_DOCX_EXTENSIONS = {".docx"}

ALL_SUPPORTED = _PDF_EXTENSIONS | _IMAGE_EXTENSIONS | _TEXT_EXTENSIONS | _DOCX_EXTENSIONS


def parse_file(file_path: str | Path, owner_id: str) -> ParsedDocument:
    """
    Route a file to the correct parser based on its extension.

    Args:
        file_path: Path to the uploaded file on disk.
        owner_id:  The portfolio owner's ID for namespacing.

    Returns:
        ParsedDocument with pages, full_text, and metadata.

    Raises:
        ValueError: If the file type is not supported.
    """
    file_path = Path(file_path)
    suffix = file_path.suffix.lower()

    if suffix not in ALL_SUPPORTED:
        raise ValueError(
            f"Unsupported file type '{suffix}'. "
            f"Supported: {sorted(ALL_SUPPORTED)}"
        )

    if suffix in _PDF_EXTENSIONS:
        from backend.ingestion.pdf_parser import parse_pdf
        return parse_pdf(file_path, owner_id)

    if suffix in _IMAGE_EXTENSIONS:
        from backend.ingestion.image_parser import parse_image
        return parse_image(file_path, owner_id)

    if suffix in _TEXT_EXTENSIONS:
        from backend.ingestion.text_parser import parse_text
        return parse_text(file_path, owner_id)

    if suffix in _DOCX_EXTENSIONS:
        from backend.ingestion.text_parser import parse_docx
        return parse_docx(file_path, owner_id)

    # Should never reach here given the check above
    raise ValueError(f"Unhandled extension: {suffix}")
