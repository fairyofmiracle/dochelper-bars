"""Антиспам и лимиты запросов (Redis + in-memory fallback)."""
from __future__ import annotations

import hashlib
import logging
import re
import time
from collections import defaultdict, deque
from dataclasses import dataclass

from redis import Redis

from app.config import settings

logger = logging.getLogger(__name__)

_mem_counts: dict[str, deque[float]] = defaultdict(lambda: deque(maxlen=64))
_mem_dup: dict[str, deque[float]] = defaultdict(lambda: deque(maxlen=32))
_mem_blocked_until: dict[str, float] = {}
_redis_ok: bool | None = None


@dataclass
class RateLimitResult:
    allowed: bool
    reason: str = ""
    retry_after_sec: int = 0


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower())[:200]


def _ping_redis() -> bool:
    global _redis_ok
    if _redis_ok is not None:
        return _redis_ok
    try:
        Redis.from_url(settings.redis_url, socket_connect_timeout=2).ping()
        _redis_ok = True
    except Exception as exc:
        logger.warning("Redis unavailable for rate limit: %s", exc)
        _redis_ok = False
    return _redis_ok


def _redis() -> Redis:
    return Redis.from_url(settings.redis_url, decode_responses=True, socket_connect_timeout=2)


def _check_memory(client_id: str, message: str, now: float) -> RateLimitResult:
    blocked = _mem_blocked_until.get(client_id, 0)
    if blocked > now:
        return RateLimitResult(
            False,
            "Временная блокировка за частые сообщения.",
            max(1, int(blocked - now)),
        )

    window = settings.rate_limit_window_sec
    counts = _mem_counts[client_id]
    while counts and counts[0] < now - window:
        counts.popleft()
    if len(counts) >= settings.rate_limit_max_per_window:
        _mem_blocked_until[client_id] = now + settings.rate_limit_block_sec
        return RateLimitResult(
            False,
            f"Слишком много сообщений — подождите {settings.rate_limit_block_sec} сек.",
            settings.rate_limit_block_sec,
        )

    norm = _normalize(message)
    if norm:
        dup_key = f"{client_id}:{hashlib.md5(norm.encode()).hexdigest()[:12]}"
        dup = _mem_dup[dup_key]
        dup_window = settings.rate_limit_duplicate_window_sec
        while dup and dup[0] < now - dup_window:
            dup.popleft()
        dup.append(now)
        if len(dup) >= settings.rate_limit_duplicate_max:
            _mem_blocked_until[client_id] = now + settings.rate_limit_block_sec
            return RateLimitResult(
                False,
                "Повторяющиеся сообщения похожи на спам — пауза перед следующим вопросом.",
                settings.rate_limit_block_sec,
            )

    counts.append(now)
    return RateLimitResult(True)


def _check_redis(client_id: str, message: str, now: int) -> RateLimitResult | None:
    try:
        r = _redis()
        block_key = f"rl:block:{client_id}"
        ttl = r.ttl(block_key)
        if ttl and ttl > 0:
            return RateLimitResult(False, "Временная блокировка за частые сообщения.", ttl)

        count_key = f"rl:count:{client_id}"
        count = r.incr(count_key)
        if count == 1:
            r.expire(count_key, settings.rate_limit_window_sec)
        if count > settings.rate_limit_max_per_window:
            r.setex(block_key, settings.rate_limit_block_sec, "1")
            return RateLimitResult(
                False,
                f"Слишком много сообщений — подождите {settings.rate_limit_block_sec} сек.",
                settings.rate_limit_block_sec,
            )

        norm = _normalize(message)
        if norm:
            dup_key = f"rl:dup:{client_id}:{hashlib.md5(norm.encode()).hexdigest()[:12]}"
            dup = r.incr(dup_key)
            if dup == 1:
                r.expire(dup_key, settings.rate_limit_duplicate_window_sec)
            if dup >= settings.rate_limit_duplicate_max:
                r.setex(block_key, settings.rate_limit_block_sec, "1")
                return RateLimitResult(
                    False,
                    "Повторяющиеся сообщения — пауза перед следующим вопросом.",
                    settings.rate_limit_block_sec,
                )
        return RateLimitResult(True)
    except Exception as exc:
        logger.debug("rate limit redis failed: %s", exc)
        return None


def check_rate_limit(client_id: str, message: str) -> RateLimitResult:
    if not settings.rate_limit_enabled:
        return RateLimitResult(True)

    text = (message or "").strip()
    if not text or text.startswith("/"):
        return RateLimitResult(True)

    now_f = time.time()
    if _ping_redis():
        redis_result = _check_redis(client_id, text, int(now_f))
        if redis_result is not None:
            return redis_result

    return _check_memory(client_id, text, now_f)


def rate_limit_message(result: RateLimitResult) -> str:
    if result.retry_after_sec:
        return (
            f"{result.reason}\n\n"
            f"Попробуйте снова через ~{result.retry_after_sec} сек. "
            f"Если срочно — напишите «оператор»."
        )
    return result.reason or "Слишком много запросов. Попробуйте позже."
