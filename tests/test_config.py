import pytest

from core.config import Settings, get_settings


def test_settings_loads_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test-123")
    monkeypatch.setenv("ENV", "test")
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")

    get_settings.cache_clear()
    s = Settings()

    assert s.deepseek_api_key == "sk-test-123"
    assert s.env == "test"
    assert s.log_level == "DEBUG"


def test_settings_defaults() -> None:
    get_settings.cache_clear()
    # Minimal env — check defaults hold when vars are absent
    s = Settings(deepseek_api_key="x", telegram_bot_token="x")

    assert s.deepseek_base_url == "https://api.deepseek.com"
    assert s.deepseek_model == "deepseek-chat"
    assert s.env == "development"


def test_get_settings_is_singleton(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DEEPSEEK_API_KEY", "singleton-test")
    get_settings.cache_clear()

    s1 = get_settings()
    s2 = get_settings()

    assert s1 is s2
