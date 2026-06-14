"""
tests/test_fsm_scenarios.py — Phase 1: FSM+RAG behaviour spec.

All LLM / intent / RAG calls are mocked — no network, no DB, fully deterministic.
Tests assert the DESIRED behaviour; failures document existing gaps.

Scenario matrix
---------------
S1  Clean answer at each step        → advance FSM, store value, send next question only
S2  Pure question mid-FSM            → RAG reply + re-ask current ONCE; NO advance, NOT stored
S3  Compound "answer + question"     → RAG reply + advance + send NEXT; must NOT re-ask current
S4  Extra message on ANSWER path     → current question never duplicated; process_turn is idempotent
S5  Invalid answer (garbage input)   → EXPECTED re-ask; ACTUAL stores + advances  [EXPECTED FAIL]
S6  Two near-simultaneous messages   → per-user lock serialises; no duplicate sends, no corruption
S7  Question after FSM finished      → RAG answer + /start nudge
S8  Garbage / empty message          → no crash (pass); empty should re-ask  [partial EXPECTED FAIL]
"""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aiogram.fsm.state import State, StatesGroup

from apps.bot.flow import StepConfig, process_turn
from apps.bot.handlers.fallback import handle_no_state
from apps.bot.middleware.user_lock import PerUserLockMiddleware
from core.schemas import IntentType

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


class _FSM(StatesGroup):
    step_a = State()
    step_b = State()
    step_c = State()


STEP_MID = StepConfig(
    current_question="Какой бюджет?",
    data_key="budget",
    next_state=_FSM.step_b,
    next_question="Какой тип услуги?",
)

# Same step but with the digit validator — used in S5 tests that probe garbage rejection.
STEP_MID_BUDGET = StepConfig(
    current_question="Какой бюджет?",
    data_key="budget",
    next_state=_FSM.step_b,
    next_question="Какой тип услуги?",
    validator=lambda t: any(c.isdigit() for c in t),
)

STEP_LAST = StepConfig(
    current_question="Опыт с агентствами?",
    data_key="experience",
    next_state=None,
    next_question=None,
)


def _msg(text: str = "ответ") -> MagicMock:
    m = MagicMock()
    m.text = text
    m.answer = AsyncMock()
    return m


def _state(conv_id: int = 1, **extra: Any) -> MagicMock:
    data: dict[str, Any] = {"conversation_id": conv_id, **extra}
    s = MagicMock()
    s.get_data = AsyncMock(return_value=data)
    s.update_data = AsyncMock()
    s.set_state = AsyncMock()
    return s


def _session_factory() -> MagicMock:
    sess = MagicMock()
    sess.__aenter__ = AsyncMock(return_value=sess)
    sess.__aexit__ = AsyncMock(return_value=False)
    sess.commit = AsyncMock()
    sess.refresh = AsyncMock()
    return MagicMock(return_value=sess)


def _llm() -> MagicMock:
    return MagicMock()


def _rag() -> MagicMock:
    r = MagicMock()
    r.search = AsyncMock(return_value=[])
    return r


# ---------------------------------------------------------------------------
# S1: Clean answer at each FSM step
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_s1_mid_step_stores_value_advances_sends_next() -> None:
    """S1: Clean answer at a mid-step → store value, advance state, send next question ONCE."""
    message = _msg("100 000 рублей")
    state = _state()

    with (
        patch("apps.bot.flow.classify_intent", new=AsyncMock(return_value=IntentType.answer)),
        patch("apps.bot.flow.add_message", new=AsyncMock()),
    ):
        result = await process_turn(message, state, _session_factory(), _llm(), _rag(), STEP_MID)

    assert result is True
    state.update_data.assert_awaited_once_with(budget="100 000 рублей")
    state.set_state.assert_awaited_once_with(_FSM.step_b)
    message.answer.assert_awaited_once_with(STEP_MID.next_question)


@pytest.mark.asyncio
async def test_s1_last_step_stores_value_no_advance_no_message() -> None:
    """S1: Last step (next_state=None) → True returned, set_state NOT called, no message sent."""
    message = _msg("не работал с агентствами")
    state = _state()

    with (
        patch("apps.bot.flow.classify_intent", new=AsyncMock(return_value=IntentType.answer)),
        patch("apps.bot.flow.add_message", new=AsyncMock()),
    ):
        result = await process_turn(message, state, _session_factory(), _llm(), _rag(), STEP_LAST)

    assert result is True
    state.set_state.assert_not_called()
    message.answer.assert_not_called()


