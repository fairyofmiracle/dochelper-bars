"""Analytics: Redis or in-memory fallback."""
from __future__ import annotations

import json
import logging
import re
from collections import Counter, defaultdict, deque
from datetime import datetime, timezone

from redis import Redis

from app.config import settings

logger = logging.getLogger(__name__)

_mem_total = 0
_mem_auto = 0
_mem_esc = 0
_mem_rate_limited = 0
_mem_log: deque = deque(maxlen=500)
_redis_ok: bool | None = None

_SKIP_QUESTIONS = {"/operator", "оператор", "задать вопрос", "отмена", "переключить на оператора"}


def _normalize_question(text: str) -> str:
    q = re.sub(r"\s+", " ", text.strip().lower())
    if q in _SKIP_QUESTIONS or q.startswith("/"):
        return ""
    return q[:200]


def _parse_ts(ts: str) -> datetime | None:
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except ValueError:
        return None


def _gap_recommendation(avg_conf: float, count: int) -> str:
    if avg_conf < 0.2:
        return "Тема, вероятно, отсутствует в документации — добавить раздел или FAQ"
    if count >= 3:
        return "Повторяющийся вопрос без уверенного ответа — расширить документ"
    return "Проверить релевантность чанков и формулировку в базе"


def _weak_spots(recent: list[dict]) -> list[dict]:
    failed: Counter[str] = Counter()
    conf_sum: dict[str, float] = defaultdict(float)
    conf_cnt: dict[str, int] = defaultdict(int)

    for row in recent:
        if row.get("kind") == "rate_limit":
            continue
        q = _normalize_question(row.get("question", ""))
        if not q:
            continue
        auto = bool(row.get("auto", False))
        conf = float(row.get("confidence", 0))
        src = str(row.get("source", "")).strip()
        if auto and conf >= 0.45 and src:
            continue
        failed[q] += 1
        conf_sum[q] += conf
        conf_cnt[q] += 1

    spots: list[dict] = []
    for q, c in failed.most_common(10):
        avg = conf_sum[q] / conf_cnt[q] if conf_cnt[q] else 0.0
        spots.append(
            {
                "question": q,
                "count": c,
                "avg_confidence": round(avg, 3),
                "recommendation": _gap_recommendation(avg, c),
            }
        )
    return spots


def _trends(recent: list[dict]) -> dict:
    daily_total: Counter[str] = Counter()
    daily_auto: Counter[str] = Counter()
    hourly: Counter[str] = Counter()
    now = datetime.now(timezone.utc)

    first_half: Counter[str] = Counter()
    second_half: Counter[str] = Counter()
    mid = len(recent) // 2

    for i, row in enumerate(recent):
        if row.get("kind") == "rate_limit":
            continue
        dt = _parse_ts(str(row.get("ts", "")))
        if not dt:
            continue
        day = dt.strftime("%Y-%m-%d")
        daily_total[day] += 1
        if row.get("auto"):
            daily_auto[day] += 1
        if (now - dt).total_seconds() <= 86400:
            hourly[dt.strftime("%H:00")] += 1

        q = _normalize_question(row.get("question", ""))
        if q:
            if i < mid:
                first_half[q] += 1
            else:
                second_half[q] += 1

    days = sorted(daily_total.keys())[-14:]
    daily = [
        {"date": d, "total": daily_total[d], "auto": daily_auto[d]}
        for d in days
    ]

    rising: list[dict] = []
    for q, cnt2 in second_half.most_common(20):
        cnt1 = first_half.get(q, 0)
        if cnt2 >= 2 and cnt2 > cnt1:
            rising.append({"question": q, "recent_count": cnt2, "earlier_count": cnt1})
    rising.sort(key=lambda x: (-x["recent_count"], x["earlier_count"]))
    rising = rising[:8]

    hour_labels = sorted(hourly.keys())
    hourly_list = [{"hour": h, "count": hourly[h]} for h in hour_labels[-24:]]

    return {
        "daily": daily,
        "hourly_last_24h": hourly_list,
        "rising_topics": rising,
    }


def _aggregate(recent: list[dict]) -> dict:
    q_counter: Counter[str] = Counter()
    src_counter: Counter[str] = Counter()
    buckets = {"high": 0, "medium": 0, "low": 0}

    for row in recent:
        if row.get("kind") == "rate_limit":
            continue
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
        "weak_spots": _weak_spots(recent),
        "doc_gaps": _weak_spots(recent)[:5],
        "trends": _trends(recent),
    }


def _build_stats(
    total: int,
    auto: int,
    esc: int,
    rate_limited: int,
    recent: list[dict],
    storage: str,
) -> dict:
    agg = _aggregate(recent)
    return {
        "total_queries": total,
        "auto_answered": auto,
        "escalated": esc,
        "rate_limited": rate_limited,
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


def _push_entry(entry: dict) -> None:
    global _mem_total, _mem_auto, _mem_esc, _mem_rate_limited

    if _ping_redis():
        try:
            r = _redis()
            kind = entry.get("kind", "query")
            if kind == "rate_limit":
                r.incr("stats:rate_limited")
            else:
                r.incr("stats:total")
                r.incr("stats:auto" if entry.get("auto") else "stats:escalated")
            r.lpush("stats:log", json.dumps(entry, ensure_ascii=False))
            r.ltrim("stats:log", 0, 499)
            return
        except Exception:
            pass

    if entry.get("kind") == "rate_limit":
        _mem_rate_limited += 1
    else:
        _mem_total += 1
        if entry.get("auto"):
            _mem_auto += 1
        else:
            _mem_esc += 1
    _mem_log.appendleft(entry)


def record_query(question: str, auto_answered: bool, confidence: float, source: str = "") -> None:
    entry = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "question": question[:500],
        "auto": auto_answered,
        "confidence": round(confidence, 3),
        "source": source,
        "kind": "query",
    }
    _push_entry(entry)


def record_rate_limit(client_id: str, message: str) -> None:
    entry = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "question": message[:500],
        "auto": False,
        "confidence": 0.0,
        "source": "",
        "kind": "rate_limit",
        "client_id": client_id[:64],
    }
    _push_entry(entry)


def get_stats() -> dict:
    if _ping_redis():
        try:
            r = _redis()
            total = int(r.get("stats:total") or 0)
            auto = int(r.get("stats:auto") or 0)
            esc = int(r.get("stats:escalated") or 0)
            rate_limited = int(r.get("stats:rate_limited") or 0)
            recent = [json.loads(x) for x in r.lrange("stats:log", 0, 499)]
            return _build_stats(total, auto, esc, rate_limited, recent, "redis")
        except Exception:
            pass

    recent = list(_mem_log)[:500]
    return _build_stats(_mem_total, _mem_auto, _mem_esc, _mem_rate_limited, recent, "memory")
