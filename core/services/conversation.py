import logging
from datetime import UTC, datetime

from openai.types.chat import ChatCompletionMessageParam
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.llm import LLMClient
from core.models import Conversation, Message, User
from core.prompts.qualifier import QUALIFIER_SYSTEM_PROMPT
from core.schemas import QualifierVerdict

logger = logging.getLogger(__name__)


async def get_or_create_user(
    session: AsyncSession,
    telegram_id: int,
    username: str | None,
) -> User:
    result = await session.execute(select(User).where(User.telegram_id == telegram_id))
    user = result.scalar_one_or_none()
    if user is None:
        user = User(telegram_id=telegram_id, username=username)
        session.add(user)
        await session.commit()
        await session.refresh(user)
        logger.info("Created new user telegram_id=%d", telegram_id)
    return user


async def start_conversation(
    session: AsyncSession,
    user: User,
) -> Conversation:
    conv = Conversation(user_id=user.id)
    session.add(conv)
    await session.commit()
    await session.refresh(conv)
    logger.info("Started conversation id=%d for user id=%d", conv.id, user.id)
    return conv


async def add_message(
    session: AsyncSession,
    conversation_id: int,
    role: str,
    content: str,
) -> Message:
    msg = Message(conversation_id=conversation_id, role=role, content=content)
    session.add(msg)
    await session.commit()
    await session.refresh(msg)
    return msg


async def get_conversation_messages(
    session: AsyncSession,
    conversation_id: int,
) -> list[Message]:
    result = await session.execute(
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.asc())
    )
    return list(result.scalars().all())


async def generate_verdict(
    llm: LLMClient,
    dialogue_summary: str,
) -> QualifierVerdict:
    messages: list[ChatCompletionMessageParam] = [
        {"role": "system", "content": QUALIFIER_SYSTEM_PROMPT},
        {"role": "user", "content": dialogue_summary},
    ]
    verdict = await llm.chat_structured(messages, QualifierVerdict)
    logger.info(
        "Verdict generated: qualified=%s next_step=%s", verdict.qualified, verdict.next_step
    )
    return verdict


async def finalize_conversation(
    session: AsyncSession,
    conversation_id: int,
    verdict: QualifierVerdict,
) -> None:
    result = await session.execute(select(Conversation).where(Conversation.id == conversation_id))
    conv = result.scalar_one()
    conv.verdict_json = verdict.model_dump()
    conv.qualified = verdict.qualified
    conv.finished_at = datetime.now(UTC)
    await session.commit()
    logger.info("Finalized conversation id=%d qualified=%s", conversation_id, verdict.qualified)
