from functools import lru_cache
from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    app_env: str = "development"
    database_url: str = "sqlite:///./workbench.db"
    redis_url: str = "redis://localhost:6379/0"
    jwt_secret: str = "development-only-change-this-secret-before-deployment"
    frontend_url: str = "http://localhost:5173"
    cookie_secure: bool = False
    access_minutes: int = 15
    refresh_days: int = 7
    groq_api_key: str = ""
    groq_model: str = "llama-3.3-70b-versatile"
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    local_model_url: str = "http://localhost:8080/v1"
    local_model_name: str = "local"
    enable_local_model: bool = False
    embedding_mode: str = "hashing"
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    smtp_host: str = "localhost"
    smtp_port: int = 1025
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_starttls: bool = False
    mail_from: str = "Workbench <noreply@workbench.local>"
    eager_jobs: bool = False
    max_upload_bytes: int = 5 * 1024 * 1024
    max_documents: int = 50
    max_chunks: int = 5000
    max_runs_per_day: int = 100
    artifact_dir: str = "./artifacts"

    @model_validator(mode="after")
    def production_checks(self):
        if self.app_env == "production":
            if len(self.jwt_secret) < 32 or self.jwt_secret.startswith("development-"):
                raise ValueError("Set a strong JWT_SECRET for production")
            if not self.cookie_secure or not self.frontend_url.startswith("https://"):
                raise ValueError("Production requires HTTPS and COOKIE_SECURE=true")
            if self.database_url.startswith("sqlite") or self.eager_jobs:
                raise ValueError("Production requires PostgreSQL and non-eager workers")
        return self


@lru_cache
def get_settings():
    return Settings()
