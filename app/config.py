"""Application configuration.

Reads settings from environment variables / .env via pydantic-settings.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Supabase — backend uses the SECRET key (bypasses RLS, server-side only).
    SUPABASE_URL: str
    SUPABASE_SECRET_KEY: str

    # LLM provider (Groq for now; abstracted behind app/llm/client.py).
    GROQ_API_KEY: str

    # Optional — used by the auth/JWT-verification phase, not the DB client.
    SUPABASE_PUBLISHABLE_KEY: str | None = None
    SUPABASE_JWKS_URL: str | None = None


@lru_cache
def get_settings() -> Settings:
    return Settings()
