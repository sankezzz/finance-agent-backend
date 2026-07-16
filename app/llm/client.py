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
    """Return the shared Groq client (created once, then cached).

    max_retries lets the SDK automatically back off and retry on 429
    rate-limit responses (respecting the retry-after header).
    """
    settings = get_settings()
    return Groq(api_key=settings.GROQ_API_KEY, max_retries=5)


@lru_cache
def get_structured_llm(mode: str = "tools"):
    """Groq client wrapped with `instructor` for validated structured output.

    Agents pass a Pydantic `response_model` and get back a validated object
    (instructor retries the model on schema mismatch). Imported lazily so a
    plain `import app...` never requires the instructor package at import time.

    mode="tools" uses function-calling (fine for capable models like scout).
    mode="json" asks the model to return a raw JSON object instead — more
    robust for smaller models (e.g. llama-3.1-8b) that mangle the tool-call
    wrapper and trip Groq's tool_use_failed. Cached per mode.
    """
    import instructor

    instructor_mode = instructor.Mode.JSON if mode == "json" else instructor.Mode.TOOLS
    return instructor.from_groq(get_llm(), mode=instructor_mode)

