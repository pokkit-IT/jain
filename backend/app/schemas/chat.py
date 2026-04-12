from typing import Any

from pydantic import BaseModel, Field


class ChatTurnIn(BaseModel):
    role: str  # "user" | "assistant"
    content: str


class ChatRequest(BaseModel):
    message: str
    history: list[ChatTurnIn] = Field(default_factory=list)
    lat: float | None = None
    lng: float | None = None


class ChatResponse(BaseModel):
    reply: str
    data: Any | None = None
    display_hint: str | None = None
    tool_events: list[dict[str, Any]] = Field(default_factory=list)
    choices: list[str] | None = None
