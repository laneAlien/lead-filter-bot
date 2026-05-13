from collections.abc import AsyncGenerator
from functools import lru_cache

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from core.config import get_settings
from core.models import Base


@lru_cache
def get_engine() -> AsyncEngine:
    return create_async_engine(get_settings().database_url, echo=False)


@lru_cache
def get_sessionmaker() -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(get_engine(), expire_on_commit=False)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with get_sessionmaker()() as session:
        yield session


async def init_db() -> None:
    """Create all tables — used for tests and first-run only.

    For production and dev, use `alembic upgrade head` instead (Phase 2+).
    """
    async with get_engine().begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
