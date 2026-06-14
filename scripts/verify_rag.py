"""
Quick smoke-test: query RAG for contact-related questions and print generated answers.
Usage:  uv run python scripts/verify_rag.py
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from core.llm import LLMClient  # noqa: E402
from core.prompts.rag_answer import answer_question  # noqa: E402
from core.rag import RagClient  # noqa: E402

QUERIES = [
    "как связаться с менеджером?",
    "как обратиться?",
]


async def main() -> None:
    llm = LLMClient()
    rag = RagClient()

    for query in QUERIES:
        print(f"\n{'─' * 60}")
        print(f"Q: {query}")
        chunks = await rag.search(query)
        print(f"RAG chunks retrieved: {len(chunks)}")
        for i, c in enumerate(chunks, 1):
            print(f"  [{i}] (score={c.score:.3f}) {c.content[:120].replace(chr(10), ' ')}…")
        answer = await answer_question(llm, rag, query)
        print(f"\nA: {answer}")

    print(f"\n{'─' * 60}")


if __name__ == "__main__":
    asyncio.run(main())
