# lead-filter-bot

[English](README.md) · [Русский](README.ru.md)

Telegram-бот на базе AI для диджитал-агентств — квалифицирует входящие лиды через
диалог с DeepSeek, отбирая по бюджету, объёму задач, стадии бизнеса, срочности
и опыту работы с агентствами.

## Стек

Python 3.12 · aiogram 3 · FastAPI · DeepSeek · SQLAlchemy 2.0 · Qdrant · fastembed (ONNX) · Docker

## Быстрый старт

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

## Переменные окружения

| Variable | Description |
|---|---|
| `DEEPSEEK_API_KEY` | Your DeepSeek API key |
| `DEEPSEEK_BASE_URL` | DeepSeek endpoint (default: `https://api.deepseek.com`) |
| `DEEPSEEK_MODEL` | Model name (default: `deepseek-chat`) |
| `TELEGRAM_BOT_TOKEN` | Token from [@BotFather](https://t.me/BotFather) |
| `DATABASE_URL` | SQLAlchemy async URL (default: `sqlite+aiosqlite:///./dev.db`) |
| `LOG_LEVEL` | Logging level (default: `INFO`) |
| `ENV` | Environment name (default: `development`) |
| `QDRANT_URL` | Qdrant endpoint (default: `http://localhost:6333`) |
| `QDRANT_API_KEY` | Qdrant API key if auth enabled (default: empty) |
| `QDRANT_COLLECTION` | Collection name (default: `kontur_kb`) |
| `EMBEDDING_MODEL` | HuggingFace model ID (default: `intfloat/multilingual-e5-small`) |
| `RAG_TOP_K` | Max chunks to retrieve (default: `4`) |
| `RAG_SCORE_THRESHOLD` | Min cosine similarity, 0 = no filter (default: `0.0`) |

## Структура проекта

```
lead-filter-bot/
├── apps/
│   ├── bot/              # aiogram process
│   │   ├── main.py       # entrypoint: Dispatcher, RedisStorage, middleware wiring
│   │   ├── flow.py       # shared per-turn router (intent → RAG or advance)
│   │   ├── states.py     # FSM state definitions
│   │   ├── keyboards.py  # inline keyboards
│   │   ├── handlers/
│   │   │   ├── start.py    # /start command
│   │   │   ├── dialogue.py # 5 FSM step handlers + validators
│   │   │   └── fallback.py # post-FSM question handler (StateFilter(None))
│   │   └── middleware/
│   │       └── user_lock.py # PerUserLockMiddleware: serializes messages per user
│   └── api/              # FastAPI process
│       ├── main.py       # app + router mounting
│       ├── deps.py       # get_db() session dependency
│       └── routers/
│           ├── health.py   # GET /health
│           └── qualify.py  # GET /qualify/ping
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

Бот использует Qdrant + `intfloat/multilingual-e5-small`, чтобы отвечать на вопросы
клиента об агентстве прямо посреди диалога, не прерывая воронку квалификации.

**Важно — конвенция e5-префиксов:**
Каждый запрос обязательно должен иметь префикс `"query: "`, а каждый индексируемый
passage — префикс `"passage: "`. Если этого не сделать, качество retrieval незаметно
деградирует. Код обеспечивает это в `core/rag.py::embed_query` и `embed_passages`.

**Qdrant:** работает на `http://localhost:6333`, коллекция `kontur_kb`, размер вектора 384, метрика Cosine.

**Индексация базы знаний:**

1. Положите `*.md` файлы в `data/kb/` (файл `agency_kb.md` там уже есть).
2. Запустите `make index` — это разбивает на чанки, делает embedding и загружает их в Qdrant (идемпотентно).

**Поток на каждое сообщение:**

1. Сообщение клиента приходит в любом состоянии FSM.
2. `classify_intent(llm, current_question, user_message)` → `QUESTION` или `ANSWER`.
3. `QUESTION` → достаём контекст из Qdrant, генерируем ответ с опорой на него, повторно
   задаём тот же вопрос FSM, состояние не меняется.
4. `ANSWER` → существующая логика сохранения и перехода к следующему шагу без изменений.

Оба шага fail-safe: Qdrant недоступен → `[]`, ошибка intent classifier → считаем `ANSWER`.

## Продакшн-деплой (Aeza)

Стек на VPS: `bot` + `redis`. В продакшене Postgres и Qdrant работают в приватной сети,
бот достаёт их через тоннель WireGuard. Образ собирается прямо на VPS.

Бот работает с `network_mode: host`, потому что Aeza блокирует исходящий порт 53 для
NAT'нутого трафика контейнеров, что ломает встроенный DNS-резолвер Docker. Host
networking позволяет боту резолвить и достигать Telegram/DeepSeek API точно так же,
как это делает сам хост. Как следствие, Redis опубликован на `127.0.0.1:6379`, и бот
обращается к нему именно так (а не через имя сервиса `redis`).

> **Важно:** в продакшене нужно обойти `docker-compose.override.yml` — этот файл
> предназначен только для локальной разработки (bind-mount исходников) и автоматически
> подхватывается при обычном `docker-compose up`. На VPS всегда передавайте `-f
> docker-compose.yml` явно, чтобы применялся только базовый прод-конфиг.

```bash
# 1. Pull latest code
git pull

# 2. Fill secrets (first time only — never commit this file)
cp .env.example .env
# Set: TELEGRAM_BOT_TOKEN, DEEPSEEK_API_KEY, DATABASE_URL (postgresql+asyncpg://...),
#      QDRANT_API_KEY, REDIS_URL=redis://127.0.0.1:6379/0   # host-net → localhost, not "redis"

# 3. Build and start (explicit -f bypasses the dev override; --force-recreate
#    ensures the container actually picks up code-only changes)
docker-compose -f docker-compose.yml up -d --force-recreate --build bot

# 4. Tail logs
docker-compose -f docker-compose.yml logs -f bot
```

**Миграции**: entrypoint бота перед стартом запускает `alembic upgrade head`. Это
идемпотентно — безопасно, даже если схема уже актуальна. При первом деплое миграция
применяется к Postgres, при последующих рестартах команда сразу завершается без изменений.

**Рестарт**: `docker-compose -f docker-compose.yml restart bot` — состояние Redis
сохраняется в named volume.

---

## Database migrations

```bash
# Generate migration after model changes
uv run alembic revision --autogenerate -m "your description"

# Apply
uv run alembic upgrade head

# Rollback one step
uv run alembic downgrade -1
```

## Дорожная карта

- [x] Phase 1: каркас проекта, интеграция с DeepSeek, хендлер /start, /health
- [x] Phase 2: полный диалог квалификации (FSM, 5 вопросов, сохранение в БД, Alembic)
- [x] Phase 3: RAG над базой знаний агентства через Qdrant + intent classifier
- [x] Phase 3.5: усиление диалоговой логики — middleware с per-user lock (защита от
      гонок), валидация входных данных, обработка составных сообщений, fallback-хендлер
      для вопросов вне FSM, матрица поведения на 66 тестов
- [x] Phase 4: продакшн-деплой в Docker, Postgres, хранение состояния FSM в Redis (живёт на Aeza)
- [ ] Phase 4b: CI/CD (в планах)
- [ ] Phase 5: лендинг на Tilda, воронка в Яндекс.Метрике, запуск на Habr/VC.ru/Reddit

## License

MIT
