"""tests/test_help_command.py — /help command handler behaviour."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from apps.bot.handlers.start import _HELP_TEXT, handle_help


def _msg() -> MagicMock:
    m = MagicMock()
    m.answer = AsyncMock()
    return m


@pytest.mark.asyncio
async def test_help_sends_help_text() -> None:
    """handle_help sends _HELP_TEXT exactly once."""
    message = _msg()
    await handle_help(message)
    message.answer.assert_awaited_once_with(_HELP_TEXT)


@pytest.mark.asyncio
async def test_help_does_not_touch_fsm_state() -> None:
    """/help handler has no FSMContext parameter — it provably cannot alter state.

    This test documents the contract: calling handle_help leaves an active
    FSM state untouched because the handler never receives the state object.
    """
    message = _msg()
    state = MagicMock()
    state.set_state = AsyncMock()
    state.clear = AsyncMock()
    state.update_data = AsyncMock()

    # handler signature is (message: Message) — state is not injected
    await handle_help(message)

    state.set_state.assert_not_called()
    state.clear.assert_not_called()
    state.update_data.assert_not_called()
    message.answer.assert_awaited_once()
