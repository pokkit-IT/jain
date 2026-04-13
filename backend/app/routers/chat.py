from anthropic import APIStatusError
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.optional_user import get_current_user_optional
from app.database import get_db
from app.dependencies import get_chat_service
from app.engine.base import ChatMessage
from app.models.user import User
from app.schemas.chat import ChatRequest, ChatResponse
from app.services.chat_service import ChatService

router = APIRouter(prefix="/api/chat", tags=["chat"])


@router.post("", response_model=ChatResponse)
async def chat(
    req: ChatRequest,
    user: User | None = Depends(get_current_user_optional),
    service: ChatService = Depends(get_chat_service),
    db: AsyncSession = Depends(get_db),
) -> ChatResponse:
    messages = [ChatMessage(role=turn.role, content=turn.content) for turn in req.history]

    context_lines: list[str] = []
    if req.lat is not None and req.lng is not None:
        context_lines.append(f"[user location: lat={req.lat}, lng={req.lng}]")

    user_content = (
        "\n".join(context_lines) + "\n" + req.message if context_lines else req.message
    )
    messages.append(ChatMessage(role="user", content=user_content))

    try:
        reply = await service.send(conversation=messages, user=user, db=db)
    except APIStatusError as exc:
        if exc.status_code in (429, 502, 503, 504, 529):
            raise HTTPException(
                status_code=503,
                detail="The model is overloaded right now. Please try again in a moment.",
            ) from exc
        raise
    return ChatResponse(
        reply=reply.text,
        data=reply.data,
        display_hint=reply.display_hint,
        tool_events=reply.tool_events,
        choices=reply.choices,
    )
