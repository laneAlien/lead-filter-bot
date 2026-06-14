"""Shared per-turn FSM flow: intent classification → RAG or advance."""

from __future__ import annotations

import logging
import re
from collections.abc import Callable
from dataclasses import dataclass, field

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
# Any Latin/Cyrillic letter or ASCII digit — used to gate non-meaningful input early.
_MEANINGFUL_RE = re.compile(r"[a-zA-Zа-яА-ЯёЁ0-9]")


def _has_embedded_question(text: str) -> bool:
    """Return True if text contains a real embedded question (≥3-word fragment ending with ?)."""
    if "?" not in text:
        return False
    parts = _QUESTION_SPLITTER.split(text)
    return any(len(p.strip().split()) >= 3 for p in parts if "?" in p)


def _is_meaningful(text: str) -> bool:
    """Return True if text contains at least one letter or digit (not pure emoji/punctuation)."""
    return bool(_MEANINGFUL_RE.search(text))


@dataclass(frozen=True)
class StepConfig:
    current_question: str
    data_key: str
    next_state: State | None
    next_question: str | None
    # Optional per-step validator: returns True when the answer is plausible for this step.
    # Called only on the ANSWER path, after intent classification. None = accept everything.
    validator: Callable[[str], bool] | None = field(default=None, compare=False)


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
    Returns False → user asked a QUESTION (or input was rejected); state unchanged.
    """
    text = message.text or ""

    # Early guard: empty / whitespace-only / emoji-punctuation-only input.
    # No LLM call — re-ask the current question immediately.
    if not _is_meaningful(text):
        await message.answer(step.current_question)
        logger.info("Non-meaningful input — re-asked current question (key=%s)", step.data_key)
        return False

    intent = await classify_intent(llm, step.current_question, text)

    if intent == IntentType.question:
        rag_reply = await answer_question(llm, rag, text)
        await message.answer(rag_reply)
        await message.answer(step.current_question)
        logger.info("Intent=QUESTION — answered from RAG, re-asked current question")
        return False

    # ANSWER path — validate, then store and advance.
    if step.validator is not None and not step.validator(text):
        await message.answer(f"Уточните, пожалуйста: {step.current_question}")
        logger.info("Validator rejected answer for key=%s — re-asked", step.data_key)
        return False

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
