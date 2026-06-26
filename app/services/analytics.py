"""Analytics: Redis or in-memory fallback."""
from __future__ import annotations

import json
import logging
from collections import deque
from datetime import datetime, timezone

from redis import Redis

from app.config import settings

logger = logging.getLogger(__name__)

_mem_total = 0
_mem_auto = 0
_mem_esc = 0
_mem_log: deque = deque(maxlen=500)
_redis_ok: bool | None = None


def _ping_redis() -> bool:
    global _redis_ok
    if _redis_ok is not None:
        return _redis_ok
    try:
        Redis.from_url(settings.redis_url, socket_connect_timeout=2).ping()
        _redis_ok = True
    except Exception as exc:
        logger.warning("Redis unavailable, analytics in-memory: %s", exc)
        _redis_ok = False
    return _redis_ok


def _redis() -> Redis:
    return Redis.from_url(settings.redis_url, decode_responses=True, socket_connect_timeout=2)


def record_query(question: str, auto_answered: bool, confidence: float, source: str = "") -> None:
    global _mem_total, _mem_auto, _mem_esc
    entry = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "question": question[:500],
        "auto": auto_answered,
        "confidence": round(confidence, 3),
        "source": source,
    }

    if _ping_redis():
        try:
            r = _redis()
            r.incr("stats:total")
            r.incr("stats:auto" if auto_answered else "stats:escalated")
            r.lpush("stats:log", json.dumps(entry, ensure_ascii=False))
            r.ltrim("stats:log", 0, 499)
            return
        except Exception:
            pass

    _mem_total += 1
    if auto_answered:
        _mem_auto += 1
    else:
        _mem_esc += 1
    _mem_log.appendleft(entry)


def get_stats() -> dict:
    if _ping_redis():
        try:
            r = _redis()
            total = int(r.get("stats:total") or 0)
            auto = int(r.get("stats:auto") or 0)
            esc = int(r.get("stats:escalated") or 0)
            recent = [json.loads(x) for x in r.lrange("stats:log", 0, 49)]
            return {
                "total_queries": total,
                "auto_answered": auto,
                "escalated": esc,
                "auto_rate_percent": round(auto / total * 100, 1) if total else 0.0,
                "recent": recent,
                "storage": "redis",
            }
        except Exception:
            pass

    rate = round(_mem_auto / _mem_total * 100, 1) if _mem_total else 0.0
    return {
        "total_queries": _mem_total,
        "auto_answered": _mem_auto,
        "escalated": _mem_esc,
        "auto_rate_percent": rate,
        "recent": list(_mem_log)[:50],
        "storage": "memory",
    }
