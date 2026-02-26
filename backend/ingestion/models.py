from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Literal


SourceType = Literal["pdf", "image", "markdown", "text", "docx"]


@dataclass
class ParsedDocument:
    """
    Output of any parser. One ParsedDocument per uploaded file.
    The chunker (Task 3) will split `pages` into smaller chunks.
    """
    # Core content
    pages: list[str]            # one string per page / logical section
    full_text: str              # concatenated, for reference

    # Metadata attached to every chunk derived from this document
    source_file: str            # original filename
    source_type: SourceType
    owner_id: str
    ingested_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    # Optional extras
    page_count: int = 0         # number of pages (PDF) / sections (other)
    extra: dict = field(default_factory=dict)   # parser-specific data
