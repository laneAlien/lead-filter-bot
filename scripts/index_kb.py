"""
Indexer: reads data/kb/*.md, chunks, embeds, upserts into Qdrant.
Idempotent — recreates the collection on each run.

Usage:
    uv run python scripts/index_kb.py
    # or via Makefile:
    make index
"""

from __future__ import annotations

import re
import sys
import uuid
from pathlib import Path

from qdrant_client.http.models import PointStruct

# Ensure project root is on the path when run directly
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from core.config import get_settings  # noqa: E402
from core.rag import embed_passages, recreate_collection, upsert_points  # noqa: E402

KB_DIR = ROOT / "data" / "kb"
MIN_CHUNK = 80
MAX_CHUNK = 500
OVERLAP = 60


def _split_into_chunks(text: str, source: str) -> list[dict[str, str]]:
    """Split markdown text into ~300-500 char chunks with small overlap."""
    # Split on headings (## or ###) to preserve section boundaries
    sections = re.split(r"\n(?=#{1,3} )", text)
    chunks: list[dict[str, str]] = []

    for section in sections:
        section = section.strip()
        if not section:
            continue
        # Within each section, split on blank lines (paragraphs)
        paragraphs = [p.strip() for p in re.split(r"\n{2,}", section) if p.strip()]

        current = ""
        for para in paragraphs:
            if len(current) + len(para) + 1 <= MAX_CHUNK:
                current = f"{current}\n\n{para}".strip() if current else para
            else:
                if len(current) >= MIN_CHUNK:
                    chunks.append({"content": current, "source": source})
                # Overlap: carry last OVERLAP chars of previous chunk
                tail = current[-OVERLAP:] if len(current) > OVERLAP else current
                current = f"{tail} {para}".strip() if tail else para

        if len(current) >= MIN_CHUNK:
            chunks.append({"content": current, "source": source})

    return chunks


def main() -> None:
    settings = get_settings()
    md_files = sorted(KB_DIR.glob("*.md"))

    if not md_files:
        print(f"No .md files found in {KB_DIR}. Drop your knowledge base files there first.")
        sys.exit(1)

    all_chunks: list[dict[str, str]] = []
    for path in md_files:
        text = path.read_text(encoding="utf-8")
        file_chunks = _split_into_chunks(text, source=path.name)
        print(f"  {path.name}: {len(file_chunks)} chunks")
        all_chunks.extend(file_chunks)

    print(f"\nTotal: {len(md_files)} file(s), {len(all_chunks)} chunks")
    print("Embedding passages (this may take a moment)...")

    texts = [c["content"] for c in all_chunks]
    vectors = embed_passages(texts)

    points = [
        PointStruct(
            id=str(uuid.uuid4()),
            vector=vec,
            payload={"content": chunk["content"], "source": chunk["source"]},
        )
        for chunk, vec in zip(all_chunks, vectors, strict=True)
    ]

    print(f"Recreating Qdrant collection '{settings.qdrant_collection}'...")
    recreate_collection()
    upsert_points(points)
    print(f"Done — {len(points)} points upserted into '{settings.qdrant_collection}'.")


if __name__ == "__main__":
    main()
