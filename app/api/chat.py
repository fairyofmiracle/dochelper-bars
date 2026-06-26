from fastapi import APIRouter

from app.api.schemas import ChatRequest, ChatResponse
from app.services.chat_async import ask_async
from app.services.session import append_message

router = APIRouter(prefix="/api/chat", tags=["chat"])


@router.post("", response_model=ChatResponse)
async def chat(body: ChatRequest):
    append_message(body.session_id, "user", body.message)
    result = await ask_async(body.message, force_escalate=body.escalate)
    append_message(body.session_id, "assistant", result.answer)
    return ChatResponse(
        answer=result.answer,
        confidence=result.confidence,
        sources=result.sources,
        needs_operator=result.needs_operator,
        escalated=result.escalated,
    )
