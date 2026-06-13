"""Shared per-turn FSM flow: intent classification → RAG or advance."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass

from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from core.llm import LLMClient
from core.prompts.rag_answer import answer_question
from core.rag import RagClient
from core.schemas import IntentType
from core.services.conversation import add_message
from core.services.intent import classify_intent

logger = logging.getLogger(__name__)

_QUESTION_SPLITTER = re.compile(r"[,;.!]\s*")


def _has_embedded_question(text: str) -> bool:
    """Return True if text contains a real embedded question (≥3-word fragment ending with ?)."""
    if "?" not in text:
        return False
    parts = _QUESTION_SPLITTER.split(text)
    return any(len(p.strip().split()) >= 3 for p in parts if "?" in p)


@dataclass(frozen=True)
class StepConfig:
    current_question: str
    data_key: str
    next_state: State | None
    next_question: str | None


async def process_turn(
    message: Message,
    state: FSMContext,
    session_factory: async_sessionmaker[AsyncSession],
    llm: LLMClient,
    rag: RagClient,
    step: StepConfig,
) -> bool:
    """
    Route one FSM turn through intent classification.

    Returns True  → user gave an ANSWER; message stored, data updated, state advanced.
    Returns False → user asked a QUESTION; RAG reply + re-ask sent, state unchanged.
    """
    text = message.text or ""
    intent = await classify_intent(llm, step.current_question, text)

    if intent == IntentType.question:
        rag_reply = await answer_question(llm, rag, text)
        await message.answer(rag_reply)
        await message.answer(step.current_question)
        logger.info("Intent=QUESTION — answered from RAG, re-asked current question")
        return False

    # ANSWER path — store and advance
    data = await state.get_data()
    conv_id: int = data["conversation_id"]

    async with session_factory() as session:
        await add_message(session, conv_id, "user", text)
        if step.next_question is not None:
            await add_message(session, conv_id, "assistant", step.next_question)

    await state.update_data(**{step.data_key: text})

    # Compound message: if the answer also contains a real embedded question, answer it via RAG
    # before the next FSM question so the FSM prompt is the last thing the user sees.
    if _has_embedded_question(text):
        rag_reply = await answer_question(llm, rag, text)
        await message.answer(rag_reply)
        logger.info("compound: answered embedded question via RAG")

    if step.next_state is not None and step.next_question is not None:
        await state.set_state(step.next_state)
        await message.answer(step.next_question)

    logger.info("Intent=ANSWER — stored key=%s, advanced to %s", step.data_key, step.next_state)
    return True