@pytest.mark.asyncio
async def test_s1_user_message_persisted_to_db() -> None:
    """S1: The user's text must be recorded as role=user before the next question is recorded."""
    message = _msg("SMM")
    state = _state()

    with (
        patch("apps.bot.flow.classify_intent", new=AsyncMock(return_value=IntentType.answer)),
        patch("apps.bot.flow.add_message", new=AsyncMock()) as mock_add,
    ):
        await process_turn(message, state, _session_factory(), _llm(), _rag(), STEP_MID)

    assert mock_add.call_count == 2  # user msg + assistant next_question
    role_of_first = mock_add.call_args_list[0].args[2]
    text_of_first = mock_add.call_args_list[0].args[3]
    assert role_of_first == "user"
    assert text_of_first == "SMM"


# ---------------------------------------------------------------------------
# S2: Pure question mid-FSM
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_s2_question_sends_rag_then_current_question() -> None:
    """S2: Pure question → [RAG reply, current_question] in that order, exactly 2 messages."""
    message = _msg("а вы работаете с маркетплейсами?")
    state = _state()

    with (
        patch("apps.bot.flow.classify_intent", new=AsyncMock(return_value=IntentType.question)),
        patch("apps.bot.flow.answer_question", new=AsyncMock(return_value="Да, работаем.")),
    ):
        result = await process_turn(message, state, _session_factory(), _llm(), _rag(), STEP_MID)

    assert result is False
    assert message.answer.call_count == 2, (
        f"Expected 2 messages, got {message.answer.call_count}"
    )
    sent = [c.args[0] for c in message.answer.call_args_list]
    assert sent[0] == "Да, работаем.", "RAG reply must come first"
    assert sent[1] == STEP_MID.current_question, "Current question must be re-asked second"


@pytest.mark.asyncio
async def test_s2_question_does_not_advance_fsm_or_store_data() -> None:
    """S2: Pure question must leave FSM state, data, and DB unchanged."""
    message = _msg("есть ли кейсы в недвижимости?")
    state = _state()

    with (
        patch("apps.bot.flow.classify_intent", new=AsyncMock(return_value=IntentType.question)),
        patch("apps.bot.flow.answer_question", new=AsyncMock(return_value="Есть.")),
        patch("apps.bot.flow.add_message", new=AsyncMock()) as mock_add,
    ):
        await process_turn(message, state, _session_factory(), _llm(), _rag(), STEP_MID)

    state.set_state.assert_not_called()
    state.update_data.assert_not_called()
    mock_add.assert_not_called()


@pytest.mark.asyncio
async def test_s2_current_question_re_asked_exactly_once() -> None:
    """S2: Current question must appear in sent messages exactly once — never twice."""
    message = _msg("какие у вас гарантии результата?")
    state = _state()

    with (
        patch("apps.bot.flow.classify_intent", new=AsyncMock(return_value=IntentType.question)),
        patch("apps.bot.flow.answer_question", new=AsyncMock(return_value="Гарантии такие-то.")),
    ):
        await process_turn(message, state, _session_factory(), _llm(), _rag(), STEP_MID)

    count = sum(
        1
        for c in message.answer.call_args_list
        if c.args[0] == STEP_MID.current_question
    )
    assert count == 1, f"Expected current question sent exactly once, got {count}"


# ---------------------------------------------------------------------------
# S3: Compound "answer + embedded question"
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_s3_compound_sends_rag_then_next_question() -> None:
    """S3: Compound → exactly 2 messages: [RAG reply, next_question]. No stale current re-ask."""
    message = _msg("немедленно, а сколько стоит таргет?")
    state = _state()

    with (
        patch("apps.bot.flow.classify_intent", new=AsyncMock(return_value=IntentType.answer)),
        patch(
            "apps.bot.flow.answer_question",
            new=AsyncMock(return_value="Таргет от 30 000 ₽."),
        ),
    ):
        result = await process_turn(message, state, _session_factory(), _llm(), _rag(), STEP_MID)

    assert result is True
    sent = [c.args[0] for c in message.answer.call_args_list]
    assert len(sent) == 2, (
        f"Expected 2 messages (RAG + next_q), got {len(sent)}: {sent}"
    )
    assert sent[0] == "Таргет от 30 000 ₽.", "RAG reply must come first"
    assert sent[1] == STEP_MID.next_question, "Next question must come second"


