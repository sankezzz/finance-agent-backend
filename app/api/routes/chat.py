"""Chat routes.

Stateless natural-language chat over the user's financial data. The client
sends the conversation history; the server injects the latest snapshot as
grounding and returns the assistant's reply. Grounded in aggregated numbers
only (no raw transactions → no PII).
"""

from fastapi import APIRouter, HTTPException

from app.config import get_settings
from app.llm.client import get_llm
from app.llm.prompts.chat import build_chat_system
from app.models.chat import ChatRequest, ChatResponse
from app.services import financial_service, onboarding_service

router = APIRouter(prefix="/chat", tags=["chat"])

# Cap how much history we forward, to bound tokens on long conversations.
_MAX_HISTORY = 20


@router.post("", response_model=ChatResponse)
def chat(payload: ChatRequest) -> ChatResponse:
    """Answer a question grounded in the user's latest analysis."""
    if onboarding_service.get_user(payload.user_id) is None:
        raise HTTPException(status_code=404, detail="User not found")

    snapshot = financial_service.get_latest_snapshot(payload.user_id)
    if snapshot is None:
        raise HTTPException(
            status_code=404,
            detail="No analysis yet. Upload documents and run the pipeline first.",
        )

    user = onboarding_service.get_user(payload.user_id)
    system = build_chat_system(snapshot, user)
    history = payload.messages[-_MAX_HISTORY:]

    messages = [{"role": "system", "content": system}]
    messages += [{"role": m.role.value, "content": m.content} for m in history]

    resp = get_llm().chat.completions.create(
        model=get_settings().CHAT_GROQ_MODEL,
        messages=messages,
        temperature=0.4,
        max_tokens=800,
    )
    return ChatResponse(content=resp.choices[0].message.content or "")
