import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.redis import RedisStorage

from apps.bot.handlers import dialogue, fallback, start
from apps.bot.middleware.user_lock import PerUserLockMiddleware
from core.config import get_settings
from core.db import get_sessionmaker
from core.llm import LLMClient
from core.rag import RagClient

logger = logging.getLogger(__name__)


async def _run() -> None:
    settings = get_settings()
    logging.basicConfig(level=settings.log_level.upper())

    bot = Bot(token=settings.telegram_bot_token)
    dp = Dispatcher(storage=RedisStorage.from_url(settings.redis_url))

    dp.message.middleware(PerUserLockMiddleware())

    dp.include_router(start.router)
    dp.include_router(dialogue.router)
    dp.include_router(fallback.router)

    dp.workflow_data.update(
        session_factory=get_sessionmaker(),
        llm=LLMClient(),
        rag=RagClient(),
    )

    logger.info("Starting bot polling...")
    await dp.start_polling(bot)


def main() -> None:
    asyncio.run(_run())


if __name__ == "__main__":
    main()
