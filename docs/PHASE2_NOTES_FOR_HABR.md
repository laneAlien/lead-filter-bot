# Заметки по Фазе 2 — пока в памяти свежо
> lead-filter-bot · 2026-06-03 · для будущей Хабр-статьи

---

## Что было сложно

### 1. Непортируемый venv
Самый неожиданный блокер в самом начале. Venv создавался на машине пользователя
(`/home/nosferatuton/`), а сессия запускается под `/root/`. Все shebang-и в `.venv/bin/*`
смотрят на несуществующий путь. Скрипты есть, выглядят нормально — но `cannot execute:
required file not found` при каждом запуске.

**Решение:** `curl astral.sh/uv/install.sh | sh` → `rm -rf .venv` → `uv sync --all-extras`.
Всё пересоздалось за 20 секунд. Урок: venv не портируется между машинами/пользователями,
lockfile (`uv.lock`) — портируется.

### 2. Alembic autogenerate вернул пустую миграцию
`alembic revision --autogenerate` → смотришь файл → `pass` внутри `upgrade()`. Неприятный
сюрприз. Причина: `dev.db` уже содержала таблицы от `init_db()` (SQLAlchemy `create_all`
при старте бота в Фазе 1). Alembic сравнивает модели с живой БД — если таблицы есть,
он считает что всё ок.

**Решение:** удалить `dev.db`, повторить — autogenerate подхватил все 3 таблицы и 3
индекса. Порядок важен: сначала чистая БД, потом autogenerate.

### 3. Ruff нашёл 14 ошибок в авто-сгенерированном коде
Alembic генерирует migration-файлы со своим стилем: `Union[str, Sequence[str], None]`,
`from typing import Sequence`, строки длиннее 100 символов, несортированные импорты.
Ruff со строгими настройками всё это режет.

**Решение:** переписал migration-файл руками в современный стиль (`str | Sequence[str] | None`,
`from collections.abc import Sequence`, перенос длинных строк). Это разовая работа, но
неочевидно что autogenerate и линтер будут конфликтовать.

### 4. mypy поймал тип в generate_verdict
```python
messages = [
    {"role": "system", "content": "..."},  # это dict[str, str]
    {"role": "user", "content": "..."},
]
await llm.chat_structured(messages, QualifierVerdict)  # ожидает list[ChatCompletionMessageParam]
```
Mypy прав — `dict[str, str]` шире чем `ChatCompletionMessageParam` (TypedDict из openai SDK).

**Решение:** явная аннотация `messages: list[ChatCompletionMessageParam] = [...]` + импорт
типа. Одна строка, но без mypy это была бы молчаливая несовместимость.

---

## Что было легко (удивило)

### aiogram 3 DI через workflow_data
Ожидал что dependency injection в боте будет громоздким. Оказалось:

```python
# При старте:
dp.workflow_data.update(session_factory=get_sessionmaker(), llm=LLMClient())

# В хендлере — просто объявить параметр:
async def handle_budget(message, state, session_factory, llm): ...
```

aiogram 3 сам матчит по имени параметра. Никаких декораторов, никаких Depends(). Чисто.

### 6 интеграционных тестов — все зелёные с первого прогона
Писал тесты после сервисного слоя, не до. Ожидал хотя бы пару красных. Запустил —
`6 passed`. In-memory SQLite + pytest-asyncio + фикстура `db_session` работают без сюрпризов.

### DeepSeek корректно квалифицировал все три smoke-теста
Три живых диалога через Telegram — бедный лид, богатый лид, уклончивый. Все три вердикта
правильные с первого раза. QUALIFIER_SYSTEM_PROMPT с чёткими критериями (бюджет ≥ 30k,
working/enterprise, immediate/month) работает без fine-tuning.

### Alembic env.py для async SQLite — минимум правок
Шаблон `alembic init -t async` уже содержит всю async-обвязку (`run_async_migrations`,
`async_engine_from_config`). Нужно было добавить только:
```python
from core.models import Base
from core.config import get_settings
target_metadata = Base.metadata
config.set_main_option("sqlalchemy.url", get_settings().database_url)
```
Четыре строки — и autogenerate видит модели.

---

## Что с первого раза, что с третьего

| Что | Попыток | Комментарий |
|---|---|---|
| 6 интеграционных тестов | **1** | Все зелёные сразу |
| DI через workflow_data | **1** | Паттерн интуитивный |
| Alembic upgrade head | **1** | После правки env.py |
| DeepSeek smoke-тест x3 | **1** | Промпт хорошо написан |
| Alembic autogenerate | **2** | Пустая миграция → удалить DB → снова |
| Lint (ruff) | **2** | 14 ошибок → правка migration + conv.py → чисто |
| mypy | **2** | Тип ChatCompletionMessageParam надо было явно аннотировать |
| Запуск venv | **3** | Непортируемый → установка uv → пересоздание |

---

## Команды и инструменты, которые запомнились

### `uv sync --all-extras`
62 пакета, ~20 секунд. После pip это ощущается как телепортация. Lockfile (`uv.lock`)
воспроизводит окружение точно — включая Python версию (скачал 3.14.5 сам).

### `alembic init -t async`
Флаг `-t async` — не очевидный, но критичный. Без него получаешь синхронный шаблон,
который с `aiosqlite`/`asyncpg` не заработает. Шаблон уже содержит `asyncio.run()` и
`async_engine_from_config`.

### aiogram 3 FSM
`StatesGroup` + `State()` + `@router.message(MyFSM.some_state)` — декларативно и читаемо.
Переход: `await state.set_state(NextState.value)`. Данные между состояниями:
`await state.update_data(key=value)` / `await state.get_data()`.

### `chat_structured[T: BaseModel]()`
PEP 695 generic-синтаксис (Python 3.12+). Вызов: `await llm.chat_structured(messages, QualifierVerdict)`.
Возвращает типизированный Pydantic-объект. JSON mode + `model_validate` под капотом —
структурированный вывод без ручного парсинга.

### Паттерн lazy `@lru_cache` для engine
```python
@lru_cache
def get_engine() -> AsyncEngine:
    return create_async_engine(get_settings().database_url)
```
Без этого engine создаётся при импорте — до того как тестовые fixtures успели подменить
DATABASE_URL. С lru_cache — создаётся лениво, тесты работают изолированно.

---

## Цифры сессии

- Файлов изменено/создано: **15**
- Строк добавлено: **916**
- Тестов: было 11 → стало **17** (все зелёные)
- Smoke-тестов через живой Telegram: **3/3 корректных вердикта**
- Время сессии: ~30 минут

---

## Что сказать в Хабр-статье

> «FSM в aiogram 3 + DI через workflow_data — это то, о чём не пишут в туториалах, но что
> делает архитектуру бота чистой. Никакого глобального состояния, никаких синглтонов руками.»

> «Alembic autogenerate — мощный инструмент, но он сравнивает модели с живой БД. Если БД
> уже содержит таблицы — получишь пустую миграцию. Всегда стартуй autogenerate на чистой базе.»

> «uv — это не просто быстрый pip. Это менеджер Python-версий, venv, зависимостей и
> lockfile в одном бинарнике. После него возвращаться к pip+venv физически больно.»
