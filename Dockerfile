# ── builder: install deps into an isolated venv ───────────────────────────────
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS builder

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# ── runtime: lean image, non-root user ────────────────────────────────────────
FROM python:3.12-slim AS runtime

WORKDIR /app

COPY --from=builder /app/.venv /app/.venv

COPY . .

ENV PATH="/app/.venv/bin:$PATH"
ENV HF_HOME=/app/.cache/huggingface

RUN groupadd -r botuser && useradd -r -g botuser botuser \
    && mkdir -p /app/.cache/huggingface \
    && chmod +x /app/entrypoint.sh \
    && chown -R botuser:botuser /app

USER botuser

ENTRYPOINT ["/app/entrypoint.sh"]
