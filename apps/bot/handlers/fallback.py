"""Fallback handler: text messages arriving with no active FSM state."""

import logging

from aiogram import Router
from aiogram.filters import StateFilter
from aiogram.types import Message

from core.llm import LLMClient
from core.prompts.rag_answer import answer_question
from core.rag import RagClient
from core.schemas import IntentType
from core.services.intent import classify_intent

logger = logging.getLogger(__name__)

router = Router()

_START_NUDGE = "Чтобы начать новую заявку, напишите /start."


@router.message(StateFilter(None))
async def handle_no_state(
    message: Message,
    llm: LLMClient,
    rag: RagClient,
) -> None:
    """
    Questions → RAG answer from kontur_kb + /start nudge.
    Everything else → /start nudge only.
    """
    text = message.text or ""
    if not text:
        return

    intent = await classify_intent(llm, current_question="", user_message=text)
    if intent == IntentType.question:
        rag_reply = await answer_question(llm, rag, text)
        await message.answer(rag_reply)
        logger.info("no-state QUESTION: answered via RAG")
    else:
        logger.info("no-state non-question: nudging to /start")

    await message.answer(_START_NUDGE)
