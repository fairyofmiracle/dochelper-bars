"""Analytics: Redis or in-memory fallback."""
from __future__ import annotations

import json
import logging
import re
from collections import Counter, deque
from datetime import datetime, timezone

from redis import Redis

from app.config import settings

logger = logging.getLogger(__name__)

_mem_total = 0
_mem_auto = 0
_mem_esc = 0
_mem_log: deque = deque(maxlen=500)
_redis_ok: bool | None = None

_SKIP_QUESTIONS = {"/operator", "оператор", "задать вопрос", "отмена", "переключить на оператора"}


def _normalize_question(text: str) -> str:
    q = re.sub(r"\s+", " ", text.strip().lower())
    if q in _SKIP_QUESTIONS or q.startswith("/"):
        return ""
    return q[:200]


def _aggregate(recent: list[dict]) -> dict:
    q_counter: Counter[str] = Counter()
    src_counter: Counter[str] = Counter()
    buckets = {"high": 0, "medium": 0, "low": 0}

    for row in recent:
        q = _normalize_question(row.get("question", ""))
        if q:
            q_counter[q] += 1
        src = str(row.get("source", "")).strip()
        if src:
            src_counter[src] += 1
        conf = float(row.get("confidence", 0))
        if conf >= 0.7:
            buckets["high"] += 1
        elif conf >= 0.45:
            buckets["medium"] += 1
        else:
            buckets["low"] += 1

    return {
        "top_questions": [
            {"question": q, "count": c} for q, c in q_counter.most_common(10)
        ],
        "top_sources": [
            {"source": s, "count": c} for s, c in src_counter.most_common(8)
        ],
        "confidence_buckets": buckets,
    }


def _build_stats(total: int, auto: int, esc: int, recent: list[dict], storage: str) -> dict:
    agg = _aggregate(recent)
    return {
        "total_queries": total,
        "auto_answered": auto,
        "escalated": esc,
        "auto_rate_percent": round(auto / total * 100, 1) if total else 0.0,
        "recent": recent,
        "storage": storage,
        **agg,
    }


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
            recent = [json.loads(x) for x in r.lrange("stats:log", 0, 499)]
            return _build_stats(total, auto, esc, recent, "redis")
        except Exception:
            pass

    rate = round(_mem_auto / _mem_total * 100, 1) if _mem_total else 0.0
    recent = list(_mem_log)[:500]
    return _build_stats(_mem_total, _mem_auto, _mem_esc, recent, "memory")
