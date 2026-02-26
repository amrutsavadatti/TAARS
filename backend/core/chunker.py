"""
Document chunker — splits a ParsedDocument into retrieval-ready chunks.

Strategy by source type:
  pdf (resume)  → detect resume sections (EXPERIENCE, SKILLS, PROJECTS,
                   EDUCATION) then split each experience / project into its
                   own chunk. Falls back to page-based overlap for non-resume PDFs.
  markdown/text → sections from parser, with overlap stitching for small sections.
  docx          → same as markdown/text.
  image         → single chunk (caption already atomic).

Each chunk is a dict ready to be embedded and upserted into ChromaDB.
"""

import re
import uuid
from dataclasses import dataclass, field

from backend.ingestion.models import ParsedDocument


# ---------------------------------------------------------------------------
# Chunk dataclass
# ---------------------------------------------------------------------------

@dataclass
class Chunk:
    chunk_id: str
    text: str
    metadata: dict = field(default_factory=dict)

    def __post_init__(self):
        if not self.chunk_id:
            self.chunk_id = str(uuid.uuid4())


# ---------------------------------------------------------------------------
# Token estimation (cheap approximation — 1 token ≈ 4 chars)
# ---------------------------------------------------------------------------

def _token_estimate(text: str) -> int:
    return max(1, len(text) // 4)


# ---------------------------------------------------------------------------
# Resume section detection
# ---------------------------------------------------------------------------

# Common resume section headers (case-insensitive)
_RESUME_SECTION_PATTERN = re.compile(
    r"^(EXPERIENCE|WORK EXPERIENCE|EMPLOYMENT|SKILLS|TECHNICAL SKILLS|"
    r"PROJECTS|EDUCATION|CERTIFICATIONS|SUMMARY|OBJECTIVE|ABOUT|"
    r"PUBLICATIONS|AWARDS|ACHIEVEMENTS|LANGUAGES|INTERESTS)\s*$",
    re.IGNORECASE | re.MULTILINE,
)

# Patterns to detect individual job/project entry starts within a section
# Matches lines that look like role titles or project names followed by dates
_ENTRY_SPLIT_PATTERN = re.compile(
    r"(?=\n(?:[A-Z][^\n]{5,80})\n(?:(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec|"
    r"\d{4})\s*[-–]\s*(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec|Present|\d{4})|"
    r"(?:Aug|Sep|Jan|Feb|Mar|Apr|May|Jun|Jul|Oct|Nov|Dec)\s+\d{4}))"
)


def _is_resume(doc: ParsedDocument) -> bool:
    """Heuristic: does the document look like a resume?"""
    text_upper = doc.full_text.upper()
    resume_signals = ["EXPERIENCE", "EDUCATION", "SKILLS"]
    hits = sum(1 for s in resume_signals if s in text_upper)
    return hits >= 2


def _split_resume(text: str) -> dict[str, str]:
    """
    Split resume text into named sections.
    Returns {section_name: section_text}.
    """
    # Find all section header positions
    matches = list(_RESUME_SECTION_PATTERN.finditer(text))
    if not matches:
        return {"full_resume": text}

    sections: dict[str, str] = {}

    # Text before first header (usually name + contact info)
    header_text = text[: matches[0].start()].strip()
    if header_text:
        sections["header"] = header_text

    for i, match in enumerate(matches):
        section_name = match.group().strip().upper()
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        section_body = text[start:end].strip()
        if section_body:
            sections[section_name] = section_body

    return sections


_DATE_PATTERN = re.compile(
    r"(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec|\d{4}).{0,20}(Present|\d{4})",
    re.IGNORECASE,
)


def _split_entries(section_text: str, section_name: str) -> list[str]:
    """
    Within EXPERIENCE or PROJECTS sections, split into individual entries.

    An entry boundary is: a non-bullet, non-date title line whose NEXT line
    is a date range. We flush the current entry and start a new one at the
    title line (keeping title + date + bullets together).
    """
    lines = section_text.split("\n")
    entries: list[str] = []
    current: list[str] = []

    i = 0
    while i < len(lines):
        line = lines[i].strip()
        next_line = lines[i + 1].strip() if i + 1 < len(lines) else ""

        is_bullet = line.startswith("•") or line.startswith("-")
        is_date_line = bool(_DATE_PATTERN.search(line)) and len(line) < 60
        # A title: non-empty, not a bullet, not itself a date, and next line is a date
        is_entry_title = (
            line
            and not is_bullet
            and not is_date_line
            and bool(_DATE_PATTERN.search(next_line))
        )

        if is_entry_title and current:
            entries.append("\n".join(current).strip())
            current = []

        current.append(lines[i])
        i += 1

    if current:
        entries.append("\n".join(current).strip())

    entries = [e for e in entries if _token_estimate(e) > 10]
    return entries if entries else [section_text]


# ---------------------------------------------------------------------------
# Overlap stitching for prose documents
# ---------------------------------------------------------------------------

def _chunks_with_overlap(
    sections: list[str],
    max_tokens: int = 400,
    overlap_tokens: int = 80,
) -> list[str]:
    """
    Combine small sections and add overlap between chunks to preserve context
    across boundaries. Used for blog posts and plain prose documents.
    """
    chunks: list[str] = []
    current_parts: list[str] = []
    current_tokens = 0

    for section in sections:
        section_tokens = _token_estimate(section)

        if current_tokens + section_tokens > max_tokens and current_parts:
            chunk_text = "\n\n".join(current_parts)
            chunks.append(chunk_text)

            # Carry the last part as overlap into the next chunk
            overlap_text = current_parts[-1] if current_parts else ""
            if _token_estimate(overlap_text) <= overlap_tokens:
                current_parts = [overlap_text]
                current_tokens = _token_estimate(overlap_text)
            else:
                # Trim overlap text to fit token budget
                words = overlap_text.split()
                overlap_words = words[-overlap_tokens:]
                current_parts = [" ".join(overlap_words)]
                current_tokens = overlap_tokens
        else:
            current_parts.append(section)
            current_tokens += section_tokens

    if current_parts:
        chunks.append("\n\n".join(current_parts))

    return [c for c in chunks if c.strip()]


# ---------------------------------------------------------------------------
# Main chunking entry point
# ---------------------------------------------------------------------------

def chunk_document(doc: ParsedDocument) -> list[Chunk]:
    """
    Split a ParsedDocument into a list of Chunks ready for embedding.

    Args:
        doc: Output from any parser in backend/ingestion/

    Returns:
        List of Chunk objects with text and metadata.
    """
    base_metadata = {
        "source_file": doc.source_file,
        "source_type": doc.source_type,
        "owner_id": doc.owner_id,
        "ingested_at": doc.ingested_at,
    }

    # ------------------------------------------------------------------
    # Images — already one atomic chunk
    # ------------------------------------------------------------------
    if doc.source_type == "image":
        return [
            Chunk(
                chunk_id=str(uuid.uuid4()),
                text=doc.full_text,
                metadata={**base_metadata, "section": "image_caption"},
            )
        ]

    # ------------------------------------------------------------------
    # PDF — resume-aware or page-based
    # ------------------------------------------------------------------
    if doc.source_type == "pdf":
        if _is_resume(doc):
            return _chunk_resume_pdf(doc, base_metadata)
        else:
            return _chunk_generic_pdf(doc, base_metadata)

    # ------------------------------------------------------------------
    # Markdown, plain text, DOCX — section/overlap based
    # ------------------------------------------------------------------
    return _chunk_prose(doc, base_metadata)


# ---------------------------------------------------------------------------
# PDF: resume chunking
# ---------------------------------------------------------------------------

def _chunk_resume_pdf(doc: ParsedDocument, base_meta: dict) -> list[Chunk]:
    """
    Resume-aware chunking:
    - Header + Summary → one chunk (identity / overview)
    - Each work experience entry → one chunk
    - Skills block → one chunk
    - Each project entry → one chunk
    - Each education entry → one chunk
    """
    chunks: list[Chunk] = []
    # Combine all pages into single text (resumes are usually 1-2 pages)
    full = doc.full_text

    # Strip [Page N] markers injected by the PDF parser before section detection
    full = re.sub(r"\[Page \d+\]\n?", "", full).strip()

    sections = _split_resume(full)

    for section_name, section_body in sections.items():
        section_lower = section_name.lower()

        if section_name == "header":
            chunks.append(Chunk(
                chunk_id=str(uuid.uuid4()),
                text=f"Contact & Overview\n{section_body}",
                metadata={**base_meta, "section": "header"},
            ))

        elif "experience" in section_lower or "employment" in section_lower:
            entries = _split_entries(section_body, section_name)
            for entry in entries:
                chunks.append(Chunk(
                    chunk_id=str(uuid.uuid4()),
                    text=f"Work Experience\n{entry}",
                    metadata={**base_meta, "section": "experience"},
                ))

        elif "project" in section_lower:
            entries = _split_entries(section_body, section_name)
            for entry in entries:
                chunks.append(Chunk(
                    chunk_id=str(uuid.uuid4()),
                    text=f"Project\n{entry}",
                    metadata={**base_meta, "section": "project"},
                ))

        elif "education" in section_lower:
            entries = _split_entries(section_body, section_name)
            for entry in entries:
                chunks.append(Chunk(
                    chunk_id=str(uuid.uuid4()),
                    text=f"Education\n{entry}",
                    metadata={**base_meta, "section": "education"},
                ))

        elif "skill" in section_lower:
            chunks.append(Chunk(
                chunk_id=str(uuid.uuid4()),
                text=f"Skills\n{section_body}",
                metadata={**base_meta, "section": "skills"},
            ))

        elif "summary" in section_lower or "objective" in section_lower or "about" in section_lower:
            chunks.append(Chunk(
                chunk_id=str(uuid.uuid4()),
                text=f"Summary\n{section_body}",
                metadata={**base_meta, "section": "summary"},
            ))

        elif "certif" in section_lower:
            # Each line is a separate cert
            for line in section_body.split("\n"):
                line = line.strip("•- ").strip()
                if line:
                    chunks.append(Chunk(
                        chunk_id=str(uuid.uuid4()),
                        text=f"Certification: {line}",
                        metadata={**base_meta, "section": "certification"},
                    ))
        else:
            # Generic section — keep as-is
            chunks.append(Chunk(
                chunk_id=str(uuid.uuid4()),
                text=f"{section_name}\n{section_body}",
                metadata={**base_meta, "section": section_lower},
            ))

    return chunks


# ---------------------------------------------------------------------------
# PDF: generic (non-resume) page-based chunking
# ---------------------------------------------------------------------------

def _chunk_generic_pdf(doc: ParsedDocument, base_meta: dict) -> list[Chunk]:
    """Page-based chunking with overlap for non-resume PDFs."""
    chunks = _chunks_with_overlap(doc.pages, max_tokens=400, overlap_tokens=80)
    return [
        Chunk(
            chunk_id=str(uuid.uuid4()),
            text=text,
            metadata={**base_meta, "section": f"page_chunk_{i + 1}"},
        )
        for i, text in enumerate(chunks)
    ]


# ---------------------------------------------------------------------------
# Prose: markdown, text, docx
# ---------------------------------------------------------------------------

def _chunk_prose(doc: ParsedDocument, base_meta: dict) -> list[Chunk]:
    """Section + overlap chunking for prose documents."""
    chunks = _chunks_with_overlap(doc.pages, max_tokens=400, overlap_tokens=80)
    return [
        Chunk(
            chunk_id=str(uuid.uuid4()),
            text=text,
            metadata={**base_meta, "section": f"section_{i + 1}"},
        )
        for i, text in enumerate(chunks)
    ]
