# lead-filter-bot — Claude Code context

Telegram qualification bot for inbound leads at a digital agency (Контур Digital).
A lead answers 5 FSM questions; the bot routes intent (QUESTION/ANSWER) via LLM,
answers off-topic questions from a RAG knowledge base, and generates a qualification
verdict. The manager reviews and calls back — the bot does **not** book calls itself.

---

## Stack

- **Python 3.12+**, managed with **uv** (`uv sync`, `uv run`)
- **aiogram 3.4–3.x** (FSM, long polling, RedisStorage for FSM state)
- **FastAPI 0.110+** (companion API, not the bot transport)
- **SQLAlchemy 2.x async** + **asyncpg**, migrations via **Alembic 1.13+**
- **openai ≥1.30** SDK — pointed at DeepSeek, not OpenAI
- **DeepSeek** model `deepseek-chat`, base URL `https://api.deepseek.com`
  (OpenAI-compatible; do not swap for a different model without testing the
  structured-output calls in `core/llm.py`)
- **fastembed ≥0.4** (ONNX runtime, **not** sentence-transformers, **not** torch)
  Model: `intfloat/multilingual-e5-small`, 384-dim vectors. Downloaded to
  `/app/.cache/huggingface` (volume-mounted); first run is slow (ONNX fetch).
  The e5 prefix convention is critical — `embed_query` prepends `"query: "`,
  `embed_passages` prepends `"passage: "`. Removing these silently wrecks retrieval.
- **qdrant-client ≥1.9** — collection `kontur_kb`, API-key auth
- **Redis 7** (alpine) — FSM storage only
- **ruff** (line-length 100, py312, rules E/W/F/I/B/UP/SIM/RUF, ignores B008+RUF001)
- **mypy strict** — covers `core/` only (not `apps/`; `ignore_missing_imports = true`)
- **pytest** + **pytest-asyncio** (`asyncio_mode = "auto"`)

Makefile targets: `make install`, `make test`, `make lint`, `make format`,
`make typecheck`, `make index` (re-embeds `data/kb/*.md` → Qdrant), `make dev-bot`.

---

## Architecture — prod topology

```
Aeza VPS (Debian 12)              Homelab (Proxmox)
┌─────────────────────┐           ┌────────────────────────┐
│ docker-compose (v1) │           │ LXC 210 @ 10.42.0.20   │
│  ├─ bot (host net)  │◄─WireGuard─►  Postgres :5432        │
│  └─ redis :6379     │           │  DB: leadbot (lowercase)│
└─────────────────────┘           ├────────────────────────┤
                                  │ LXC 209 @ 10.42.0.19   │
                                  │  Qdrant :6333           │
                                  │  collection: kontur_kb  │
                                  └────────────────────────┘
```

- **Long polling** only — no webhook configured.
- **Bot process**: `python -m apps.bot.main`, entrypoint runs `alembic upgrade head` first.
- **FSM state** lives in Redis (local on Aeza). Conversation data lives in Postgres (homelab).
- **WireGuard tunnel** connects Aeza ↔ homelab. If tunnel/homelab is down, bot crash-loops
  (`restart: unless-stopped`) until it recovers.

---

## Deploy gotchas — read every time before touching prod

### 1. `docker-compose` with a hyphen (v1 standalone binary)
Aeza has `docker-compose` (v1), not the `docker compose` plugin. Using the wrong
form silently does nothing or uses the wrong config.

### 2. ALWAYS pass `-f docker-compose.yml` explicitly
```bash
docker-compose -f docker-compose.yml up -d --force-recreate --build bot
```
`docker-compose.override.yml` is **dev-only** (source bind-mount + SQLite URL).
Docker Compose auto-loads it when you omit `-f`. This once injected an SQLite
`DATABASE_URL` into prod and broke persistence silently.

### 3. Image is BUILT on the VPS — there is no registry
`--build` is required on every deploy that touches code. There is nothing to `pull`.

### 4. `network_mode: host` on the bot service
Aeza blocks outbound port 53 for NAT'd containers (Docker's embedded DNS breaks).
Host networking sidesteps this. Consequence:

> **`REDIS_URL` must be `redis://127.0.0.1:6379/0`** — not `redis://redis:6379/0`.
> The `redis` service name is unreachable from a host-networked container.

### 5. `.env` is gitignored — secrets live only on the server
After any fresh clone on Aeza, recreate `.env` with production values before
running anything. Key fields: `DEEPSEEK_API_KEY`, `DATABASE_URL` (must reference
`leadbot` db at 10.42.0.20), `REDIS_URL` (127.0.0.1), `QDRANT_URL`, `QDRANT_API_KEY`.

