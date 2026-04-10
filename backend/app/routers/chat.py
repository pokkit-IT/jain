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

    context_lines: list[str] = []
    if req.lat is not None and req.lng is not None:
        context_lines.append(f"[user location: lat={req.lat}, lng={req.lng}]")
    if req.auth:
        auth_pairs = ", ".join(
            f"{name}={'logged_in' if v else 'not_logged_in'}"
            for name, v in sorted(req.auth.items())
        )
        context_lines.append(f"[auth state: {auth_pairs}]")

    user_content = (
        "\n".join(context_lines) + "\n" + req.message if context_lines else req.message
    )
    messages.append(ChatMessage(role="user", content=user_content))

    reply = await service.send(conversation=messages)
    return ChatResponse(
        reply=reply.text,
        data=reply.data,
        display_hint=reply.display_hint,
        tool_events=reply.tool_events,
    )
