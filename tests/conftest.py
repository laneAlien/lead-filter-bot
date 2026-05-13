import pytest

from core.config import Settings, get_settings


@pytest.fixture
def settings_test(monkeypatch: pytest.MonkeyPatch) -> Settings:
    """Override settings with safe test values (no real API keys needed)."""
    test_settings = Settings(
        deepseek_api_key="test-key",
        deepseek_base_url="https://api.deepseek.com",
        deepseek_model="deepseek-chat",
        telegram_bot_token="0000000000:test-token",
        database_url="sqlite+aiosqlite:///./test.db",
        log_level="WARNING",
        env="test",
    )
    monkeypatch.setattr("core.config.get_settings", lambda: test_settings)
    get_settings.cache_clear()
    return test_settings


@pytest.fixture(autouse=True)
def _clear_caches() -> None:
    from core.config import get_settings
    from core.db import get_engine, get_sessionmaker

    get_settings.cache_clear()
    get_engine.cache_clear()
    get_sessionmaker.cache_clear()
