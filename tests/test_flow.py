"""Tests for apps/bot/flow.py — the per-turn FSM router."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aiogram.fsm.state import State, StatesGroup

from apps.bot.flow import StepConfig, process_turn
from core.schemas import IntentType


class _TestFSM(StatesGroup):
    step_a = State()
    step_b = State()
    step_c = State()


STEP_A = StepConfig(
    current_question="Какой бюджет?",
    data_key="budget",
    next_state=_TestFSM.step_b,
    next_question="Какой тип услуги?",
)

STEP_LAST = StepConfig(
    current_question="Опыт с агентствами?",
    data_key="experience",
    next_state=None,
    next_question=None,
)


def _make_message(text: str = "тестовый ответ") -> MagicMock:
    msg = MagicMock()
    msg.text = text
    msg.answer = AsyncMock()
    return msg


def _make_state(conv_id: int = 1, existing_data: dict | None = None) -> MagicMock:
    state = MagicMock()
    data = {"conversation_id": conv_id}
    if existing_data:
        data.update(existing_data)
    state.get_data = AsyncMock(return_value=data)
    state.update_data = AsyncMock()
    state.set_state = AsyncMock()
    return state


def _make_session_factory() -> MagicMock:
    session = MagicMock()
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock(return_value=False)
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    factory = MagicMock()
    factory.return_value = session
    return factory


def _make_llm() -> MagicMock:
    llm = MagicMock()
    return llm


def _make_rag() -> MagicMock:
    rag = MagicMock()
    rag.search = AsyncMock(return_value=[])
    return rag


# ---------------------------------------------------------------------------
# QUESTION path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_question_intent_stays_in_state_and_re_asks() -> None:
    message = _make_message("а вы работаете с маркетплейсами?")
    state = _make_state()
    session_factory = _make_session_factory()
    llm = _make_llm()
    rag = _make_rag()

    with (
        patch(
            "apps.bot.flow.classify_intent",
            new=AsyncMock(return_value=IntentType.question),
        ),
        patch(
            "apps.bot.flow.answer_question",
            new=AsyncMock(return_value="Да, работаем с маркетплейсами."),
        ),
    ):
        result = await process_turn(message, state, session_factory, llm, rag, STEP_A)

    assert result is False
    # RAG answer sent, then current question re-asked
    assert message.answer.call_count == 2
    calls = [c.args[0] for c in message.answer.call_args_list]
    assert calls[0] == "Да, работаем с маркетплейсами."
    assert calls[1] == STEP_A.current_question

    # State must NOT have advanced
    state.set_state.assert_not_called()
    state.update_data.assert_not_called()


@pytest.mark.asyncio
async def test_question_intent_does_not_store_message() -> None:
    message = _make_message("а есть ли у вас кейсы в недвижимости?")
    state = _make_state()
    session_factory = _make_session_factory()
    llm = _make_llm()
    rag = _make_rag()

    with (
        patch("apps.bot.flow.classify_intent", new=AsyncMock(return_value=IntentType.question)),
        patch("apps.bot.flow.answer_question", new=AsyncMock(return_value="Есть.")),
        patch("apps.bot.flow.add_message", new=AsyncMock()) as mock_add,
    ):
        await process_turn(message, state, session_factory, llm, rag, STEP_A)

    mock_add.assert_not_called()


# ---------------------------------------------------------------------------
# ANSWER path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_answer_intent_returns_true_and_advances_state() -> None:
    message = _make_message("50 000 рублей")
    state = _make_state()
    session_factory = _make_session_factory()
    llm = _make_llm()
    rag = _make_rag()

    with patch(
        "apps.bot.flow.classify_intent",
        new=AsyncMock(return_value=IntentType.answer),
    ):
        result = await process_turn(message, state, session_factory, llm, rag, STEP_A)

    assert result is True
    state.update_data.assert_awaited_once_with(budget="50 000 рублей")
    state.set_state.assert_awaited_once_with(_TestFSM.step_b)
    message.answer.assert_awaited_once_with(STEP_A.next_question)


@pytest.mark.asyncio
async def test_answer_intent_stores_user_message() -> None:
    message = _make_message("SMM")
    state = _make_state()
    session_factory = _make_session_factory()
    llm = _make_llm()
    rag = _make_rag()

    with (
        patch("apps.bot.flow.classify_intent", new=AsyncMock(return_value=IntentType.answer)),
        patch("apps.bot.flow.add_message", new=AsyncMock()) as mock_add,
    ):
        await process_turn(message, state, session_factory, llm, rag, STEP_A)

    # First call: store user message; second: store next question
    assert mock_add.call_count == 2
    first_call = mock_add.call_args_list[0]
    assert first_call.args[2] == "user"
    assert first_call.args[3] == "SMM"


@pytest.mark.asyncio
async def test_answer_last_step_does_not_advance_state() -> None:
    """Last step (next_state=None) returns True but does not call set_state."""
    message = _make_message("не было опыта")
    state = _make_state()
    session_factory = _make_session_factory()
    llm = _make_llm()
    rag = _make_rag()

    with patch(
        "apps.bot.flow.classify_intent",
        new=AsyncMock(return_value=IntentType.answer),
    ):
        result = await process_turn(message, state, session_factory, llm, rag, STEP_LAST)

    assert result is True
    state.set_state.assert_not_called()
    message.answer.assert_not_called()


# ---------------------------------------------------------------------------
# Compound message (answer + embedded question)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_compound_message_advances_fsm_and_sends_rag() -> None:
    """Answer part advances FSM; embedded question triggers a RAG reply before the next prompt."""
    message = _make_message("немедленно, а сколько стоит таргет?")
    state = _make_state()
    session_factory = _make_session_factory()
    llm = _make_llm()
    rag = _make_rag()

    with (
        patch("apps.bot.flow.classify_intent", new=AsyncMock(return_value=IntentType.answer)),
        patch(
            "apps.bot.flow.answer_question",
            new=AsyncMock(return_value="Стоимость таргета от 30 000 ₽."),
        ) as mock_aq,
    ):
        result = await process_turn(message, state, session_factory, llm, rag, STEP_A)

    assert result is True
    state.set_state.assert_awaited_once_with(_TestFSM.step_b)
    state.update_data.assert_awaited_once()
    mock_aq.assert_awaited_once()
    # RAG answer sent first, then the next FSM question
    assert message.answer.call_count == 2
    calls = [c.args[0] for c in message.answer.call_args_list]
    assert calls[0] == "Стоимость таргета от 30 000 ₽."
    assert calls[1] == STEP_A.next_question


@pytest.mark.asyncio
async def test_trailing_confirmation_does_not_trigger_rag() -> None:
    """A short trailing '?' like 'ок?' must not fire a RAG lookup."""
    message = _make_message("50 тысяч, ок?")
    state = _make_state()
    session_factory = _make_session_factory()
    llm = _make_llm()
    rag = _make_rag()

    with (
        patch("apps.bot.flow.classify_intent", new=AsyncMock(return_value=IntentType.answer)),
        patch("apps.bot.flow.answer_question", new=AsyncMock()) as mock_aq,
    ):
        result = await process_turn(message, state, session_factory, llm, rag, STEP_A)

    assert result is True
    mock_aq.assert_not_called()
    # Only the next FSM question — no RAG message
    message.answer.assert_awaited_once_with(STEP_A.next_question)


# ---------------------------------------------------------------------------
# RAG failure robustness
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_rag_failure_does_not_block_question_path() -> None:
    """Even if answer_question raises, the bot should still re-ask the question."""
    message = _make_message("вопрос клиента")
    state = _make_state()
    session_factory = _make_session_factory()
    llm = _make_llm()
    rag = _make_rag()

    with (
        patch("apps.bot.flow.classify_intent", new=AsyncMock(return_value=IntentType.question)),
        patch(
            "apps.bot.flow.answer_question",
            new=AsyncMock(return_value="Менеджер уточнит на звонке."),
        ),
    ):
        result = await process_turn(message, state, session_factory, llm, rag, STEP_A)

    assert result is False
    assert message.answer.call_count == 2
