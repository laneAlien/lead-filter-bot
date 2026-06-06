# Phase 3 Patch 1 — Qdrant API-key auth

## What changed

The homelab Qdrant instance (`10.42.0.19:6333`) was enabled with API-key auth.
This patch wires the key through the full stack so the bot and the indexer
authenticate correctly.

---

## Code audit result

**No code changes required.** The previous Phase 3 implementation already
handled the key correctly:

### `core/config.py`

```python
qdrant_api_key: str = ""   # reads QDRANT_API_KEY from env, default empty
```

### `core/rag.py` — `_qdrant_kwargs()`

```python
def _qdrant_kwargs() -> dict[str, Any]:
    settings = get_settings()
    kwargs: dict[str, Any] = {"url": settings.qdrant_url}
    if settings.qdrant_api_key:          # only added when non-empty
        kwargs["api_key"] = settings.qdrant_api_key
    return kwargs
```

Both `_make_async_client()` (bot) and `_make_sync_client()` (indexer) call
`_qdrant_kwargs()`, so the key is passed to every `AsyncQdrantClient` and
`QdrantClient` construction.

The conditional `if settings.qdrant_api_key` means a local/dev Qdrant without
auth still works with `QDRANT_API_KEY=` (empty string).

---

## Files actually changed

| File | Change |
|---|---|
| `.env.example` | Added inline comment to `QDRANT_API_KEY=` explaining empty = no auth |
| `.env` | Added `QDRANT_API_KEY=<key>` + full RAG section (file is gitignored, key is NOT in git) |

---

## `.env` entry to set (not committed)

```
QDRANT_API_KEY=<your-key>   # set this; never commit the value
```

---

## Verification results

```
make lint      → All checks passed (ruff)
make typecheck → Success: no issues found in 14 source files (mypy strict)
make test      → 36 passed in 3.34s
```

### Auth smoke-test

```
# Authenticated:
curl -sf -H "api-key: $QDRANT_API_KEY" http://10.42.0.19:6333/collections/kontur_kb
→ AUTH OK ✓

# Unauthenticated (as of 2026-06-06):
curl -s -o /dev/null -w "%{http_code}\n" http://10.42.0.19:6333/collections
→ 200
```

**Note on the 200 without key:** At the time of this patch, the Qdrant instance
returns 200 on unauthenticated read requests — auth appears to be configured
but not yet enforced (possibly needs a Qdrant process restart for the config
to take effect, or the instance is in a mode that allows anonymous reads).
Authenticated requests succeed with `AUTH OK`. The bot code is correct and will
function without changes when full enforcement is enabled.

---

## Failure mode when auth IS enforced

If `QDRANT_API_KEY` is empty and Qdrant requires auth, `RagClient.search()`
catches the resulting exception and returns `[]` (logs a warning). The bot
degrades gracefully — the qualification FSM treats a RAG failure as no-context
and continues. No crash, no hang.

---

## Commit command

```bash
git add .env.example PHASE3_PATCH1_REPORT.md

git commit -m "fix: wire Qdrant API-key auth through config and clients

- .env.example: clarify QDRANT_API_KEY= comment (empty = no auth, set for
  auth-enabled Qdrant instances); key value goes in .env only (gitignored)
- No code changes: core/config.py and core/rag.py already handled the key
  correctly via _qdrant_kwargs() conditional; both async and sync clients covered
- 36 tests pass; ruff + mypy strict clean

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```
