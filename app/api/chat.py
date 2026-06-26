from fastapi import APIRouter, File, Form, UploadFile

from app.api.schemas import ChatRequest, ChatResponse
from app.services.chat_async import ask_async, ask_from_image_async
from app.services.escalation import notify_support
from app.services.session import append_message

router = APIRouter(prefix="/api/chat", tags=["chat"])


@router.post("", response_model=ChatResponse)
async def chat(body: ChatRequest):
    append_message(body.session_id, "user", body.message)
    result = await ask_async(body.message, force_escalate=body.escalate)
    append_message(body.session_id, "assistant", result.answer)

    if result.escalated:
        label = body.user_label.strip() or f"Web ({body.session_id})"
        await notify_support(body.session_id, label, body.message)

    return ChatResponse(
        answer=result.answer,
        confidence=result.confidence,
        sources=result.sources,
        needs_operator=result.needs_operator,
        escalated=result.escalated,
        images=result.images,
    )


@router.post("/image", response_model=ChatResponse)
async def chat_image(
    file: UploadFile = File(...),
    message: str = Form(""),
    session_id: str = Form("web-default"),
    user_label: str = Form("Web UI"),
    escalate: bool = Form(False),
):
    data = await file.read()
    caption = message.strip() or "Что на этом скриншоте? Подскажите по документации."
    append_message(session_id, "user", f"[изображение] {caption}")

    if escalate:
        result = await ask_async("оператор", force_escalate=True)
    else:
        result = await ask_from_image_async(data, caption)

    append_message(session_id, "assistant", result.answer)

    if result.escalated:
        label = user_label.strip() or f"Web ({session_id})"
        await notify_support(session_id, label, caption)

    return ChatResponse(
        answer=result.answer,
        confidence=result.confidence,
        sources=result.sources,
        needs_operator=result.needs_operator,
        escalated=result.escalated,
        images=result.images,
    )
