"""RAG layer: sentence-transformers embedder + Qdrant client.

E5 prefix convention (CRITICAL — skipping silently wrecks retrieval):
  - Queries  → "query: <text>"
  - Passages → "passage: <text>"
"""

from __future__ import annotations

import logging
from functools import lru_cache
from typing import Any

from qdrant_client import AsyncQdrantClient, QdrantClient
from qdrant_client.http.exceptions import UnexpectedResponse
from qdrant_client.http.models import Distance, PointStruct, VectorParams
from qdrant_client.http.models import QueryResponse

from core.config import get_settings
from core.schemas import RagChunk

logger = logging.getLogger(__name__)

_VECTOR_SIZE = 384  # intfloat/multilingual-e5-small output dimension


@lru_cache(maxsize=1)
def get_embedder() -> Any:  # SentenceTransformer; typed as Any — ignore_missing_imports handles it
    from sentence_transformers import SentenceTransformer

    settings = get_settings()
    logger.info("Loading embedding model: %s", settings.embedding_model)
    return SentenceTransformer(settings.embedding_model)


def _embed(texts: list[str]) -> list[list[float]]:
    embedder: Any = get_embedder()
    raw: Any = embedder.encode(texts, normalize_embeddings=True)
    result: list[list[float]] = raw.tolist()
    return result


def embed_query(text: str) -> list[float]:
    """Embed a single query string with the required e5 'query: ' prefix."""
    return _embed([f"query: {text}"])[0]


def embed_passages(texts: list[str]) -> list[list[float]]:
    """Embed passage chunks with the required e5 'passage: ' prefix."""
    return _embed([f"passage: {t}" for t in texts])


def _qdrant_kwargs() -> dict[str, Any]:
    settings = get_settings()
    kwargs: dict[str, Any] = {"url": settings.qdrant_url}
    if settings.qdrant_api_key:
        kwargs["api_key"] = settings.qdrant_api_key
    return kwargs


def _make_async_client() -> AsyncQdrantClient:
    return AsyncQdrantClient(**_qdrant_kwargs())


def _make_sync_client() -> QdrantClient:
    return QdrantClient(**_qdrant_kwargs())


def ensure_collection(collection: str | None = None) -> None:
    """Create the Qdrant collection if it doesn't exist (sync, used by indexer)."""
    settings = get_settings()
    col = collection or settings.qdrant_collection
    client = _make_sync_client()
    existing = {c.name for c in client.get_collections().collections}
    if col not in existing:
        client.create_collection(
            collection_name=col,
            vectors_config=VectorParams(size=_VECTOR_SIZE, distance=Distance.COSINE),
        )
        logger.info("Created Qdrant collection '%s'", col)
    else:
        logger.info("Qdrant collection '%s' already exists", col)


def recreate_collection(collection: str | None = None) -> None:
    """Drop and recreate the collection (used by the indexer for idempotent re-index)."""
    settings = get_settings()
    col = collection or settings.qdrant_collection
    client = _make_sync_client()
    existing = {c.name for c in client.get_collections().collections}
    if col in existing:
        client.delete_collection(col)
        logger.info("Dropped Qdrant collection '%s'", col)
    client.create_collection(
        collection_name=col,
        vectors_config=VectorParams(size=_VECTOR_SIZE, distance=Distance.COSINE),
    )
    logger.info("Created Qdrant collection '%s'", col)


def upsert_points(points: list[PointStruct], collection: str | None = None) -> None:
    """Upsert embedding points into the collection (sync, used by indexer)."""
    settings = get_settings()
    col = collection or settings.qdrant_collection
    client = _make_sync_client()
    client.upsert(collection_name=col, points=points)


class RagClient:
    """Async Qdrant search client for use inside the bot."""

    def __init__(self) -> None:
        settings = get_settings()
        self._collection = settings.qdrant_collection
        self._top_k = settings.rag_top_k
        self._threshold = settings.rag_score_threshold
        self._client: AsyncQdrantClient = _make_async_client()

    async def search(self, query: str, top_k: int | None = None) -> list[RagChunk]:
        """
        Search Qdrant for the closest chunks to query.
        Returns [] (and logs) on any connection or unexpected error — never raises.
        """
        k = top_k if top_k is not None else self._top_k
        try:
            vector = embed_query(query)
            threshold = self._threshold if self._threshold > 0.0 else None
            response: QueryResponse = await self._client.query_points(
                collection_name=self._collection,
                query=vector,
                limit=k,
                score_threshold=threshold,
            )
            chunks: list[RagChunk] = []
            for point in response.points:
                payload = point.payload or {}
                chunks.append(
                    RagChunk(
                        content=str(payload.get("content", "")),
                        score=float(point.score),
                        source=str(payload.get("source", "")),
                    )
                )
            return chunks
        except (ConnectionError, UnexpectedResponse, OSError):
            logger.warning("Qdrant search failed (connection/response error), returning []")
            return []
        except Exception:
            logger.warning("Qdrant search failed (unexpected error), returning []")
            return []
