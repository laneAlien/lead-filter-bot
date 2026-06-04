"""Intent classifier: QUESTION vs ANSWER routing for the qualification FSM."""

import logging

from openai.types.chat import ChatCompletionMessageParam

from core.llm import LLMClient
from core.prompts.intent import INTENT_SYSTEM_PROMPT, INTENT_USER_TEMPLATE
from core.schemas import IntentResult, IntentType

logger = logging.getLogger(__name__)


async def classify_intent(
    llm: LLMClient,
    current_question: str,
    user_message: str,
) -> IntentType:
    """
    Classify whether the user message is a QUESTION to the agency or an ANSWER to the FSM.
    Fails safe to ANSWER on any error so the funnel is never blocked.
    """
    messages: list[ChatCompletionMessageParam] = [
        {"role": "system", "content": INTENT_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": INTENT_USER_TEMPLATE.format(
                current_question=current_question,
                user_message=user_message,
            ),
        },
    ]
    try:
        result = await llm.chat_structured(
            messages,
            IntentResult,
            temperature=0.0,
            max_tokens=20,
        )
        return result.intent
    except Exception as exc:
        logger.warning("Intent classification failed, defaulting to ANSWER: %s", exc)
        return IntentType.answer
