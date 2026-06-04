import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from core.config import Settings, get_settings
from core.models import Base


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
        qdrant_url="http://localhost:6333",
        qdrant_collection="test_kb",
        embedding_model="intfloat/multilingual-e5-small",
        rag_top_k=4,
        rag_score_threshold=0.0,
    )
    monkeypatch.setattr("core.config.get_settings", lambda: test_settings)
    get_settings.cache_clear()
    return test_settings


@pytest.fixture(autouse=True)
def _clear_caches() -> None:
    from core.config import get_settings
    from core.db import get_engine, get_sessionmaker
    from core.rag import get_embedder

    get_settings.cache_clear()
    get_engine.cache_clear()
    get_sessionmaker.cache_clear()
    get_embedder.cache_clear()


@pytest_asyncio.fixture
async def db_session() -> AsyncSession:  # type: ignore[misc]
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as session:
        yield session
    await engine.dispose()
