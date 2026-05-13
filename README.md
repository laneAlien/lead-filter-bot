# lead-filter-bot

AI-powered Telegram bot for digital agencies — qualifies inbound leads via
DeepSeek-driven dialogue, filters by budget, scope, business stage, urgency,
and prior agency experience.

🚧 Building in public. Following progress: [LinkedIn URL placeholder]

## Stack

Python 3.12 · aiogram 3 · FastAPI · DeepSeek · SQLAlchemy 2.0 · Docker

## Quick start

```bash
git clone https://github.com/laneAlien/lead-filter-bot.git
cd lead-filter-bot

# Copy and fill environment variables
cp .env.example .env
# Edit .env: set DEEPSEEK_API_KEY and TELEGRAM_BOT_TOKEN

# Install dependencies
make install

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
├── core/                 # shared library
│   ├── config.py         # pydantic-settings
│   ├── llm.py            # DeepSeek client wrapper
│   ├── prompts/          # system prompts
│   ├── models.py         # SQLAlchemy 2.0 models
│   ├── schemas.py        # Pydantic schemas
│   ├── db.py             # async session / engine
│   └── rag.py            # stub for Phase 2 RAG
├── migrations/           # Alembic (Phase 2)
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

## Roadmap

- [x] Phase 1: project skeleton, DeepSeek integration, /start handler, /health
- [ ] Phase 2: full qualification dialogue (FSM, 5-question flow, DB persistence)
- [ ] Phase 3: RAG over agency knowledge base via Qdrant
- [ ] Phase 4: Docker production deploy, Postgres, Redis FSM storage, CI/CD
- [ ] Phase 5: Tilda landing, Yandex.Metrica funnel, launch on Habr/VC.ru/Reddit

## License

MIT
