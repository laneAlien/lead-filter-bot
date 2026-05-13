import logging

from fastapi import FastAPI

from apps.api.routers import health, qualify
from core.config import get_settings
from core.db import init_db

settings = get_settings()
logging.basicConfig(level=settings.log_level.upper())

app = FastAPI(title="lead-filter-bot API", version="0.1.0")

app.include_router(health.router)
app.include_router(qualify.router)


@app.on_event("startup")
async def on_startup() -> None:
    await init_db()


def main() -> None:
    import uvicorn

    uvicorn.run("apps.api.main:app", host="0.0.0.0", port=8000, reload=False)


if __name__ == "__main__":
    main()
