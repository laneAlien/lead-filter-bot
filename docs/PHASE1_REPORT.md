# Отчёт: Фаза 1 — Стартовый скелет `lead-filter-bot`

**Дата:** 2026-05-13  
**Репозиторий:** https://github.com/laneAlien/lead-filter-bot  
**Статус:** ✅ Завершено

---

## Что было сделано

### 1. Инициализация проекта

- Клонирован репозиторий в `/home/nosferatuton/work_dir/lead-filter-bot/`
- Установлен `uv` (не был установлен на системе) — `~/.local/bin/uv`
- Создан `pyproject.toml` с полным конфигом:
  - Python `^3.12`
  - Зависимости: aiogram 3.x, FastAPI, SQLAlchemy 2.0, openai SDK, pydantic-settings, aiosqlite, asyncpg, alembic, httpx и др.
  - Dev-зависимости: pytest, pytest-asyncio, ruff, mypy, faker
  - Scripts: `bot` и `api` как точки входа
  - Конфиг ruff (line-length 100, правила E/W/F/I/B/UP/SIM/RUF), mypy strict для `core/`
- `.gitignore` дополнен: `qdrant_storage/`, `*.db`, `dev.db`, `uv.lock`
- `.env.example` со всеми 7 переменными окружения

### 2. `core/` — общая библиотека

| Файл | Что реализовано |
|---|---|
| `config.py` | `Settings(BaseSettings)` с `SettingsConfigDict`, синглтон `get_settings()` через `@lru_cache` |
| `llm.py` | `LLMClient` — async-обёртка над DeepSeek; методы `chat()` и `chat_structured[T]()` с логированием токенов |
| `prompts/qualifier.py` | `QUALIFIER_SYSTEM_PROMPT` — системный промпт квалификации лидов, 5 параметров, критерии `qualified=true`, JSON-вердикт |
| `schemas.py` | `QualifierVerdict`, `DialogueMessage`, 5 `StrEnum`-классов (ServiceType, BusinessStage, Urgency, AgencyExperience, NextStep) |
| `models.py` | SQLAlchemy 2.0: `User`, `Conversation`, `Message` с `Mapped`/`mapped_column` |
| `db.py` | `create_async_engine`, `async_sessionmaker`, `get_session()` как async generator, `init_db()` для локального старта без Alembic |
| `rag.py` | Заглушка с TODO для Фазы 2 |

**Важные технические решения:**
- `LLMClient.chat_structured()` использует generic-метод `[T: BaseModel]` (Python 3.12 синтаксис) — type-safe парсинг ответа DeepSeek в Pydantic-модель
- Для `response_format` используется `ResponseFormatJSONObject` из openai SDK вместо raw dict — это позволяет пройти mypy strict
- `StrEnum` вместо `str, Enum` (правило UP042 ruff)

### 3. `apps/bot/` — Telegram-бот

| Файл | Что реализовано |
|---|---|
| `main.py` | Создаёт `Bot` + `Dispatcher(MemoryStorage)`, регистрирует роутеры, вызывает `init_db()`, запускает polling |
| `states.py` | `QualificationFSM` с состояниями `waiting_for_start_confirm` и `in_dialogue` |
| `keyboards.py` | `yes_no_keyboard()` — inline-клавиатура «Да»/«Нет» |
| `handlers/start.py` | Handler `/start` — устанавливает FSM-состояние, отправляет приветствие с кнопками |
| `handlers/dialogue.py` | Заглушка: обрабатывает callback «да/нет» и сообщения в состоянии `in_dialogue`, с TODO-комментариями для Фазы 2 |

### 4. `apps/api/` — FastAPI

| Файл | Что реализовано |
|---|---|
| `main.py` | FastAPI app, регистрирует роутеры, `on_startup` вызывает `init_db()` |
| `deps.py` | `get_db()` — async generator для DI |
| `routers/health.py` | `GET /health` → `{"status": "ok", "env": "..."}` |
| `routers/qualify.py` | `GET /qualify/ping` — тестовый вызов DeepSeek, возвращает ответ модели |

