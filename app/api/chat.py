from fastapi import APIRouter, File, Form, UploadFile

from app.api.schemas import ChatRequest, ChatResponse, SourceSnippetOut
from app.services.chat_async import ask_async, ask_from_image_async
from app.services.escalation import notify_support
from app.services.escalation_queue import enqueue
from app.services.session import append_message, get_history

router = APIRouter(prefix="/api/chat", tags=["chat"])


def _to_response(result, session_id: str, user_message: str) -> ChatResponse:
    snippets = [
        SourceSnippetOut(
            source=s.source,
            excerpt=s.excerpt,
            chunk_index=s.chunk_index,
            score=s.score,
            download_url=s.download_url,
        )
        for s in result.source_snippets
    ]
    return ChatResponse(
        answer=result.answer,
        confidence=result.confidence,
        sources=result.sources,
        needs_operator=result.needs_operator,
        escalated=result.escalated,
        images=result.images,
        source_snippets=snippets,
        user_question=result.user_question or user_message,
    )


@router.post("", response_model=ChatResponse)
async def chat(body: ChatRequest):
    append_message(body.session_id, "user", body.message)
    result = await ask_async(body.message, force_escalate=body.escalate)
    append_message(body.session_id, "assistant", result.answer)

    if result.escalated:
        label = body.user_label.strip() or f"Web ({body.session_id})"
        await notify_support(body.session_id, label, body.message)
        enqueue(body.session_id, label, body.message)

    return _to_response(result, body.session_id, body.message)


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
        enqueue(session_id, label, caption)

    return _to_response(result, session_id, caption)


@router.get("/messages/{session_id}")
async def chat_messages(session_id: str):
    return {"messages": get_history(session_id)}
