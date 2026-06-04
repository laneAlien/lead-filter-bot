# lead-filter-bot

AI-powered Telegram bot for digital agencies — qualifies inbound leads via
DeepSeek-driven dialogue, filters by budget, scope, business stage, urgency,
and prior agency experience.

🚧 Building in public. Following progress: [LinkedIn URL placeholder]

## Stack

Python 3.12 · aiogram 3 · FastAPI · DeepSeek · SQLAlchemy 2.0 · Qdrant · sentence-transformers · Docker

## Quick start

```bash
git clone https://github.com/laneAlien/lead-filter-bot.git
cd lead-filter-bot

# Copy and fill environment variables
cp .env.example .env
# Edit .env: set DEEPSEEK_API_KEY and TELEGRAM_BOT_TOKEN

# Install dependencies
make install

# Apply database migrations
uv run alembic upgrade head

# Verify everything works
make lint && make typecheck && make test

# Run API server (terminal 1)
make dev-api

# Run Telegram bot (terminal 2)
make dev-bot
```

## Environment variables

| Variable | Description |
|---|---|
| `DEEPSEEK_API_KEY` | Your DeepSeek API key |
| `DEEPSEEK_BASE_URL` | DeepSeek endpoint (default: `https://api.deepseek.com`) |
| `DEEPSEEK_MODEL` | Model name (default: `deepseek-chat`) |
| `TELEGRAM_BOT_TOKEN` | Token from [@BotFather](https://t.me/BotFather) |
| `DATABASE_URL` | SQLAlchemy async URL (default: `sqlite+aiosqlite:///./dev.db`) |
| `LOG_LEVEL` | Logging level (default: `INFO`) |
| `ENV` | Environment name (default: `development`) |
| `QDRANT_URL` | Qdrant endpoint (default: `http://10.42.0.19:6333`) |
| `QDRANT_API_KEY` | Qdrant API key if auth enabled (default: empty) |
| `QDRANT_COLLECTION` | Collection name (default: `kontur_kb`) |
| `EMBEDDING_MODEL` | HuggingFace model ID (default: `intfloat/multilingual-e5-small`) |
| `RAG_TOP_K` | Max chunks to retrieve (default: `4`) |
| `RAG_SCORE_THRESHOLD` | Min cosine similarity, 0 = no filter (default: `0.0`) |

## Project structure

```
lead-filter-bot/
├── apps/
│   ├── bot/              # aiogram process
│   │   ├── handlers/     # /start and dialogue FSM handlers
│   │   ├── states.py     # FSM state definitions
│   │   └── keyboards.py  # inline keyboards
│   └── api/              # FastAPI process
│       └── routers/      # health, qualify endpoints
├── apps/
│   └── bot/
│       ├── flow.py       # shared per-turn router (intent → RAG or advance)
│       └── ...
├── core/                 # shared library
│   ├── config.py         # pydantic-settings
│   ├── llm.py            # DeepSeek client wrapper
│   ├── rag.py            # Embedder + RagClient (Qdrant)
│   ├── prompts/
│   │   ├── qualifier.py  # qualification system prompt
│   │   ├── intent.py     # QUESTION vs ANSWER classifier prompt
│   │   └── rag_answer.py # grounded answer builder
│   ├── services/
│   │   ├── conversation.py
│   │   └── intent.py     # classify_intent()
│   ├── models.py         # SQLAlchemy 2.0 models
│   ├── schemas.py        # Pydantic schemas (+ IntentType, RagChunk)
│   └── db.py             # async session / engine
├── data/kb/              # drop *.md knowledge base files here
├── scripts/
│   └── index_kb.py       # chunks + embeds + upserts into Qdrant
├── migrations/           # Alembic
├── tests/
├── .env.example
├── pyproject.toml        # uv-managed
└── Makefile
```

## API endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/health` | Health check, returns env |
| `GET` | `/qualify/ping` | Test DeepSeek connection |

## RAG (Phase 3)

The bot uses Qdrant + `intfloat/multilingual-e5-small` to answer client questions
about the agency mid-conversation without interrupting the qualification funnel.

**Important — e5 prefix convention:**
Every query must be prefixed with `"query: "` and every indexed passage with `"passage: "`.
Skipping this silently degrades retrieval quality. The code enforces this in
`core/rag.py::embed_query` and `embed_passages`.

**Qdrant:** running at `http://10.42.0.19:6333`, collection `kontur_kb`, vector size 384, Cosine distance.

**Indexing the knowledge base:**

1. Drop `*.md` files into `data/kb/` (the `agency_kb.md` file is already there).
2. Run `make index` — this chunks, embeds, and upserts into Qdrant (idempotent).

**Flow per turn:**

1. Client message arrives in any FSM state.
2. `classify_intent(llm, current_question, user_message)` → `QUESTION` or `ANSWER`.
3. `QUESTION` → retrieve from Qdrant, generate grounded reply, re-ask the same FSM question, stay in state.
4. `ANSWER` → existing store-and-advance logic unchanged.

Both steps fail safe: Qdrant unreachable → `[]`, intent classifier error → treat as `ANSWER`.

## Database migrations

```bash
# Generate migration after model changes
uv run alembic revision --autogenerate -m "your description"

# Apply
uv run alembic upgrade head

# Rollback one step
uv run alembic downgrade -1
```

## Roadmap

- [x] Phase 1: project skeleton, DeepSeek integration, /start handler, /health
- [x] Phase 2: full qualification dialogue (FSM, 5-question flow, DB persistence, Alembic)
- [x] Phase 3: RAG over agency knowledge base via Qdrant + intent classifier
- [ ] Phase 4: Docker production deploy, Postgres, Redis FSM storage, CI/CD
- [ ] Phase 5: Tilda landing, Yandex.Metrica funnel, launch on Habr/VC.ru/Reddit

## License

MIT