@pytest.mark.asyncio
async def test_s3_compound_must_not_rereask_current_question() -> None:
    """S3: The CURRENT question must NOT appear in compound-path output (stale re-ask bug)."""
    message = _msg("50 000 рублей, а что входит в SMM?")
    state = _state()

    with (
        patch("apps.bot.flow.classify_intent", new=AsyncMock(return_value=IntentType.answer)),
        patch("apps.bot.flow.answer_question", new=AsyncMock(return_value="В SMM входит...")),
    ):
        await process_turn(message, state, _session_factory(), _llm(), _rag(), STEP_MID)

    sent = [c.args[0] for c in message.answer.call_args_list]
    assert STEP_MID.current_question not in sent, (
        f"Stale re-ask bug: current question appeared in output. Messages: {sent}"
    )


@pytest.mark.asyncio
async def test_s3_compound_advances_fsm_and_stores_full_text() -> None:
    """S3: FSM must advance and store the compound message text even when it has an embedded ?."""
    text = "работающий бизнес с выручкой, как давно вы на рынке?"
    message = _msg(text)
    state = _state()

    with (
        patch("apps.bot.flow.classify_intent", new=AsyncMock(return_value=IntentType.answer)),
        patch("apps.bot.flow.answer_question", new=AsyncMock(return_value="С 2018 года.")),
    ):
        result = await process_turn(message, state, _session_factory(), _llm(), _rag(), STEP_MID)

    assert result is True
    state.set_state.assert_awaited_once_with(STEP_MID.next_state)
    state.update_data.assert_awaited_once_with(budget=text)


@pytest.mark.asyncio
async def test_s3_short_trailing_question_mark_not_treated_as_compound() -> None:
    """S3 guard: '50 тысяч, ок?' has a <3-word question fragment — must NOT fire RAG."""
    message = _msg("50 тысяч, ок?")
    state = _state()

    with (
        patch("apps.bot.flow.classify_intent", new=AsyncMock(return_value=IntentType.answer)),
        patch("apps.bot.flow.answer_question", new=AsyncMock()) as mock_aq,
    ):
        await process_turn(message, state, _session_factory(), _llm(), _rag(), STEP_MID)

    mock_aq.assert_not_called()
    # Only next_question sent — no RAG message prepended
    message.answer.assert_awaited_once_with(STEP_MID.next_question)


# ---------------------------------------------------------------------------
# S4: Extra / unexpected message — duplicate guard
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_s4_answer_path_never_sends_current_question() -> None:
    """
    S4: On the ANSWER path, the current question must never be sent to the user.

    Rationale: without the per-user lock, two rapid messages could both enter the
    Q1 handler and both send the next question (duplicate). Within process_turn itself,
    the current question must never appear on the answer path, ensuring one call
    contributes exactly one next_question send.
    """
    for attempt in range(2):
        message = _msg(f"50 000 рублей (attempt {attempt})")
        state = _state()

        with (
            patch("apps.bot.flow.classify_intent", new=AsyncMock(return_value=IntentType.answer)),
            patch("apps.bot.flow.add_message", new=AsyncMock()),
        ):
            result = await process_turn(
                message, state, _session_factory(), _llm(), _rag(), STEP_MID
            )

        assert result is True
        sent = [c.args[0] for c in message.answer.call_args_list]
        assert STEP_MID.current_question not in sent, (
            f"Attempt {attempt}: current_question leaked onto ANSWER path. Sent: {sent}"
        )
        assert sent.count(STEP_MID.next_question) == 1, (
            f"Attempt {attempt}: next_question must appear exactly once. Sent: {sent}"
        )


@pytest.mark.asyncio
async def test_s4_no_rag_call_on_plain_answer() -> None:
    """S4: A plain answer without embedded question must never trigger a RAG call."""
    message = _msg("100 тысяч рублей в месяц")
    state = _state()

    with (
        patch("apps.bot.flow.classify_intent", new=AsyncMock(return_value=IntentType.answer)),
        patch("apps.bot.flow.add_message", new=AsyncMock()),
        patch("apps.bot.flow.answer_question", new=AsyncMock()) as mock_aq,
    ):
        await process_turn(message, state, _session_factory(), _llm(), _rag(), STEP_MID)

    mock_aq.assert_not_called()


