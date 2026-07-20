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
    PARSER_GROQ_MODEL: str = "llama-3.1-8b-instant"
    # Categorizer only classifies unknown merchant names (a small, easy task),
    # so a fast/cheap model is fine — and it uses a separate TPM bucket from
    # the parser's model.
    CATEGORIZER_GROQ_MODEL: str = "llama-3.1-8b-instant"
    # Recommendations are quality-sensitive (advice grounded in the numbers),
    # so use a stronger model. One short call per run — TPM isn't a concern.
    RECOMMENDATION_GROQ_MODEL: str = "openai/gpt-oss-120b"
    # Chat is high-frequency (many messages), so favour a model with generous
    # rate limits (scout: TPM 30K / TPD 500K) that's still good at grounded Q&A.
    CHAT_GROQ_MODEL: str = "openai/gpt-oss-120b"
    # Cap output high enough that a full statement's extracted JSON isn't
    # truncated mid-tool-call, but within the model's ceiling: llama-4-scout
    # allows at most 8192 output tokens, so keep this <= 8192. 
    GROQ_MAX_TOKENS: int = 4000 #this is the output tokens

    # Comma-separated allowed origins for CORS ("*" = allow all, fine for MVP
    # since we don't use cookies — the frontend sends user_id explicitly).
    CORS_ORIGINS: str = "*"

    # Optional — used by the auth/JWT-verification phase, not the DB client.
    SUPABASE_PUBLISHABLE_KEY: str | None = None
    SUPABASE_JWKS_URL: str | None = None

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
