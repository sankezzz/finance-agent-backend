"""Application configuration.

Reads settings from environment variables / .env via pydantic-settings.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    SUPABASE_URL: str
    SUPABASE_KEY: str
    LLM_API_KEY: str


@lru_cache
def get_settings() -> Settings:
    return Settings()
