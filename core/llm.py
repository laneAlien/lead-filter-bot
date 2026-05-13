import json
import logging

from openai import APIConnectionError, AsyncOpenAI, RateLimitError
from openai.types.chat import ChatCompletionMessageParam
from openai.types.shared_params import ResponseFormatJSONObject
from pydantic import BaseModel

from core.config import get_settings

logger = logging.getLogger(__name__)


class LLMClient:
    def __init__(self) -> None:
        settings = get_settings()
        self._client = AsyncOpenAI(
            api_key=settings.deepseek_api_key,
            base_url=settings.deepseek_base_url,
        )
        self._model = settings.deepseek_model

    async def chat(
        self,
        messages: list[ChatCompletionMessageParam],
        temperature: float = 0.3,
        max_tokens: int = 1500,
    ) -> str:
        """Send a chat request and return the assistant's text response."""
        response = await self._client.chat.completions.create(
            model=self._model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        usage = response.usage
        if usage:
            logger.info(
                "DeepSeek tokens — prompt: %d, completion: %d, total: %d",
                usage.prompt_tokens,
                usage.completion_tokens,
                usage.total_tokens,
            )
        return response.choices[0].message.content or ""

    async def chat_structured[T: BaseModel](
        self,
        messages: list[ChatCompletionMessageParam],
        response_schema: type[T],
        temperature: float = 0.3,
        max_tokens: int = 1500,
    ) -> T:
        """Send a chat request and parse the JSON response into a Pydantic model."""
        response = await self._client.chat.completions.create(
            model=self._model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            response_format=ResponseFormatJSONObject(type="json_object"),
        )
        usage = response.usage
        if usage:
            logger.info(
                "DeepSeek tokens — prompt: %d, completion: %d, total: %d",
                usage.prompt_tokens,
                usage.completion_tokens,
                usage.total_tokens,
            )
        raw = response.choices[0].message.content or "{}"
        data = json.loads(raw)
        return response_schema.model_validate(data)


__all__ = ["APIConnectionError", "LLMClient", "RateLimitError"]
