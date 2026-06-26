"""Redis with in-memory fallback if Docker Redis is down."""
from __future__ import annotations

import json
import logging
from collections import defaultdict, deque

from redis import Redis

from app.config import settings

logger = logging.getLogger(__name__)

MAX_HISTORY = 20
_mem_sessions: dict[str, deque] = defaultdict(lambda: deque(maxlen=MAX_HISTORY))
_redis_ok: bool | None = None


def _ping_redis() -> bool:
    global _redis_ok
    if _redis_ok is not None:
        return _redis_ok
    try:
        Redis.from_url(settings.redis_url, socket_connect_timeout=2).ping()
        _redis_ok = True
    except Exception as exc:
        logger.warning("Redis unavailable, using in-memory sessions: %s", exc)
        _redis_ok = False
    return _redis_ok


def _redis() -> Redis:
    return Redis.from_url(settings.redis_url, decode_responses=True, socket_connect_timeout=2)


def append_message(session_id: str, role: str, content: str) -> None:
    entry = {"role": role, "content": content}
    if _ping_redis():
        try:
            r = _redis()
            key = f"session:{session_id}"
            r.rpush(key, json.dumps(entry, ensure_ascii=False))
            r.ltrim(key, -MAX_HISTORY, -1)
            r.expire(key, 86400 * 7)
            return
        except Exception:
            pass
    _mem_sessions[session_id].append(entry)


def get_history(session_id: str) -> list[dict[str, str]]:
    if _ping_redis():
        try:
            raw = _redis().lrange(f"session:{session_id}", 0, -1)
            return [json.loads(x) for x in raw]
        except Exception:
            pass
    return list(_mem_sessions[session_id])


def format_history_for_escalation(session_id: str) -> str:
    lines = []
    for msg in get_history(session_id):
        who = "Пользователь" if msg["role"] == "user" else "Бот"
        lines.append(f"{who}: {msg['content']}")
    return "\n\n".join(lines)


def clear_session(session_id: str) -> None:
    if _ping_redis():
        try:
            _redis().delete(f"session:{session_id}")
            return
        except Exception:
            pass
    _mem_sessions.pop(session_id, None)
