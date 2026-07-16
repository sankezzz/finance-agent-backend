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
    # llama-4-scout: non-reasoning (no wasted "thinking" tokens), reliable
    # tool-calling, and the best free-tier limits for extraction-sized calls
    # (TPM 30K / TPD 500K — vs 12K/100K on llama-3.3-70b, which rate-limited us).
    GROQ_API_KEY: str
    PARSER_GROQ_MODEL: str = "meta-llama/llama-4-scout-17b-16e-instruct"
    # Categorizer only classifies unknown merchant names (a small, easy task),
    # so a fast/cheap model is fine — and it uses a separate TPM bucket from
    # the parser's model.
    CATEGORIZER_GROQ_MODEL: str = "llama-3.1-8b-instant"
    # Recommendations are quality-sensitive (advice grounded in the numbers),
    # so use a stronger model. One short call per run — TPM isn't a concern.
    RECOMMENDATION_GROQ_MODEL: str = "llama-3.3-70b-versatile"
    # Cap output high enough that a full statement's extracted JSON isn't
    # truncated mid-tool-call (which surfaces as Groq's tool_use_failed).
    GROQ_MAX_TOKENS: int = 25000

    # Optional — used by the auth/JWT-verification phase, not the DB client.
    SUPABASE_PUBLISHABLE_KEY: str | None = None
    SUPABASE_JWKS_URL: str | None = None


@lru_cache
def get_settings() -> Settings:
    return Settings()