### 6. Code-only changes need a bot redeploy; KB-only changes do not
`make index` writes directly to homelab Qdrant — the change is live for prod
immediately. Only `.py` / template / config changes need the VPS rebuild+restart.

### 7. Dev sessions live on 208 (this machine)
Deploy runs ON Aeza via SSH or a Claude Code session opened on the VPS itself.
Direct SSH from 208 may fail on key auth — check before assuming it works.

---

## Database

- DB name: **`leadbot`** (lowercase). A casing bug once created a stray `Leadbot` —
  never use any other casing in `DATABASE_URL` or raw SQL.
- All timestamp columns are **`TIMESTAMP WITH TIME ZONE`** (timestamptz). Always use
  `datetime.now(UTC)` (tz-aware). A naive/aware mismatch once silently hung the
  final verdict step because SQLAlchemy's asyncpg dialect rejects naive datetimes
  on timestamptz columns with a comparator error that surfaced only at runtime.
- Migrations in `migrations/versions/`. Run automatically by entrypoint.sh.
  Code-only deploys are safe (alembic is idempotent). Schema changes need a
  migration file committed first.

---

## RAG / dialogue behaviour — do not regress

### Intent routing (per turn, `apps/bot/flow.py: process_turn`)
1. **Early guard** (before LLM): empty / whitespace-only / emoji-only / no-alphanumeric
   input → re-ask current FSM question immediately, no LLM call, no advance.
2. **Intent classifier** (`core/services/intent.py`): classifies as `QUESTION` or `ANSWER`.
   - `QUESTION` → RAG answer from `kontur_kb` + re-ask current FSM question. No state change.
   - `ANSWER` → step validator → store → advance FSM.
3. **Step validators** on `StepConfig.validator` (Python, no LLM):
   - budget step: must contain at least one digit (rejects "привет", emojis)
   - other steps: ≥2 stripped characters
   Validator failure → re-ask with "Уточните, пожалуйста: …", no advance.
4. **Compound message** ("answer + embedded question"): ANSWER path runs, and if the
   text contains a `?`-fragment of ≥3 words (guarded by `_has_embedded_question`),
   a RAG reply is sent *before* the next FSM question. "ок?" (1 word) does NOT trigger.

### Per-user asyncio lock (`apps/bot/middleware/user_lock.py`)
Serializes all messages from the same user. Prevents FSM race conditions where a slow
RAG/LLM call and a rapid second message interleave, causing duplicate question sends
or data corruption. Do not remove or bypass this middleware.

### RAG system prompt (`core/prompts/rag_answer.py`)
Contains an explicit instruction: when a lead asks how to contact the manager,
the bot must clarify that the bot itself is the entry point (answer questions →
manager calls back). This addresses a real user-frustration loop seen in prod.

### 66 tests encode the full behavior matrix
`tests/test_fsm_scenarios.py` covers scenarios S1–S8 (clean answer, pure question,
compound, extra message, invalid answer, concurrency, post-FSM, garbage input).
`make test` must be green before every commit. The tests are deterministic: all
LLM/intent/RAG calls are mocked.

---

## Code layout

```
apps/
  bot/
    flow.py          # process_turn: per-turn FSM router (the critical path)
    handlers/
      dialogue.py    # 5 FSM step handlers + StepConfig definitions + validators
      fallback.py    # StateFilter(None): post-FSM question handler
      start.py       # /start command
    middleware/
      user_lock.py   # PerUserLockMiddleware
    states.py        # QualificationFSM state group
  api/               # FastAPI companion (health + qualify endpoints)
core/
  config.py          # Settings (pydantic-settings, lru_cache)
  db.py              # async engine + sessionmaker (lru_cache)
  llm.py             # LLMClient wrapping openai SDK → DeepSeek
  models.py          # User, Conversation, Message (SQLAlchemy)
  rag.py             # RagClient (Qdrant), embed_query/embed_passages
  services/
    conversation.py  # DB helpers: get_or_create_user, add_message, generate_verdict
    intent.py        # classify_intent: QUESTION vs ANSWER
  prompts/
    intent.py        # Intent classifier prompt
    qualifier.py     # Final verdict prompt
    rag_answer.py    # RAG answer prompt + answer_question helper
data/kb/             # Markdown knowledge base files (agency_kb.md)
scripts/
  index_kb.py        # make index: chunks + embeds + upserts to Qdrant
  verify_rag.py      # smoke-test: queries RAG and prints generated answers
migrations/          # Alembic migration versions
```