### 5. Тесты

11 тестов в 3 файлах, **все проходят**:

| Файл | Тесты |
|---|---|
| `test_config.py` | Загрузка из env-переменных, дефолтные значения, singleton `get_settings()` |
| `test_llm.py` | `chat()` возвращает строку, передаёт temperature/max_tokens, `chat_structured()` парсит `QualifierVerdict` |
| `test_schemas.py` | Валидный вердикт, null-бюджет, невалидный `service_type`, невалидный `next_step`, отсутствующее поле |

`conftest.py`: фикстура `settings_test` с `monkeypatch` + автоматический сброс `lru_cache`.

### 6. Makefile + README

`Makefile` с командами: `install`, `dev-bot`, `dev-api`, `test`, `lint`, `format`, `typecheck`.  
`README.md` полностью переписан: стек, quick start, таблица переменных, структура проекта, roadmap.

---

## Результаты проверок

```
make lint       → All checks passed ✅
make typecheck  → Success: no issues found in 9 source files ✅
make test       → 11 passed in 1.80s ✅
GET /health     → {"status":"ok","env":"development"} ✅
```

---

## Что намеренно НЕ сделано (отложено)

| Компонент | Фаза |
|---|---|
| Alembic-миграции | Фаза 2 |
| Полный FSM-диалог квалификации (5 вопросов) | Фаза 2 |
| Сохранение диалога и вердикта в БД | Фаза 2 |
| Qdrant + RAG + sentence-transformers | Фаза 3 |
| Dockerfile + docker-compose | Фаза 3 |
| GitHub Actions CI/CD | Фаза 3 |
| Redis для FSM-хранилища | Фаза 4 |

---

## Что нужно сделать вручную

1. **Создать бота** через [@BotFather](https://t.me/BotFather): `/newbot` → имя → username (заканчивается на `bot`)
2. **Заполнить `.env`:**
   ```bash
   cp .env.example .env
   # вписать DEEPSEEK_API_KEY и TELEGRAM_BOT_TOKEN
   ```
3. **Установить зависимости:** `make install`
4. **Проверить интеграцию с DeepSeek:**
   ```bash
   make dev-api                              # терминал 1
   curl http://localhost:8000/qualify/ping   # должен вернуть ответ от модели
   ```
5. **Запустить бота:** `make dev-bot`, написать `/start` — должен ответить приветствием с кнопками «Да»/«Нет»
6. **Закоммитить:**
   ```bash
   git add .
   git commit -m "phase 1: project skeleton, DeepSeek integration, /start handler, /health"
   git push
   ```

---

## Известные ограничения текущей версии

- `MemoryStorage` для FSM — состояния сбрасываются при перезапуске бота. Это нормально для Фазы 1, Redis добавится в Фазе 4.
- `init_db()` создаёт таблицы напрямую через `metadata.create_all()` — без миграций. Alembic подключим в Фазе 2.
- `/qualify/ping` делает прямой вызов DeepSeek без сохранения в БД — это намеренно, только для проверки интеграции.
- `handlers/dialogue.py` содержит заглушку вместо реального диалога — полный FSM-флоу реализуем в Фазе 2.

---

## Следующий шаг — Фаза 2

Промпт для следующей сессии Claude Code:

> «Phase 2: implement the full qualification FSM dialogue in `apps/bot/handlers/dialogue.py`.
> 5 questions sequentially (budget → service type → business stage → urgency →
> agency experience), each answer stored in FSM state, save full conversation
> to DB, after the 5th answer make a single DeepSeek call with `QUALIFIER_SYSTEM_PROMPT`
> + full dialogue history, parse response as `QualifierVerdict`, save to DB, send
> verdict to user. Add Alembic, initial migration. Add 3-5 integration tests
> with mocked DeepSeek.»