# ---------------------------------------------------------------------------
# S5: Invalid / nonsensical answer — validator guards
#
# "привет" has letters (passes the empty guard) but no digit → digit validator rejects.
# Emoji-only has no alphanumeric content → early meaningful-input guard rejects.
# Both must return False with re-ask, no advance, nothing stored.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_s5_garbage_text_at_budget_step_expected_rereask() -> None:
    """
    S5: 'привет' at a budget step with digit validator → validator rejects, re-asks with
    clarification prefix. FSM must NOT advance, nothing stored.
    """
    message = _msg("привет")
    state = _state()

    with (
        patch("apps.bot.flow.classify_intent", new=AsyncMock(return_value=IntentType.answer)),
        patch("apps.bot.flow.add_message", new=AsyncMock()),
    ):
        result = await process_turn(
            message, state, _session_factory(), _llm(), _rag(), STEP_MID_BUDGET
        )

    assert result is False
    state.set_state.assert_not_called()
    state.update_data.assert_not_called()
    sent = [c.args[0] for c in message.answer.call_args_list]
    # Validator failure produces "Уточните, пожалуйста: <current_question>"
    assert len(sent) == 1
    assert STEP_MID_BUDGET.current_question in sent[0]
    assert sent[0].startswith("Уточните")


@pytest.mark.asyncio
async def test_s5_emoji_only_at_budget_step_expected_rereask() -> None:
    """
    S5: Emoji-only '😊👍' — caught by the early meaningful-input guard BEFORE classify_intent.
    Re-asks current question (plain, no prefix). classify_intent must NOT be called.
    """
    message = _msg("😊👍")
    state = _state()

    with (
        patch("apps.bot.flow.classify_intent", new=AsyncMock()) as mock_ci,
        patch("apps.bot.flow.add_message", new=AsyncMock()),
    ):
        result = await process_turn(
            message, state, _session_factory(), _llm(), _rag(), STEP_MID
        )

    assert result is False
    mock_ci.assert_not_called()  # early guard fires before LLM call
    state.set_state.assert_not_called()
    sent = [c.args[0] for c in message.answer.call_args_list]
    assert sent == [STEP_MID.current_question]


# ---------------------------------------------------------------------------
# S6: Two near-simultaneous messages — PerUserLockMiddleware
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_s6_same_user_messages_serialised() -> None:
    """
    S6: Two concurrent messages from the same user must be fully serialised.

    The per-user asyncio.Lock in PerUserLockMiddleware guarantees that message-2
    starts only after message-1's handler has returned. Without the lock, both
    could run concurrently and both send the next FSM question (duplicate).
    """
    middleware = PerUserLockMiddleware()
    log: list[str] = []

    async def slow_handler(event: Any, data: dict[str, Any]) -> None:
        log.append("start")
        await asyncio.sleep(0.01)  # yields the event loop — exposes races without lock
        log.append("end")

    def _event(uid: int) -> MagicMock:
        ev = MagicMock()
        ev.from_user = MagicMock()
        ev.from_user.id = uid
        return ev

    e1, e2 = _event(99), _event(99)
    await asyncio.gather(
        middleware(slow_handler, e1, {}),
        middleware(slow_handler, e2, {}),
    )

    assert log == ["start", "end", "start", "end"], (
        f"S6 FAIL: same-user messages not serialised. Execution log: {log}"
    )


@pytest.mark.asyncio
async def test_s6_different_users_not_blocked_by_each_other() -> None:
    """S6: Messages from DIFFERENT users must execute concurrently (no cross-user blocking)."""
    middleware = PerUserLockMiddleware()
    log: list[str] = []
    barrier = asyncio.Event()

    async def handler(event: Any, data: dict[str, Any]) -> None:
        log.append(f"start:{event.from_user.id}")
        await barrier.wait()  # both must reach this point concurrently
        log.append(f"end:{event.from_user.id}")

    def _event(uid: int) -> MagicMock:
        ev = MagicMock()
        ev.from_user = MagicMock()
        ev.from_user.id = uid
        return ev

    e1, e2 = _event(1), _event(2)

    t1 = asyncio.create_task(middleware(handler, e1, {}))
    t2 = asyncio.create_task(middleware(handler, e2, {}))
    await asyncio.sleep(0.01)  # give both tasks time to reach the barrier
    barrier.set()
    await asyncio.gather(t1, t2)

    # Both "start" entries appear before any "end" → true concurrent execution
    start_positions = [i for i, e in enumerate(log) if e.startswith("start")]
    end_positions = [i for i, e in enumerate(log) if e.startswith("end")]
    assert len(start_positions) == 2 and len(end_positions) == 2
    assert max(start_positions) < min(end_positions), (
        f"S6 FAIL: different users blocked each other. Log: {log}"
    )


