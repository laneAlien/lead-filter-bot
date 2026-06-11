import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.redis import RedisStorage

from apps.bot.handlers import dialogue, start
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

    dp.include_router(start.router)
    dp.include_router(dialogue.router)

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
