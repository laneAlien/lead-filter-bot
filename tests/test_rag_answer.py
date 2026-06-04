"""Tests for core/prompts/rag_answer.py."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from core.prompts.rag_answer import answer_question
from core.schemas import RagChunk


def _make_llm(reply: str = "Ответ агентства") -> MagicMock:
    llm = MagicMock()
    llm.chat = AsyncMock(return_value=reply)
    return llm


def _make_rag(chunks: list[RagChunk]) -> MagicMock:
    rag = MagicMock()
    rag.search = AsyncMock(return_value=chunks)
    return rag


@pytest.mark.asyncio
async def test_answer_question_builds_context_and_calls_llm() -> None:
    chunks = [
        RagChunk(content="SMM от 35 000 ₽/мес", score=0.9, source="agency_kb.md"),
        RagChunk(content="Таргет от 40 000 ₽/мес", score=0.85, source="agency_kb.md"),
    ]
    llm = _make_llm("SMM стоит от 35 000 ₽ в месяц.")
    rag = _make_rag(chunks)

    result = await answer_question(llm, rag, "сколько стоит SMM?")

    assert result == "SMM стоит от 35 000 ₽ в месяц."
    rag.search.assert_awaited_once_with("сколько стоит SMM?")

    call_args = llm.chat.call_args
    messages = call_args.args[0]
    user_content = messages[1]["content"]
    assert "SMM от 35 000" in user_content
    assert "Таргет от 40 000" in user_content


@pytest.mark.asyncio
async def test_answer_question_fallback_when_no_chunks() -> None:
    llm = _make_llm()
    rag = _make_rag([])

    result = await answer_question(llm, rag, "что-то неизвестное")

    assert "менеджер" in result.lower()
    llm.chat.assert_not_called()


@pytest.mark.asyncio
async def test_answer_question_uses_low_temperature() -> None:
    chunks = [RagChunk(content="контекст", score=0.8, source="kb.md")]
    llm = _make_llm()
    rag = _make_rag(chunks)

    await answer_question(llm, rag, "вопрос")

    call_kwargs = llm.chat.call_args.kwargs
    assert call_kwargs["temperature"] <= 0.3
