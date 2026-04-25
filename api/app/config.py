from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    database_url: str = "postgresql+psycopg://veros:veros@localhost:5432/veros"
    redis_url: str = "redis://localhost:6379/0"

    llm_provider: str = "zai"  # "zai" | "gemini"

    zai_api_key: str = ""
    zai_base_url: str = "https://api.z.ai/api/paas/v4/"
    zai_model: str = "glm-4.6"

    gemini_api_key: str = ""
    gemini_base_url: str = "https://generativelanguage.googleapis.com/v1beta/openai/"
    gemini_model: str = "gemini-2.5-flash"

    openreview_username: str = ""
    openreview_password: str = ""

    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"

    demo_user_id: str = "demo-user"
    demo_user_email: str = "demo@veros.local"

    cors_origins: str = "http://localhost:3000"
    log_level: str = "INFO"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
