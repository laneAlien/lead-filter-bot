"""Per-user message serialization: one message at a time per user."""

import asyncio
from collections import defaultdict
from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject


class PerUserLockMiddleware(BaseMiddleware):
    """
    Serializes message handling per user so that two rapid messages from the
    same user never run concurrently — eliminating FSM state races where a slow
    RAG call and a fast ANSWER processing can interleave and produce stale
    question re-asks or corrupted FSM data.

    Per-user (not global): a slow RAG for user A does not block user B.

    Registered on dp.message so every event is a Message; we use getattr so
    channel posts (from_user=None) pass through without locking.

    Lock-dict growth: defaultdict is unbounded; for a low-traffic pilot this is
    acceptable (each Lock is ~200 bytes; 10 000 users ≈ 2 MB). Add eviction when
    traffic warrants it.
    """

    def __init__(self) -> None:
        self._locks: dict[int, asyncio.Lock] = defaultdict(asyncio.Lock)

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        from_user = getattr(event, "from_user", None)
        user_id: int | None = getattr(from_user, "id", None)
        if user_id is None:
            return await handler(event, data)
        async with self._locks[user_id]:
            return await handler(event, data)
