"""Tests for apps/bot/handlers/fallback.py — no-state catch-all handler."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from apps.bot.handlers.fallback import handle_no_state
from core.schemas import IntentType


def _make_message(text: str) -> MagicMock:
    msg = MagicMock()
    msg.text = text
    msg.answer = AsyncMock()
    return msg


def _make_llm() -> MagicMock:
    return MagicMock()


def _make_rag() -> MagicMock:
    rag = MagicMock()
    rag.search = AsyncMock(return_value=[])
    return rag


@pytest.mark.asyncio
async def test_question_outside_fsm_triggers_rag_and_start_nudge() -> None:
    """A question with no active FSM state gets a RAG answer then the /start nudge."""
    message = _make_message("сколько стоит таргет?")
    llm = _make_llm()
    rag = _make_rag()

    with (
        patch(
            "apps.bot.handlers.fallback.classify_intent",
            new=AsyncMock(return_value=IntentType.question),
        ),
        patch(
            "apps.bot.handlers.fallback.answer_question",
            new=AsyncMock(return_value="Стоимость таргета от 30 000 ₽."),
        ) as mock_aq,
    ):
        await handle_no_state(message, llm, rag)

    mock_aq.assert_awaited_once()
    assert message.answer.call_count == 2
    calls = [c.args[0] for c in message.answer.call_args_list]
    assert calls[0] == "Стоимость таргета от 30 000 ₽."
    assert "/start" in calls[1]


@pytest.mark.asyncio
async def test_non_question_outside_fsm_sends_only_start_nudge() -> None:
    """A non-question with no active FSM gets only the /start nudge, no RAG."""
    message = _make_message("привет")
    llm = _make_llm()
    rag = _make_rag()

    with (
        patch(
            "apps.bot.handlers.fallback.classify_intent",
            new=AsyncMock(return_value=IntentType.answer),
        ),
        patch("apps.bot.handlers.fallback.answer_question", new=AsyncMock()) as mock_aq,
    ):
        await handle_no_state(message, llm, rag)

    mock_aq.assert_not_called()
    message.answer.assert_awaited_once()
    assert "/start" in message.answer.call_args.args[0]
