from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.models import Conversation, Message, User
from core.prompts.qualifier import QUALIFIER_SYSTEM_PROMPT
from core.schemas import (
    AgencyExperience,
    BusinessStage,
    NextStep,
    QualifierVerdict,
    ServiceType,
    Urgency,
)
from core.services.conversation import (
    add_message,
    finalize_conversation,
    generate_verdict,
    get_conversation_messages,
    get_or_create_user,
    start_conversation,
)

SAMPLE_VERDICT = QualifierVerdict(
    qualified=True,
    budget_rub_monthly=50000,
    service_type=ServiceType.smm,
    business_stage=BusinessStage.working,
    urgency=Urgency.immediate,
    agency_experience=AgencyExperience.none,
    reasoning="Все критерии выполнены.",
    next_step=NextStep.book_call,
)


@pytest.mark.asyncio
async def test_get_or_create_user_creates_new(db_session: AsyncSession) -> None:
    user = await get_or_create_user(db_session, telegram_id=111, username="alice")

    count = await db_session.scalar(select(func.count()).select_from(User))
    assert count == 1
    assert user.telegram_id == 111
    assert user.username == "alice"
    assert user.id is not None


@pytest.mark.asyncio
async def test_get_or_create_user_returns_existing(db_session: AsyncSession) -> None:
    first = await get_or_create_user(db_session, telegram_id=222, username="bob")
    second = await get_or_create_user(db_session, telegram_id=222, username="bob_updated")

    count = await db_session.scalar(select(func.count()).select_from(User))
    assert count == 1
    assert first.id == second.id


@pytest.mark.asyncio
async def test_start_conversation_links_to_user(db_session: AsyncSession) -> None:
    user = await get_or_create_user(db_session, telegram_id=333, username=None)
    conv = await start_conversation(db_session, user)

    assert conv.id is not None
    assert conv.user_id == user.id
    assert conv.started_at is not None
    assert conv.finished_at is None
    assert conv.qualified is None


@pytest.mark.asyncio
async def test_add_and_retrieve_messages(db_session: AsyncSession) -> None:
    user = await get_or_create_user(db_session, telegram_id=444, username=None)
    conv = await start_conversation(db_session, user)

    await add_message(db_session, conv.id, "assistant", "Привет!")
    await add_message(db_session, conv.id, "user", "Здравствуйте")
    await add_message(db_session, conv.id, "assistant", "Какой бюджет?")

    messages = await get_conversation_messages(db_session, conv.id)

    assert len(messages) == 3
    assert messages[0].role == "assistant"
    assert messages[0].content == "Привет!"
    assert messages[1].role == "user"
    assert messages[2].content == "Какой бюджет?"


@pytest.mark.asyncio
async def test_generate_verdict_mocks_llm() -> None:
    mock_llm = MagicMock()
    mock_llm.chat_structured = AsyncMock(return_value=SAMPLE_VERDICT)

    summary = "1. Бюджет: 50000\n2. Тип: smm"

    with patch("core.services.conversation.LLMClient", return_value=mock_llm):
        verdict = await generate_verdict(mock_llm, summary)

    assert verdict.qualified is True
    assert verdict.next_step == NextStep.book_call

    call_args = mock_llm.chat_structured.call_args
    messages = call_args.args[0]
    assert messages[0]["role"] == "system"
    assert messages[0]["content"] == QUALIFIER_SYSTEM_PROMPT
    assert messages[1]["role"] == "user"
    assert messages[1]["content"] == summary


@pytest.mark.asyncio
async def test_finalize_conversation_persists_verdict(db_session: AsyncSession) -> None:
    user = await get_or_create_user(db_session, telegram_id=555, username=None)
    conv = await start_conversation(db_session, user)

    await finalize_conversation(db_session, conv.id, SAMPLE_VERDICT)

    result = await db_session.execute(select(Conversation).where(Conversation.id == conv.id))
    updated = result.scalar_one()

    assert updated.verdict_json is not None
    assert updated.qualified == SAMPLE_VERDICT.qualified
    assert updated.finished_at is not None
    # Regression guard: finalize must commit a timezone-aware datetime without
    # raising. A naive TIMESTAMP column made asyncpg raise DataError here, which
    # silently hung the dialogue on "Анализирую...".
    assert updated.finished_at.tzinfo is not None


def test_timestamp_columns_are_timezone_aware() -> None:
    """All timestamp columns must be timezone-aware (TIMESTAMP WITH TIME ZONE).

    The code writes tz-aware ``datetime.now(UTC)``; naive columns make asyncpg
    raise DataError on commit. This pins the schema side of that contract.
    """
    columns = [
        User.__table__.c.created_at,
        Conversation.__table__.c.started_at,
        Conversation.__table__.c.finished_at,
        Message.__table__.c.created_at,
    ]
    for column in columns:
        assert column.type.timezone is True, f"{column} must be timezone-aware"
