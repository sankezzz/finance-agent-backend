"""LLM provider client abstraction.

Wraps whichever provider SDK is configured (Groq/Claude/Gemini) behind
a single interface so agents can be swapped between providers without
changing agent code.
"""
from functools import lru_cache

from groq import Groq

from app.config import get_settings


@lru_cache
def get_llm() -> Groq:
    """Return the shared Groq client (created once, then cached)."""
    settings = get_settings()
    return Groq(api_key=settings.GROQ_API_KEY)

