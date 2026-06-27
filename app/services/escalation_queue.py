"""Очередь эскалаций для веб-панели оператора."""
from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass

from redis import Redis

from app.config import settings
from app.services.session import get_history
from app.services.tickets import get_ticket

logger = logging.getLogger(__name__)

QUEUE_KEY = "escalations:queue"
_redis_ok: bool | None = None
_mem_queue: list[dict] = []


def _ping_redis() -> bool:
    global _redis_ok
    if _redis_ok is not None:
        return _redis_ok
    try:
        Redis.from_url(settings.redis_url, socket_connect_timeout=2).ping()
        _redis_ok = True
    except Exception as exc:
        logger.warning("Redis unavailable for escalation queue: %s", exc)
        _redis_ok = False
    return _redis_ok


def _redis() -> Redis:
    return Redis.from_url(settings.redis_url, decode_responses=True, socket_connect_timeout=2)


@dataclass
class EscalationItem:
    session_id: str
    user_label: str
    question: str
    ts: float
    status: str = "waiting"


def enqueue(session_id: str, user_label: str, question: str = "") -> None:
    item = {
        "session_id": session_id,
        "user_label": user_label,
        "question": question,
        "ts": time.time(),
        "status": "waiting",
    }
    if _ping_redis():
        try:
            r = _redis()
            raw = r.hget(QUEUE_KEY, session_id)
            if raw:
                existing = json.loads(raw)
                existing["question"] = question or existing.get("question", "")
                existing["ts"] = item["ts"]
                existing["status"] = "waiting"
                item = existing
            r.hset(QUEUE_KEY, session_id, json.dumps(item, ensure_ascii=False))
            r.expire(QUEUE_KEY, 86400 * 7)
            return
        except Exception:
            pass
    for i, row in enumerate(_mem_queue):
        if row["session_id"] == session_id:
            _mem_queue[i] = item
            return
    _mem_queue.append(item)


def list_queue() -> list[dict]:
    items: list[dict] = []
    if _ping_redis():
        try:
            raw = _redis().hgetall(QUEUE_KEY)
            items = [json.loads(v) for v in raw.values()]
        except Exception:
            items = list(_mem_queue)
    else:
        items = list(_mem_queue)

    out = []
    for row in sorted(items, key=lambda x: x.get("ts", 0), reverse=True):
        sid = row["session_id"]
        history = get_history(sid)
        out.append(
            {
                **row,
                "history": history,
                "message_count": len(history),
                "ticket": get_ticket(sid),
            }
        )
    return out


def resolve(session_id: str) -> None:
    if _ping_redis():
        try:
            raw = _redis().hget(QUEUE_KEY, session_id)
            if raw:
                item = json.loads(raw)
                item["status"] = "resolved"
                _redis().hset(QUEUE_KEY, session_id, json.dumps(item, ensure_ascii=False))
            return
        except Exception:
            pass
    for row in _mem_queue:
        if row["session_id"] == session_id:
            row["status"] = "resolved"
