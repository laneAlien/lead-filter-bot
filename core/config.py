from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_model: str = "deepseek-chat"

    telegram_bot_token: str = ""

    database_url: str = "sqlite+aiosqlite:///./dev.db"

    log_level: str = "INFO"
    env: str = "development"

    # RAG / Qdrant
    qdrant_url: str = "http://10.42.0.19:6333"
    qdrant_api_key: str = ""
    qdrant_collection: str = "kontur_kb"
    embedding_model: str = "intfloat/multilingual-e5-small"
    rag_top_k: int = 4
    rag_score_threshold: float = 0.0


@lru_cache
def get_settings() -> Settings:
    return Settings()
