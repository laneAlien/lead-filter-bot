"""Tests for PerUserLockMiddleware — per-user message serialization."""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import MagicMock

import pytest

from apps.bot.middleware.user_lock import PerUserLockMiddleware


def _make_message(user_id: int) -> MagicMock:
    msg = MagicMock()
    msg.from_user = MagicMock()
    msg.from_user.id = user_id
    return msg


async def _handler(event: Any, data: dict[str, Any]) -> str:
    """Trivial handler stub — real handlers are tested elsewhere."""
    return "ok"


@pytest.mark.asyncio
async def test_same_user_serialized() -> None:
    """Two messages from the same user are processed strictly sequentially."""
    middleware = PerUserLockMiddleware()
    order: list[str] = []

    async def slow_handler(event: Any, data: dict[str, Any]) -> None:
        order.append("A-start")
        await asyncio.sleep(0.05)  # simulate slow RAG
        order.append("A-end")

    async def fast_handler(event: Any, data: dict[str, Any]) -> None:
        order.append("B-start")
        order.append("B-end")

    msg_a = _make_message(user_id=42)
    msg_b = _make_message(user_id=42)

    task_a = asyncio.create_task(middleware(slow_handler, msg_a, {}))
    await asyncio.sleep(0)  # let task_a acquire the lock first
    task_b = asyncio.create_task(middleware(fast_handler, msg_b, {}))

    await asyncio.gather(task_a, task_b)

    # B must start only after A fully finishes — no interleaving
    assert order == ["A-start", "A-end", "B-start", "B-end"]


@pytest.mark.asyncio
async def test_different_users_not_blocked() -> None:
    """A slow handler for user A does not delay user B (per-user, not global)."""
    middleware = PerUserLockMiddleware()
    finished: list[int] = []

    async def slow_handler(event: Any, data: dict[str, Any]) -> None:
        await asyncio.sleep(0.05)
        finished.append(event.from_user.id)

    msg_a = _make_message(user_id=1)
    msg_b = _make_message(user_id=2)

    # Fire both concurrently — user 2 should finish before user 1 if truly independent
    task_a = asyncio.create_task(middleware(slow_handler, msg_a, {}))
    task_b = asyncio.create_task(middleware(slow_handler, msg_b, {}))

    await asyncio.gather(task_a, task_b)

    # Both finished — neither was blocked by the other
    assert set(finished) == {1, 2}


@pytest.mark.asyncio
async def test_non_message_event_passes_through() -> None:
    """Non-Message events (CallbackQuery etc.) bypass the lock entirely."""
    middleware = PerUserLockMiddleware()
    called = False

    async def handler(event: Any, data: dict[str, Any]) -> None:
        nonlocal called
        called = True

    # Not a Message — pass a plain object
    await middleware(handler, MagicMock(spec=[]), {})
    assert called
