from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.llm import LLMClient
from core.schemas import QualifierVerdict


def _make_mock_response(content: str) -> MagicMock:
    choice = MagicMock()
    choice.message.content = content

    usage = MagicMock()
    usage.prompt_tokens = 10
    usage.completion_tokens = 20
    usage.total_tokens = 30

    response = MagicMock()
    response.choices = [choice]
    response.usage = usage
    return response


@pytest.fixture
def llm_client(settings_test: object) -> LLMClient:
    with patch("core.llm.get_settings") as mock_get_settings:
        mock_get_settings.return_value = MagicMock(
            deepseek_api_key="test-key",
            deepseek_base_url="https://api.deepseek.com",
            deepseek_model="deepseek-chat",
        )
        return LLMClient()


@pytest.mark.asyncio
async def test_chat_returns_string(llm_client: LLMClient) -> None:
    mock_response = _make_mock_response("Привет! Как могу помочь?")

    with patch.object(
        llm_client._client.chat.completions,
        "create",
        new_callable=AsyncMock,
        return_value=mock_response,
    ):
        result = await llm_client.chat([{"role": "user", "content": "Привет"}])

    assert result == "Привет! Как могу помочь?"


@pytest.mark.asyncio
async def test_chat_passes_temperature_and_max_tokens(llm_client: LLMClient) -> None:
    mock_response = _make_mock_response("OK")
    create_mock = AsyncMock(return_value=mock_response)

    with patch.object(llm_client._client.chat.completions, "create", new=create_mock):
        await llm_client.chat(
            [{"role": "user", "content": "test"}],
            temperature=0.7,
            max_tokens=500,
        )

    call_kwargs = create_mock.call_args.kwargs
    assert call_kwargs["temperature"] == 0.7
    assert call_kwargs["max_tokens"] == 500


@pytest.mark.asyncio
async def test_chat_structured_parses_verdict(llm_client: LLMClient) -> None:
    verdict_json = """{
        "qualified": true,
        "budget_rub_monthly": 50000,
        "service_type": "smm",
        "business_stage": "working",
        "urgency": "immediate",
        "agency_experience": "none",
        "reasoning": "Бюджет и стадия бизнеса соответствуют критериям.",
        "next_step": "book_call"
    }"""
    mock_response = _make_mock_response(verdict_json)

    with patch.object(
        llm_client._client.chat.completions,
        "create",
        new_callable=AsyncMock,
        return_value=mock_response,
    ):
        verdict = await llm_client.chat_structured(
            [{"role": "user", "content": "..."}],
            QualifierVerdict,
        )

    assert verdict.qualified is True
    assert verdict.budget_rub_monthly == 50000
    assert verdict.next_step.value == "book_call"
