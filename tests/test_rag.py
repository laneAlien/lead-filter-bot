"""Tests for core/rag.py — mocks both embedder and Qdrant, never hits real services."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.rag import RagClient, embed_passages, embed_query
from core.schemas import RagChunk


def _make_scored_point(content: str, source: str, score: float) -> MagicMock:
    point = MagicMock()
    point.payload = {"content": content, "source": source}
    point.score = score
    return point


def _mock_embedder_ctx(vectors: list[list[float]]) -> tuple[MagicMock, MagicMock]:
    """Returns (mock_get_embedder patcher, mock_embedder) — caller must use as context manager."""
    mock_embedder = MagicMock()
    enc_result = MagicMock()
    enc_result.tolist.return_value = vectors
    mock_embedder.encode.return_value = enc_result
    return mock_embedder


# ---------------------------------------------------------------------------
# Embedder prefix tests (mock the underlying SentenceTransformer)
# ---------------------------------------------------------------------------


def test_embed_query_adds_query_prefix() -> None:
    captured: list[list[str]] = []

    def fake_encode(texts: list[str], **_kwargs: object) -> MagicMock:
        captured.append(texts)
        result = MagicMock()
        result.tolist.return_value = [[0.1] * 384]
        return result

    with patch("core.rag.get_embedder") as mock_get:
        mock_embedder = MagicMock()
        mock_embedder.encode.side_effect = fake_encode
        mock_get.return_value = mock_embedder

        embed_query("сколько стоит SMM?")

    assert captured[0] == ["query: сколько стоит SMM?"]


def test_embed_passages_adds_passage_prefix() -> None:
    captured: list[list[str]] = []

    def fake_encode(texts: list[str], **_kwargs: object) -> MagicMock:
        captured.append(texts)
        result = MagicMock()
        result.tolist.return_value = [[0.1] * 384, [0.2] * 384]
        return result

    with patch("core.rag.get_embedder") as mock_get:
        mock_embedder = MagicMock()
        mock_embedder.encode.side_effect = fake_encode
        mock_get.return_value = mock_embedder

        embed_passages(["SMM от 35 000 ₽", "Таргет от 40 000 ₽"])

    assert captured[0] == ["passage: SMM от 35 000 ₽", "passage: Таргет от 40 000 ₽"]


# ---------------------------------------------------------------------------
# RagClient.search — happy path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_search_returns_parsed_chunks() -> None:
    points = [
        _make_scored_point("SMM от 35 000 ₽/мес", "agency_kb.md", 0.92),
        _make_scored_point("Таргет от 40 000 ₽/мес", "agency_kb.md", 0.85),
    ]
    mock_embedder = _mock_embedder_ctx([[0.1] * 384])

    mock_response = MagicMock()
    mock_response.points = points

    mock_async_qdrant = MagicMock()
    mock_async_qdrant.query_points = AsyncMock(return_value=mock_response)

    with (
        patch("core.rag.get_embedder", return_value=mock_embedder),
        patch("core.rag._make_async_client", return_value=mock_async_qdrant),
    ):
        client = RagClient()
        chunks = await client.search("сколько стоит SMM?", top_k=2)

    assert len(chunks) == 2
    assert isinstance(chunks[0], RagChunk)
    assert chunks[0].content == "SMM от 35 000 ₽/мес"
    assert chunks[0].score == pytest.approx(0.92)
    assert chunks[0].source == "agency_kb.md"
    assert chunks[1].content == "Таргет от 40 000 ₽/мес"


# ---------------------------------------------------------------------------
# RagClient.search — error paths
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_search_returns_empty_on_connection_error() -> None:
    mock_embedder = _mock_embedder_ctx([[0.1] * 384])
    mock_async_qdrant = MagicMock()
    mock_async_qdrant.search = AsyncMock(side_effect=ConnectionError("refused"))

    with (
        patch("core.rag.get_embedder", return_value=mock_embedder),
        patch("core.rag._make_async_client", return_value=mock_async_qdrant),
    ):
        client = RagClient()
        chunks = await client.search("test query")

    assert chunks == []


@pytest.mark.asyncio
async def test_search_returns_empty_on_unexpected_exception() -> None:
    mock_embedder = _mock_embedder_ctx([[0.1] * 384])
    mock_async_qdrant = MagicMock()
    mock_async_qdrant.search = AsyncMock(side_effect=RuntimeError("collection empty"))

    with (
        patch("core.rag.get_embedder", return_value=mock_embedder),
        patch("core.rag._make_async_client", return_value=mock_async_qdrant),
    ):
        client = RagClient()
        chunks = await client.search("test query")

    assert chunks == []
