from fastapi import APIRouter, File, Form, UploadFile

from app.api.schemas import ChatRequest, ChatResponse, SourceSnippetOut
from app.services.analytics import record_rate_limit
from app.services.chat_async import ask_async, ask_from_image_async
from app.services.escalation_flow import escalate_session
from app.services.rate_limit import check_rate_limit, rate_limit_message
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
        image_type=getattr(result, "image_type", "") or "",
        image_preview=getattr(result, "image_preview", "") or "",
    )


def _blocked_response(message: str, user_message: str) -> ChatResponse:
    return ChatResponse(
        answer=message,
        confidence=0.0,
        sources=[],
        needs_operator=False,
        escalated=False,
        images=[],
        source_snippets=[],
        user_question=user_message,
    )


@router.post("", response_model=ChatResponse)
async def chat(body: ChatRequest):
    rl = check_rate_limit(body.session_id, body.message)
    if not rl.allowed:
        record_rate_limit(body.session_id, body.message)
        msg = rate_limit_message(rl)
        append_message(body.session_id, "user", body.message)
        append_message(body.session_id, "assistant", msg)
        return _blocked_response(msg, body.message)

    append_message(body.session_id, "user", body.message)
    result = await ask_async(body.message, force_escalate=body.escalate)
    append_message(body.session_id, "assistant", result.answer)

    if result.escalated:
        label = body.user_label.strip() or f"Web ({body.session_id})"
        await escalate_session(body.session_id, label, body.message)

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
    rl = check_rate_limit(session_id, caption)
    if not rl.allowed:
        record_rate_limit(session_id, caption)
        msg = rate_limit_message(rl)
        append_message(session_id, "user", f"[изображение] {caption}")
        append_message(session_id, "assistant", msg)
        return _blocked_response(msg, caption)

    append_message(session_id, "user", f"[изображение] {caption}")

    if escalate:
        result = await ask_async("оператор", force_escalate=True)
    else:
        result = await ask_from_image_async(data, caption)

    append_message(session_id, "assistant", result.answer)

    if result.escalated:
        label = user_label.strip() or f"Web ({session_id})"
        await escalate_session(session_id, label, caption)

    return _to_response(result, session_id, caption)


@router.get("/messages/{session_id}")
async def chat_messages(session_id: str):
    return {"messages": get_history(session_id)}
