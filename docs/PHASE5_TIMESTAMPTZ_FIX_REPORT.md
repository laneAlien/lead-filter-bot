# Phase 5 — Отчёт: фикс зависания квалификации (timestamptz + silent-hang)

**Дата:** 2026-06-12
**Ветка:** main (изменения в рабочем дереве, не закоммичены)
**Статус:** готово к ревью. Миграция **не применена**, коммита нет — по запросу.

---

## 1. Симптом

Диалог квалификации зависал на последнем шаге: пользователь видел
«Анализирую ваши ответы, секунду...» бесконечно, ответа не приходило.

## 2. Корневая причина (две связанные проблемы)

1. **Type-bug.** Колонки времени в `core/models.py` были объявлены как
   `DateTime` → в Postgres это `TIMESTAMP WITHOUT TIME ZONE` (naive). При этом
   код пишет tz-aware значение `datetime.now(UTC)`
   (`core/services/conversation.py:93`). Привязка tz-aware значения к naive
   колонке заставляет **asyncpg бросать `DataError`** на коммите.

2. **Silent-hang-bug.** Путь финализации в
   `apps/bot/handlers/dialogue.py::_finalize_and_respond` не имел обработки
   ошибок. Сообщение «Анализирую...» отправлялось **до** генерации вердикта и
   коммита, исключение проглатывалось, FSM оставался в состоянии
   `generating_verdict`. Пользователь висел навсегда, `/start` не помогал.

## 3. Что сделано

### 3.1 Типы колонок (`core/models.py`)

Все четыре временные колонки переведены на `DateTime(timezone=True)`
(`TIMESTAMP WITH TIME ZONE`):

| Таблица | Колонка | Было | Стало |
|---|---|---|---|
| users | created_at | DateTime | DateTime(timezone=True) |
| conversations | started_at | DateTime | DateTime(timezone=True) |
| conversations | finished_at | DateTime | DateTime(timezone=True) |
| messages | created_at | DateTime | DateTime(timezone=True) |

Аудит записи `datetime` по `core/`: единственная запись —
`datetime.now(UTC)` (tz-aware, консистентно). Naive `datetime.utcnow()` нигде
не используется. `server_default=func.now()` сохранён.

### 3.2 Миграция Alembic

Новый файл:
`migrations/versions/30531cd442f0_phase_5_timestamptz_for_all_datetime_.py`
(down_revision → `8aaa353472e8`, текущий head).

Эффективный SQL:

**upgrade** — существующие naive-строки трактуются как UTC:
```sql
ALTER TABLE users         ALTER COLUMN created_at  TYPE TIMESTAMPTZ USING created_at  AT TIME ZONE 'UTC';
ALTER TABLE conversations ALTER COLUMN started_at  TYPE TIMESTAMPTZ USING started_at  AT TIME ZONE 'UTC';
ALTER TABLE conversations ALTER COLUMN finished_at TYPE TIMESTAMPTZ USING finished_at AT TIME ZONE 'UTC';
ALTER TABLE messages      ALTER COLUMN created_at  TYPE TIMESTAMPTZ USING created_at  AT TIME ZONE 'UTC';
```

**downgrade** — обратная проекция в UTC wall-clock:
```sql
ALTER TABLE ... ALTER COLUMN ... TYPE TIMESTAMP USING ... AT TIME ZONE 'UTC';
```

`existing_server_default` сохранён на трёх колонках с дефолтом, чтобы Alembic
не сбросил `CURRENT_TIMESTAMP`.

### 3.3 Фикс зависания (`apps/bot/handlers/dialogue.py`)

Путь генерации вердикта + коммита + ответа обёрнут в `try/except/finally`:

- любое исключение логируется с трейсбеком
  (`logger.exception("Finalization failed for conversation_id=%s", conv_id)`);
- пользователю отправляется понятное сообщение:
  «Что-то пошло не так при обработке заявки. Попробуйте начать заново: /start»;
- `await state.clear()` вынесен в `finally` → FSM сбрасывается и при успехе, и
  при ошибке, `/start` всегда работает чисто.

Пользователь больше **никогда** не остаётся висеть на «Анализирую...».

### 3.4 Тесты (`tests/test_conversation_service.py`)

- `test_timestamp_columns_are_timezone_aware` — пинит схему: у каждой временной
  колонки `.type.timezone is True`.
- В `test_finalize_conversation_persists_verdict` добавлена проверка
  `updated.finished_at.tzinfo is not None` — пинит код (пишем tz-aware).

Вместе эти проверки поймали бы исходное рассогласование.

## 4. Проверки

```
make lint       → All checks passed!  (ruff check + format)
make typecheck  → Success: no issues found in 14 source files  (mypy strict)
make test       → 37 passed
```

Пин `openai<2` не тронут.

## 5. Следующий шаг (вручную, на homelab-хосте)

После ревью:

```bash
alembic upgrade head     # применяет 30531cd442f0
# затем перезапустить бота
```

Откат при необходимости: `alembic downgrade -1`.

## 6. Изменённые файлы

- `core/models.py`
- `core/services/conversation.py` — без изменений (уже tz-aware; подтверждено аудитом)
- `apps/bot/handlers/dialogue.py`
- `migrations/versions/30531cd442f0_phase_5_timestamptz_for_all_datetime_.py` (новый)
- `tests/test_conversation_service.py`
