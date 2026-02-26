"""
PDF parser using PyMuPDF (fitz).

Strategy:
- Extract text page-by-page preserving page boundaries.
- If a page has no extractable text (scanned image page), fall back to
  rendering it as an image and returning a placeholder so the chunker
  can skip or flag it for the image parser.
- Preserve page numbers in metadata for source citation.
"""

import fitz  # PyMuPDF
from pathlib import Path

from backend.ingestion.models import ParsedDocument


def parse_pdf(file_path: str | Path, owner_id: str) -> ParsedDocument:
    file_path = Path(file_path)
    doc = fitz.open(str(file_path))

    pages: list[str] = []

    for page_num, page in enumerate(doc, start=1):
        text = page.get_text("text").strip()

        if text:
            # Prefix with page marker so the chunker can use it
            pages.append(f"[Page {page_num}]\n{text}")
        else:
            # Scanned / image-only page — flag it; image_parser handles these
            pages.append(f"[Page {page_num}] [IMAGE_ONLY_PAGE]")

    doc.close()

    full_text = "\n\n".join(pages)

    return ParsedDocument(
        pages=pages,
        full_text=full_text,
        source_file=file_path.name,
        source_type="pdf",
        owner_id=owner_id,
        page_count=len(pages),
    )
