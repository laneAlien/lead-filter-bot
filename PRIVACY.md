# Политика конфиденциальности / Privacy Policy

**Язык / Language:** [Русский](#политика-конфиденциальности) · [English](#privacy-policy)

---

## Политика конфиденциальности

**Последнее обновление:** 24 июня 2026 г.

### О проекте

**lead-filter-bot** — учебно-демонстрационный проект (портфолио). Бот имитирует квалификацию входящих лидов для вымышленного digital-агентства «Контур Digital». Никакие реальные маркетинговые услуги не оказываются, оплата не принимается, настоящая компания за ботом не стоит.

### Какие данные собираются

При взаимодействии с ботом сохраняются:

| Данные | Источник | Зачем |
|---|---|---|
| Telegram user ID | Telegram API | идентификация пользователя |
| Telegram username (если задан) | Telegram API | читаемая метка в базе |
| Текст сообщений в ходе диалога | ввод пользователя | хранение истории разговора |
| Ответы на 5 квалификационных вопросов | ввод пользователя | бюджет, тип услуги, стадия бизнеса, срочность, опыт с агентствами |
| Вердикт и результат квалификации | сгенерировано LLM | итог сессии (JSON + булев флаг) |
| Временны́е метки начала/конца разговора | система | аудит, отладка |

Данные хранятся в приватной базе данных PostgreSQL, не доступной публично.

Бот **не** получает:
- номер телефона,
- email,
- геолокацию,
- медиафайлы.

### Передача данных третьим сторонам

Текст сообщений пользователя передаётся в **DeepSeek API** (api.deepseek.com) для:
- классификации намерения (вопрос или ответ),
- генерации ответов на вопросы по базе знаний агентства,
- формирования итогового вердикта квалификации.

Передача происходит без имён и контактных данных — только текст реплик. Условия обработки данных DeepSeek: [platform.deepseek.com/privacy](https://platform.deepseek.com/privacy).

Никакие другие третьи стороны доступа к данным не имеют.

### Хранение и сроки

Данные хранятся в демонстрационных целях без автоматического удаления. Поскольку проект является учебным и не ведёт коммерческой деятельности, формальная политика хранения не установлена.

### Запрос на удаление данных

Чтобы запросить удаление своих данных, откройте issue в репозитории проекта:

**https://github.com/laneAlien/lead-filter-bot/issues**

Укажите ваш Telegram username или user ID. Данные будут удалены вручную в разумные сроки.

### Правовая основа

Проект является некоммерческим демонстрационным и не подпадает под обязательное применение GDPR или аналогичных регуляторных режимов. Данные обрабатываются исключительно в учебных и демонстрационных целях.

### Контакт

GitHub: [github.com/laneAlien/lead-filter-bot](https://github.com/laneAlien/lead-filter-bot)

---

## Privacy Policy

**Last updated:** 24 June 2026

### About this project

**lead-filter-bot** is a portfolio / demonstration project. The bot simulates inbound lead qualification for a fictional digital agency called "Kontur Digital". No real marketing services are provided, no payment is accepted, and no actual company is behind this bot.

### What data is collected

When you interact with the bot, the following is stored:

| Data | Source | Purpose |
|---|---|---|
| Telegram user ID | Telegram API | identify the user |
| Telegram username (if set) | Telegram API | human-readable label in the DB |
| Message text during the dialogue | user input | store conversation history |
| Answers to 5 qualification questions | user input | budget, service type, business stage, urgency, agency experience |
| Qualification verdict and result | LLM-generated | outcome of the session (JSON + boolean flag) |
| Conversation start/end timestamps | system | auditing and debugging |

Data is stored in a private PostgreSQL database that is not publicly accessible.

The bot does **not** collect:
- phone number,
- email address,
- location data,
- media files.

### Third-party data transfers

Your message text is sent to the **DeepSeek API** (api.deepseek.com) for:
- intent classification (question vs. answer),
- generating answers to off-topic questions from the agency knowledge base,
- producing the final qualification verdict.

Only the text of your replies is transmitted — no names or contact details are attached. DeepSeek's data processing terms: [platform.deepseek.com/privacy](https://platform.deepseek.com/privacy).

No other third parties have access to your data.

### Retention

Data is retained for demonstration purposes with no automatic deletion schedule. As this is a non-commercial educational project, no formal retention policy is in place.

### Requesting deletion

To request deletion of your data, open an issue in the project repository:

**https://github.com/laneAlien/lead-filter-bot/issues**

Include your Telegram username or user ID. Data will be deleted manually within a reasonable time.

### Legal basis

This is a non-commercial demonstration project and is not subject to mandatory GDPR compliance or equivalent regulatory regimes. Data is processed solely for educational and portfolio purposes.

### Contact

GitHub: [github.com/laneAlien/lead-filter-bot](https://github.com/laneAlien/lead-filter-bot)
