"""Тикеты во внешние TMS (Usedesk / Jira / Zendesk) — mock для демо + опциональный API."""
from __future__ import annotations

import json
import logging
import random
import time
from dataclasses import dataclass

import httpx
from redis import Redis

from app.config import settings
from app.services.session import format_history_for_escalation

logger = logging.getLogger(__name__)

TICKETS_KEY = "tickets:by_session"
_redis_ok: bool | None = None
_mem_tickets: dict[str, dict] = {}


@dataclass
class TicketInfo:
    provider: str
    ticket_id: str
    url: str
    status: str = "open"
    created_at: float = 0.0

    def to_dict(self) -> dict:
        return {
            "provider": self.provider,
            "ticket_id": self.ticket_id,
            "url": self.url,
            "status": self.status,
            "created_at": self.created_at,
        }


def _ping_redis() -> bool:
    global _redis_ok
    if _redis_ok is not None:
        return _redis_ok
    try:
        Redis.from_url(settings.redis_url, socket_connect_timeout=2).ping()
        _redis_ok = True
    except Exception as exc:
        logger.warning("Redis unavailable for tickets: %s", exc)
        _redis_ok = False
    return _redis_ok


def _redis() -> Redis:
    return Redis.from_url(settings.redis_url, decode_responses=True, socket_connect_timeout=2)


def _save_ticket(session_id: str, ticket: TicketInfo) -> None:
    data = ticket.to_dict()
    if _ping_redis():
        try:
            r = _redis()
            r.hset(TICKETS_KEY, session_id, json.dumps(data, ensure_ascii=False))
            r.expire(TICKETS_KEY, 86400 * 30)
            return
        except Exception:
            pass
    _mem_tickets[session_id] = data


def get_ticket(session_id: str) -> dict | None:
    if _ping_redis():
        try:
            raw = _redis().hget(TICKETS_KEY, session_id)
            if raw:
                return json.loads(raw)
        except Exception:
            pass
    return _mem_tickets.get(session_id)


def _mock_ticket_id(provider: str) -> str:
    prefix = {"usedesk": "USD", "jira": "BARS", "zendesk": "ZD"}.get(provider, "TKT")
    return f"{prefix}-{time.strftime('%y%m')}{random.randint(1000, 9999)}"


def _ticket_url(provider: str, ticket_id: str) -> str:
    base = settings.ticket_base_url.strip().rstrip("/")
    if base:
        return f"{base}/{ticket_id}"
    labels = {
        "usedesk": "Usedesk",
        "jira": "Jira",
        "zendesk": "Zendesk",
    }
    label = labels.get(provider, provider)
    return f"/operator#ticket-{ticket_id} ({label} demo — ответ в панели оператора)"


def _try_usedesk_api(session_id: str, user_label: str, question: str, history: str) -> TicketInfo | None:
    url = settings.usedesk_api_url.strip()
    token = settings.usedesk_api_token.strip()
    if not url or not token:
        return None
    payload = {
        "subject": f"DocHelper: {question[:120] or 'эскалация'}",
        "message": history,
        "client_name": user_label,
        "tags": ["dochelper", session_id],
    }
    try:
        r = httpx.post(
            url.rstrip("/") + "/create/ticket",
            json=payload,
            headers={"Authorization": f"Bearer {token}"},
            timeout=15.0,
        )
        if r.status_code >= 400:
            logger.warning("Usedesk API %s: %s", r.status_code, r.text[:200])
            return None
        data = r.json()
        tid = str(data.get("ticket_id") or data.get("id") or _mock_ticket_id("usedesk"))
        return TicketInfo("usedesk", tid, _ticket_url("usedesk", tid))
    except Exception as exc:
        logger.warning("Usedesk ticket failed: %s", exc)
        return None


def create_escalation_ticket(
    session_id: str,
    user_label: str,
    question: str = "",
) -> TicketInfo | None:
    """Создаёт тикет при эскалации. По умолчанию — mock для демо на защите."""
    provider = settings.ticket_provider.strip().lower()
    if provider in ("", "none", "off"):
        return None

    existing = get_ticket(session_id)
    if existing:
        return TicketInfo(**existing)

    history = format_history_for_escalation(session_id)
    ticket: TicketInfo | None = None

    if provider == "usedesk":
        ticket = _try_usedesk_api(session_id, user_label, question, history)
    if ticket is None:
        pid = provider if provider in ("usedesk", "jira", "zendesk") else "usedesk"
        tid = _mock_ticket_id(pid)
        ticket = TicketInfo(pid, tid, _ticket_url(pid, tid))

    ticket.created_at = time.time()
    _save_ticket(session_id, ticket)
    logger.info("Ticket %s for session %s (%s)", ticket.ticket_id, session_id, ticket.provider)
    return ticket


def close_ticket(session_id: str) -> None:
    row = get_ticket(session_id)
    if not row:
        return
    row["status"] = "closed"
    if _ping_redis():
        try:
            _redis().hset(TICKETS_KEY, session_id, json.dumps(row, ensure_ascii=False))
            return
        except Exception:
            pass
    _mem_tickets[session_id] = row
