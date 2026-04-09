from fastapi import APIRouter, Depends

from app.dependencies import get_chat_service
from app.engine.base import ChatMessage
from app.schemas.chat import ChatRequest, ChatResponse
from app.services.chat_service import ChatService

router = APIRouter(prefix="/api/chat", tags=["chat"])


@router.post("", response_model=ChatResponse)
async def chat(
    req: ChatRequest,
    service: ChatService = Depends(get_chat_service),
) -> ChatResponse:
    messages = [ChatMessage(role=turn.role, content=turn.content) for turn in req.history]

    user_content = req.message
    if req.lat is not None and req.lng is not None:
        user_content = f"[user location: lat={req.lat}, lng={req.lng}]\n{req.message}"
    messages.append(ChatMessage(role="user", content=user_content))

    reply = await service.send(conversation=messages)
    return ChatResponse(
        reply=reply.text,
        data=reply.data,
        display_hint=reply.display_hint,
        tool_events=reply.tool_events,
    )
