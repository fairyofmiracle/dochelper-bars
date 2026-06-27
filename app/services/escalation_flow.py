"""Единая точка эскалации: очередь оператора + TMS-тикет + Telegram."""
from __future__ import annotations

from app.services.escalation import notify_support
from app.services.escalation_queue import enqueue
from app.services.tickets import create_escalation_ticket


async def escalate_session(
    session_id: str,
    user_label: str,
    question: str = "",
) -> dict | None:
    """Поставить в очередь оператора и создать тикет (Usedesk/Jira demo)."""
    enqueue(session_id, user_label, question)
    ticket = create_escalation_ticket(session_id, user_label, question)
    await notify_support(session_id, user_label, question)
    return ticket.to_dict() if ticket else None
