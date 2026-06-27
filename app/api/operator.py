"""API панели оператора: очередь эскалаций и ответы пользователям."""
from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException

from app.api.schemas import OperatorReplyRequest
from app.config import settings
from app.services.escalation_queue import list_queue, resolve
from app.services.session import append_message, get_history

router = APIRouter(prefix="/api/operator", tags=["operator"])


def _check_pin(pin: str | None) -> None:
    expected = settings.operator_pin.strip()
    if not expected:
        return
    if not pin or pin.strip() != expected:
        raise HTTPException(401, "Неверный PIN оператора")


@router.get("/queue")
async def operator_queue(x_operator_pin: str | None = Header(default=None)):
    _check_pin(x_operator_pin)
    all_items = list_queue()
    waiting = [q for q in all_items if q.get("status") == "waiting"]
    resolved = [q for q in all_items if q.get("status") == "resolved"]
    return {"queue": waiting, "resolved": resolved, "total": len(waiting)}


@router.get("/sessions")
async def operator_sessions(x_operator_pin: str | None = Header(default=None)):
    _check_pin(x_operator_pin)
    return {"sessions": list_queue()}


@router.post("/reply")
async def operator_reply(body: OperatorReplyRequest, x_operator_pin: str | None = Header(default=None)):
    _check_pin(x_operator_pin)
    text = body.message.strip()
    if not text and not body.resolve:
        raise HTTPException(400, "Пустое сообщение")
    if text:
        append_message(body.session_id, "operator", text)
    if body.resolve:
        resolve(body.session_id)
    return {"ok": True}


@router.get("/messages/{session_id}")
async def session_messages(session_id: str):
    """Пользовательский long-poll: новые сообщения оператора в сессии."""
    history = get_history(session_id)
    operator_msgs = [m for m in history if m["role"] == "operator"]
    return {"messages": history, "operator_replies": operator_msgs}
