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
    # Per-plugin auth state. Keys are plugin names, values are True/False.
    # The chat router injects this into the system context so Jain can decide
    # whether to call auth-required tools or prompt the user to log in first.
    auth: dict[str, bool] = Field(default_factory=dict)


class ChatResponse(BaseModel):
    reply: str
    data: Any | None = None
    display_hint: str | None = None
    tool_events: list[dict[str, Any]] = Field(default_factory=list)
