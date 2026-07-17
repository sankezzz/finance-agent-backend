"""Chat schemas.

Stateless chat: the client holds the conversation and sends the full message
history each call; the server injects the financial grounding (snapshot) and
returns the assistant's reply. No server-side session state.
"""

from enum import Enum

from pydantic import BaseModel, Field


class ChatRole(str, Enum):
    user = "user"
    assistant = "assistant"


class ChatMessage(BaseModel):
    role: ChatRole
    content: str = Field(min_length=1)


class ChatRequest(BaseModel):
    user_id: str
    messages: list[ChatMessage] = Field(min_length=1)


class ChatResponse(BaseModel):
    role: ChatRole = ChatRole.assistant
    content: str