# ---------------------------------------------------------------------------
# S7: Question after FSM has finished (StateFilter(None) → handle_no_state)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_s7_question_after_fsm_sends_rag_then_start_nudge() -> None:
    """S7: Question with no active FSM state → RAG answer first, then /start nudge."""
    message = _msg("можно ли заказать только SEO без таргета?")

    with (
        patch(
            "apps.bot.handlers.fallback.classify_intent",
            new=AsyncMock(return_value=IntentType.question),
        ),
        patch(
            "apps.bot.handlers.fallback.answer_question",
            new=AsyncMock(return_value="Да, SEO можно заказать отдельно."),
        ),
    ):
        await handle_no_state(message, _llm(), _rag())

    assert message.answer.call_count == 2, (
        f"Expected 2 messages, got {message.answer.call_count}"
    )
    sent = [c.args[0] for c in message.answer.call_args_list]
    assert sent[0] == "Да, SEO можно заказать отдельно.", "RAG reply must come first"
    assert "/start" in sent[1], f"Second message must contain /start nudge, got: {sent[1]!r}"


@pytest.mark.asyncio
async def test_s7_non_question_after_fsm_sends_only_start_nudge() -> None:
    """S7: Non-question with no active FSM state → ONLY /start nudge, no RAG call."""
    message = _msg("хочу заказать продвижение")

    with (
        patch(
            "apps.bot.handlers.fallback.classify_intent",
            new=AsyncMock(return_value=IntentType.answer),
        ),
        patch(
            "apps.bot.handlers.fallback.answer_question",
            new=AsyncMock(),
        ) as mock_aq,
    ):
        await handle_no_state(message, _llm(), _rag())

    mock_aq.assert_not_called()
    message.answer.assert_awaited_once()
    assert "/start" in message.answer.call_args.args[0]


# ---------------------------------------------------------------------------
# S8: Garbage / emoji / empty message
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_s8_empty_string_does_not_crash() -> None:
    """S8: Empty text must not raise; documents that process_turn is crash-safe."""
    message = _msg("")
    message.text = ""
    state = _state()

    with (
        patch("apps.bot.flow.classify_intent", new=AsyncMock(return_value=IntentType.answer)),
        patch("apps.bot.flow.add_message", new=AsyncMock()),
    ):
        result = await process_turn(
            message, state, _session_factory(), _llm(), _rag(), STEP_MID
        )

    assert isinstance(result, bool)


@pytest.mark.asyncio
async def test_s8_none_text_does_not_crash() -> None:
    """S8: message.text = None must not crash (coerced to empty string by flow)."""
    message = MagicMock()
    message.text = None
    message.answer = AsyncMock()
    state = _state()

    with (
        patch("apps.bot.flow.classify_intent", new=AsyncMock(return_value=IntentType.answer)),
        patch("apps.bot.flow.add_message", new=AsyncMock()),
    ):
        result = await process_turn(
            message, state, _session_factory(), _llm(), _rag(), STEP_MID
        )

    assert isinstance(result, bool)


@pytest.mark.asyncio
async def test_s8_emoji_only_does_not_crash() -> None:
    """S8: Emoji-only message must not crash at any FSM step."""
    message = _msg("😂🔥💯")
    state = _state()

    with (
        patch("apps.bot.flow.classify_intent", new=AsyncMock(return_value=IntentType.answer)),
        patch("apps.bot.flow.add_message", new=AsyncMock()),
    ):
        result = await process_turn(
            message, state, _session_factory(), _llm(), _rag(), STEP_MID
        )

    assert isinstance(result, bool)


@pytest.mark.asyncio
async def test_s8_empty_message_gentle_rereask() -> None:
    """
    S8: Empty message hits the early meaningful-input guard — no LLM call, no advance,
    current question re-asked (plain, no clarification prefix).
    """
    message = _msg("")
    message.text = ""
    state = _state()

    with (
        patch("apps.bot.flow.classify_intent", new=AsyncMock()) as mock_ci,
        patch("apps.bot.flow.add_message", new=AsyncMock()),
    ):
        result = await process_turn(
            message, state, _session_factory(), _llm(), _rag(), STEP_MID
        )

    assert result is False
    mock_ci.assert_not_called()
    state.set_state.assert_not_called()
    sent = [c.args[0] for c in message.answer.call_args_list]
    assert sent == [STEP_MID.current_question]
