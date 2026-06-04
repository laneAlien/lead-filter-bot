"""RAG-answer prompt and answer_question helper."""

import logging

from openai.types.chat import ChatCompletionMessageParam

from core.llm import LLMClient
from core.rag import RagClient

logger = logging.getLogger(__name__)

_FALLBACK = "Менеджер уточнит этот вопрос на звонке — я не хочу давать неточную информацию."

RAG_SYSTEM_PROMPT = """\
Ты — ассистент digital-агентства «Контур Digital».
Отвечай на вопросы клиента коротко и по-деловому, используя ТОЛЬКО предоставленный контекст.
Если ответа в контексте нет — скажи, что менеджер уточнит на звонке, и не придумывай.
Никаких обещаний по конкретным цифрам и срокам за пределами контекста.\
"""


async def answer_question(llm: LLMClient, rag: RagClient, user_message: str) -> str:
    """Retrieve context from Qdrant and generate a grounded answer."""
    chunks = await rag.search(user_message)

    if not chunks:
        logger.info("RAG: no chunks for query, returning fallback")
        return _FALLBACK

    context_parts = [f"[{i + 1}] {chunk.content}" for i, chunk in enumerate(chunks)]
    context = "\n\n".join(context_parts)

    messages: list[ChatCompletionMessageParam] = [
        {"role": "system", "content": RAG_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": (
                f"Контекст из базы знаний агентства:\n\n{context}\n\nВопрос клиента: {user_message}"
            ),
        },
    ]
    return await llm.chat(messages, temperature=0.2, max_tokens=300)
