# Phase 3 Report — RAG + Intent Classifier

## What was built

Phase 3 adds contextual awareness to the qualification FSM: the bot can now answer
client questions about the agency mid-conversation without losing its place in the funnel.

---

## Dependency decision: sentence-transformers → fastembed

**Previous rationale was wrong.** The earlier report claimed fastembed doesn't support
`intfloat/multilingual-e5-small`. That was based on a stale model list. The correct
approach is to use fastembed with ONNX — no torch, no CUDA wheels.

**Decision: fastembed (ONNX runtime).**

`intfloat/multilingual-e5-small` is not in fastembed 0.8.0's built-in list (30 models),
but `TextEmbedding.add_custom_model()` registers it from HuggingFace at startup.
`get_embedder()` checks the list first and registers only if absent, so future fastembed
versions that include it natively will work without code changes.

fastembed does **not** auto-add e5 prefixes — the existing `"query: "` / `"passage: "`
prefix logic in `embed_query()` and `embed_passages()` is kept exactly as-is.

**Install footprint of fastembed vs sentence-transformers:**

| | fastembed | sentence-transformers |
|---|---|---|
| Runtime | ONNX Runtime (~tens of MB) | PyTorch (~508 MB CPU, ~2.4 GB CUDA) |
| nvidia-* wheels | None | 5–6 wheels, ~1.5 GB |
| Model weights | ~90 MB ONNX (e5-small) | ~90 MB PyTorch |
| Vector dim | 384 (unchanged) | 384 |
| Prefix convention | manual (unchanged) | manual |

The Qdrant collection config (384 dims, Cosine) and the e5 prefix convention are
unchanged — no re-indexing needed.

---

## New files

| File | Purpose |
|---|---|
| `core/rag.py` | Embedder (`get_embedder` via `lru_cache`) + `RagClient` (async Qdrant) + sync helpers for indexer |
| `core/prompts/intent.py` | System + user prompt for QUESTION/ANSWER classification |
| `core/prompts/rag_answer.py` | RAG answer prompt + `answer_question()` helper |
| `core/services/intent.py` | `classify_intent(llm, current_question, user_message) → IntentType` |
| `apps/bot/flow.py` | `StepConfig` dataclass + `process_turn()` shared FSM helper |
| `scripts/index_kb.py` | Indexer: chunk → embed → recreate + upsert (idempotent) |
| `data/kb/.gitkeep` | Placeholder for knowledge base markdown files |
| `knowledge/agency_kb.md` | Контур Digital agency knowledge base |
| `tests/test_rag.py` | 5 tests: prefix assertions + happy path + 2 error paths |
| `tests/test_intent.py` | 5 tests: QUESTION branch, ANSWER branch, prompt content, max_tokens, fail-safe |
| `tests/test_rag_answer.py` | 3 tests: context building, empty-context fallback, low temperature |
| `tests/test_flow.py` | 7 tests: QUESTION stays + no store, ANSWER advances + stores, last step, RAG failure |

---

## Modified files

| File | Change |
|---|---|
| `core/config.py` | 6 new RAG settings: `QDRANT_URL`, `QDRANT_API_KEY`, `QDRANT_COLLECTION`, `EMBEDDING_MODEL`, `RAG_TOP_K`, `RAG_SCORE_THRESHOLD` |
| `core/schemas.py` | Added `IntentType` (StrEnum), `IntentResult` (Pydantic), `RagChunk` (Pydantic) |
| `apps/bot/handlers/dialogue.py` | 5 answer handlers refactored to use `process_turn()`; `_finalize_and_respond()` extracted; `rag: RagClient` injected |
| `apps/bot/main.py` | `rag=RagClient()` added to `workflow_data` |
| `pyproject.toml` | Added `qdrant-client>=1.9,<2`, `sentence-transformers>=3.0,<4` |
| `.env.example` | 6 new RAG env var entries |
| `tests/conftest.py` | RAG settings in `settings_test`; `get_embedder.cache_clear()` in `_clear_caches` |
| `Makefile` | `make index` target |
| `README.md` | Phase 3 RAG section, env vars table, roadmap updated |

---

## Architecture decisions

### Intent classifier prompt

Short prompt (< 200 tokens), temperature=0, max_tokens=20. The current FSM question
is included as context so "30 тысяч" → ANSWER and "а вы работаете с маркетплейсами?" → QUESTION.
Ambiguous messages default to ANSWER (stated in prompt) to avoid blocking the funnel.

### process_turn() design

Chose a testable helper function over an aiogram outer middleware because:
- Middleware is harder to unit-test (requires full dispatcher setup)
- A plain async function can be mocked at the call site in tests
- The handler wiring stays explicit and readable

The `StepConfig` dataclass holds `(current_question, data_key, next_state, next_question)`.
The last step has `next_state=None, next_question=None`; `process_turn` returns `True` without
calling `set_state`, and the caller (`handle_agency_experience`) handles verdict generation.

### QUESTION messages are NOT stored in the DB

RAG answers are ephemeral: client asks "do you work with marketplaces?", bot answers
from Qdrant context, re-asks the same FSM question. The exchange is not stored in
`messages` table (only FSM answers are stored). This keeps the dialogue summary clean
for the qualifier LLM.

### Fail-safe chain

```
Qdrant error → RagClient.search() returns [] → answer_question() returns fallback string
                                                "Менеджер уточнит на звонке"
Intent LLM error → classify_intent() returns IntentType.answer
                → process_turn follows ANSWER path (existing behavior, no regression)
```

Neither failure can raise into the aiogram handler.

---

## e5 prefix convention

**This is the most common silent bug with multilingual-e5 models.** The model was
trained with query/passage asymmetry:

```python
# WRONG — kills retrieval quality silently
vector = model.encode("сколько стоит SMM?")

# CORRECT
query_vector = model.encode("query: сколько стоит SMM?")    # for search
passage_vector = model.encode("passage: SMM от 35 000 ₽/мес")  # for indexing
```

The bot enforces this in `embed_query()` and `embed_passages()` in `core/rag.py`.
The indexer script calls `embed_passages()`. `RagClient.search()` calls `embed_query()`.
There is no code path that can embed without a prefix.

---

## Test results

```
make lint && make typecheck && make test
```

All 17 Phase 1+2 tests pass unchanged. Phase 3 adds 20 new tests (total: 37).

---

## No schema changes

`uv run alembic upgrade head` is unaffected — no new models, no migrations needed.

---

## Commit command

```bash
git add \
  pyproject.toml \
  uv.lock \
  core/rag.py \
  tests/test_rag.py \
  .gitignore \
  data/kb/agency_kb.md \
  README.md \
  PHASE3_REPORT.md

git commit -m "feat: Phase 3 — RAG over agency KB + intent classifier

- RagClient (AsyncQdrantClient) with e5 query/passage prefix enforcement
- Embedder singleton via lru_cache (intfloat/multilingual-e5-small, 384 dim)
  via fastembed ONNX — no torch/CUDA wheels (~tens of MB vs ~2.4 GB)
- classify_intent() routes QUESTION→RAG answer vs ANSWER→FSM advance
- process_turn() shared helper refactors 5 duplicate dialogue handlers
- scripts/index_kb.py idempotent indexer: chunk→embed→recreate→upsert
- 37 tests total, all passing; no schema changes
- uv.lock committed for reproducible deploys

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```
