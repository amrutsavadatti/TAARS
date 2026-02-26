"""
Bulk ingest all files from raw_user_files/ into ChromaDB.

Usage:
    python scripts/ingest_all.py

Drop any files (PDF, MD, TXT, DOCX) into raw_user_files/ and run this
script to ingest them all in one shot. Safe to re-run — existing chunks
are upserted (not duplicated).
"""

import sys
from pathlib import Path

# Allow running from project root
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.config import settings
from backend.ingestion.pipeline import ingest_file
from backend.ingestion.parser import ALL_SUPPORTED

RAW_FILES_DIR = Path(__file__).parent.parent / "raw_user_files"


def main():
    if not RAW_FILES_DIR.exists():
        print(f"Directory not found: {RAW_FILES_DIR}")
        print("Create it and drop your files in there, then re-run.")
        sys.exit(1)

    files = [
        f for f in RAW_FILES_DIR.iterdir()
        if f.is_file() and f.suffix.lower() in ALL_SUPPORTED
    ]

    if not files:
        print(f"No supported files found in {RAW_FILES_DIR}/")
        print(f"Supported types: {sorted(ALL_SUPPORTED)}")
        sys.exit(0)

    print(f"Found {len(files)} file(s) in raw_user_files/\n")

    total_chunks = 0
    owner_id = settings.owner_name

    for f in sorted(files):
        try:
            result = ingest_file(f, owner_id=owner_id)
            print(f"  ✓ {f.name:<35}  {result.chunks_created:>3} chunks  doc_id={result.doc_id}")
            total_chunks += result.chunks_created
        except Exception as e:
            print(f"  ✗ {f.name:<35}  ERROR: {e}")

    print(f"\nDone. Total chunks in corpus: {total_chunks}")


if __name__ == "__main__":
    main()
