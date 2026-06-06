# Phase 4 — Production Deploy Prerequisites

> Аудит текущего состояния стека перед production-деплоем.
> Дата: 2026-06-06. Код на момент коммита `be73d63`.

---

## 1. База данных

| Параметр | Значение |
|---|---|
| Движок | SQLAlchemy **async** (`create_async_engine`) |
| Драйвер | **`aiosqlite`** — SQLite через async-обёртку |
| DSN по умолчанию | `sqlite+aiosqlite:///./dev.db` (файл в CWD) |
| Для prod | нужен swap на `postgresql+asyncpg://...` |

**Alembic:** настроен и работает.
- `alembic.ini` → `migrations/` → `env.py`
- `env.py` запускает миграции через async-движок, DSN берёт из `get_settings().database_url` (строка в `alembic.ini` — заглушка, игнорируется)
- Миграций: **1** — `8aaa353472e8_phase_2_initial_schema.py`, создаёт все три таблицы

---

## 2. FSM-хранилище

```python
# apps/bot/main.py:22
dp = Dispatcher(storage=MemoryStorage())
```

Используется **`MemoryStorage`** — хранится в оперативной памяти процесса.
При любом перезапуске бота все активные диалоги теряются: пользователь видит
бота как начавшего разговор заново. Для Phase 4 нужен `RedisStorage`.

---

## 3. Модели (SQLAlchemy)

Три таблицы в `core/models.py`:

| Таблица | Ключевые поля | Назначение |
|---|---|---|
| `users` | `telegram_id` (unique), `username` | Идентификация Telegram-пользователя |
| `conversations` | `user_id` (FK), `verdict_json` (JSON), `qualified` (bool), `finished_at` | Один сеанс квалификации; финальный вердикт LLM хранится как JSON-блоб |
| `messages` | `conversation_id` (FK), `role`, `content` | Лог ответов на вопросы FSM (RAG-обмены НЕ пишутся) |

FSM-состояние (`StepN`) в БД **не персистируется** — только в `MemoryStorage`.

---

## 4. Конфигурация — что есть и что нужно добавить

| Переменная | Дефолт в `config.py` | `.env.example` | Статус |
|---|---|---|---|
| `DATABASE_URL` | `sqlite+aiosqlite:///./dev.db` | ✅ | работает для dev |
| `QDRANT_URL` | `http://10.42.0.19:6333` | ✅ | ✅ wired |
| `QDRANT_API_KEY` | `""` | ✅ | ✅ wired (conditional) |
| `QDRANT_COLLECTION` | `kontur_kb` | ✅ | ✅ wired |
| `REDIS_URL` | **отсутствует** | **отсутствует** | ❌ не существует |

Redis в конфиге не заведён вообще — ни поля в `Settings`, ни строки в `.env.example`.

---

## 5. Деплой и запуск

**Dockerfile / docker-compose / systemd — отсутствуют.** Репозиторий содержит
только `Makefile` с `uv run`-командами для локальной разработки.

Бот работает в режиме **long polling** (`dp.start_polling(bot)`).
Webhook не настроен, webhook-endpoint в FastAPI-приложении не реализован.

---

## 6. Блокеры для Phase 4

В порядке приоритета:

### 6.1 `MemoryStorage` → `RedisStorage` (критично)

Без этого каждый перезапуск контейнера обрывает все активные диалоги.

Что нужно:
1. Добавить `aiogram-redis` / `redis` в зависимости
2. Добавить `REDIS_URL` в `config.py` и `.env.example`
3. В `apps/bot/main.py` заменить:
   ```python
   # было
   from aiogram.fsm.storage.memory import MemoryStorage
   dp = Dispatcher(storage=MemoryStorage())

   # станет
   from aiogram.fsm.storage.redis import RedisStorage
   dp = Dispatcher(storage=RedisStorage.from_url(settings.redis_url))
   ```

### 6.2 SQLite → PostgreSQL (критично)

SQLite не выдержит concurrent async-записей под нагрузкой и не подходит
для контейнерного деплоя (файл в CWD).

Что нужно:
1. Добавить `asyncpg` в зависимости (уже есть в `pyproject.toml`)
2. Поменять `DATABASE_URL` в `.env` на `postgresql+asyncpg://...`
3. Прогнать `alembic upgrade head` против Postgres — миграция одна, применится чисто

### 6.3 Dockerfile + docker-compose (критично)

Без контейнеризации нет воспроизводимого деплоя.

Минимальный состав:
- `Dockerfile` для бота (и API, если нужен)
- `docker-compose.yml` с сервисами: `bot`, `api`, `postgres`, `redis`
- `docker-compose.override.yml` для локального dev (монтирование исходников)

### 6.4 Polling → Webhook (желательно)

Long polling работает, но:
- требует постоянного исходящего соединения из контейнера
- хуже масштабируется
- на VPS предпочтительнее webhook через nginx/caddy

FastAPI-приложение уже есть (`apps/api/`) — webhook-роут там логично разместить.

### 6.5 `alembic.ini` — заглушка DSN (косметика)

```ini
# alembic.ini:89 — нерабочая строка, игнорируется env.py, но вводит в заблуждение
sqlalchemy.url = driver://user:pass@localhost/dbname
```

Стоит убрать или заменить на комментарий.

---

## Итог

```
dev-ready:   ✅ SQLite + MemoryStorage + polling — работает локально
prod-ready:  ❌ нет Docker, нет Postgres, нет Redis, нет webhook
```

Phase 4 = Dockerfile + compose + Postgres + Redis + (опционально) webhook.
Код приложения при этом меняется минимально — только DSN и storage.
