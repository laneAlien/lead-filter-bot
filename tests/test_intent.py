"""Tests for core/services/intent.py — mocks LLMClient.chat_structured."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from core.schemas import IntentResult, IntentType
from core.services.intent import classify_intent


def _make_llm(intent: IntentType | None = None, raises: Exception | None = None) -> MagicMock:
    llm = MagicMock()
    if raises is not None:
        llm.chat_structured = AsyncMock(side_effect=raises)
    else:
        llm.chat_structured = AsyncMock(return_value=IntentResult(intent=intent))  # type: ignore[arg-type]
    return llm


@pytest.mark.asyncio
async def test_classify_intent_returns_question() -> None:
    llm = _make_llm(IntentType.question)
    result = await classify_intent(llm, "Какой у вас бюджет?", "а вы работаете с маркетплейсами?")
    assert result == IntentType.question


@pytest.mark.asyncio
async def test_classify_intent_returns_answer() -> None:
    llm = _make_llm(IntentType.answer)
    result = await classify_intent(llm, "Какой у вас бюджет?", "50 000 рублей")
    assert result == IntentType.answer


@pytest.mark.asyncio
async def test_classify_intent_passes_current_question_in_prompt() -> None:
    llm = _make_llm(IntentType.answer)
    current_q = "На каком этапе ваш бизнес?"
    user_msg = "работающий бизнес с выручкой"

    await classify_intent(llm, current_q, user_msg)

    call_args = llm.chat_structured.call_args
    messages = call_args.args[0]
    user_content = messages[1]["content"]
    assert current_q in user_content
    assert user_msg in user_content


@pytest.mark.asyncio
async def test_classify_intent_uses_low_max_tokens() -> None:
    llm = _make_llm(IntentType.answer)
    await classify_intent(llm, "Q?", "A")

    call_kwargs = llm.chat_structured.call_args.kwargs
    assert call_kwargs["max_tokens"] <= 50


@pytest.mark.asyncio
async def test_classify_intent_fails_safe_to_answer_on_exception() -> None:
    llm = _make_llm(raises=RuntimeError("API down"))
    result = await classify_intent(llm, "Какой бюджет?", "50к")
    assert result == IntentType.answer
