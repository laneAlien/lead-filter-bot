# Phase 3 Report — RAG + Intent Classifier

## What was built

Phase 3 adds contextual awareness to the qualification FSM: the bot can now answer
client questions about the agency mid-conversation without losing its place in the funnel.

---

## Dependency decision: sentence-transformers vs fastembed

**Checked fastembed** (`TextEmbedding.list_supported_models()` on v0.8.0, 30 models):

| Model | In fastembed? | Dims |
|---|---|---|
| `intfloat/multilingual-e5-small` | **No** | 384 |
| `intfloat/multilingual-e5-large` | Yes | 1024 |
| `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` | Yes | 384 |

fastembed does **not** support `multilingual-e5-small`. The closest multilingual 384-dim
alternative is `paraphrase-multilingual-MiniLM-L12-v2`, but that's a different model
with different retrieval characteristics and no e5 prefix convention.

**Decision: sentence-transformers.**

Rationale:
- The Qdrant collection is configured for 384 dims (e5-small size).
- The e5 prefix convention (`query: ` / `passage: `) is part of the spec and only
  applies to the e5 family.
- Switching model would require re-indexing and would change retrieval quality.

**Install footprint of sentence-transformers (Linux, Python 3.12):**

Downloaded wheels during `uv add`:
- `torch` (CPU+CUDA): ~508 MB wheel
- `nvidia-cublas`: ~404 MB
- `nvidia-cudnn-cu13`: ~349 MB
- `nvidia-nccl-cu13`: ~196 MB
- `triton`: ~192 MB
- `nvidia-cusolver`: ~192 MB
- `nvidia-cufft`: ~204 MB
- `nvidia-cusparse`: ~139 MB
- `transformers`, `tokenizers`, `sympy`, etc.: ~40 MB combined
- **Total download: ~2.4 GB** (CUDA build; CPU-only `--extra-index-url https://download.pytorch.org/whl/cpu` would be ~200 MB)

For CPU-only deployment, add to `uv.toml` or `pyproject.toml`:
```toml
[tool.uv.sources]
torch = { url = "https://download.pytorch.org/whl/cpu/torch-2.x.x+cpu-cp312-cp312-linux_x86_64.whl" }
```

The embedder loads once at startup and stays in memory (~90 MB for e5-small weights).

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
  core/config.py \
  core/schemas.py \
  core/rag.py \
  core/prompts/intent.py \
  core/prompts/rag_answer.py \
  core/services/intent.py \
  apps/bot/flow.py \
  apps/bot/handlers/dialogue.py \
  apps/bot/main.py \
  scripts/__init__.py \
  scripts/index_kb.py \
  data/kb/.gitkeep \
  tests/test_rag.py \
  tests/test_intent.py \
  tests/test_rag_answer.py \
  tests/test_flow.py \
  tests/conftest.py \
  pyproject.toml \
  uv.lock \
  .env.example \
  Makefile \
  README.md \
  PHASE3_REPORT.md

git commit -m "feat: Phase 3 — RAG over agency KB + intent classifier

- RagClient (AsyncQdrantClient) with e5 query/passage prefix enforcement
- Embedder singleton via lru_cache (intfloat/multilingual-e5-small, 384 dim)
- classify_intent() routes QUESTION→RAG answer vs ANSWER→FSM advance
- process_turn() shared helper refactors 5 duplicate dialogue handlers
- scripts/index_kb.py idempotent indexer: chunk→embed→recreate→upsert
- 20 new tests (37 total), all passing; no schema changes

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```
