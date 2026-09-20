from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    app_name: str = "Enterprise RAG Copilot"
    environment: str = "development"
    api_prefix: str = "/api/v1"
    database_url: str = "postgresql+asyncpg://copilot:copilot@postgres:5432/copilot"
    redis_url: str = "redis://redis:6379/0"
    openai_api_key: str = ""
    chat_model: str = "gpt-4.1-mini"
    embedding_model: str = "text-embedding-3-small"
    model_mode: str = "demo"
    jwt_secret: str = "replace-in-production"
    allowed_origins: str = "http://localhost:5173"
    top_k: int = 6
    max_input_chars: int = 6000
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def cors_origins(self) -> list[str]:
        return [x.strip() for x in self.allowed_origins.split(",") if x.strip()]

@lru_cache
def settings() -> Settings:
    return Settings()
