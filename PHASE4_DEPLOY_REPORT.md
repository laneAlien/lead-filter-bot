# Phase 4 — Deploy & IaC Drift Fix: Session Report

**Date:** 2026-06-11  
**Branch:** main  
**Commits:** `5dbe950`, `688eb9f`

---

## What was done

### Phase 4 (previous session) — Containerization

Prepared the bot for production deploy on Aeza VPS:

- `MemoryStorage` → `RedisStorage` (`redis>=5`, `REDIS_URL` config field)
- Multi-stage `Dockerfile`: uv-based builder, `python:3.12-slim` runtime, non-root `botuser`, `HF_HOME` for fastembed cache
- `docker-compose.yml`: `bot` + `redis:7-alpine`; Postgres (10.42.0.20) and Qdrant (10.42.0.19) stay remote over WireGuard
- `docker-compose.override.yml`: source mount + SQLite override for local dev
- `entrypoint.sh`: runs `alembic upgrade head` before bot start (idempotent)
- `.env.example` updated with `REDIS_URL` and `HF_HOME`
- `core/config.py`: added `extra="ignore"` to `SettingsConfigDict` so Docker `ENV` vars don't crash pydantic-settings

During bring-up a casing bug was introduced: `"Leadbot"` (uppercase) was created manually
on the homelab Postgres, while the ansible-provisioned database is `"leadbot"` (lowercase).
The bot temporarily ran against `"Leadbot"`.

---

### This session — IaC drift fix + git hygiene

**Postgres cleanup (`10.42.0.20`):**

| Action | Result |
|--------|--------|
| Verified `leadbot` already had schema (alembic ran earlier) | 4 tables, 0 rows |
| Verified `Leadbot` also had schema, 0 rows in all tables | safe to drop |
| `DROP DATABASE "Leadbot"` | done |
| Confirmed only `leadbot` remains | ✓ |

**Git fixes (commit `688eb9f`):**

| File | Problem | Fix |
|------|---------|-----|
| `Dockerfile` | Builder `FROM ghcr.io/astral-sh/uv:python3.12-slim` — tag doesn't exist on ghcr.io | Changed to `python3.12-bookworm-slim` |
| `entrypoint.sh` | Mode `100644` in git — not executable on clean clone | `git update-index --chmod=+x` → `100755` |

---

## Current state

- **Postgres:** single DB `leadbot` (lowercase), schema applied, 0 rows
- **Dockerfile:** `ghcr.io/astral-sh/uv:python3.12-bookworm-slim` (verified working)
- **entrypoint.sh:** `100755` in git

## Pending (manual on homelab)

The bot containers ran from `/home/nosferatuton/lead-filter-bot/` (different machine).
That `.env` still has `DATABASE_URL=...5432/Leadbot`. Fix before next restart:

```bash
sed -i 's|/Leadbot|/leadbot|' /home/nosferatuton/lead-filter-bot/.env
cd /home/nosferatuton/lead-filter-bot
docker compose restart bot
docker compose logs --tail=20 bot
# Expected: "alembic: up to date", "Starting bot polling...", Qdrant 200 OK
```

---

## Roadmap

- [x] Phase 1: project skeleton, DeepSeek integration, /start handler, /health
- [x] Phase 2: full qualification dialogue (FSM, 5-question flow, DB persistence, Alembic)
- [x] Phase 3: RAG over agency knowledge base via Qdrant + intent classifier
- [x] Phase 4: Docker production deploy, Postgres, Redis FSM storage
- [ ] Phase 5: Tilda landing, Yandex.Metrica funnel, launch on Habr/VC.ru/Reddit
