"""Синхронизация базы знаний: Git webhook / Confluence (демо + reindex)."""
from __future__ import annotations

import json
import logging
import time
from dataclasses import asdict, dataclass

from redis import Redis

from app.config import settings
from app.rag.indexer import index_all

logger = logging.getLogger(__name__)

SYNC_KEY = "docsync:last"
_redis_ok: bool | None = None
_mem_sync: dict | None = None


@dataclass
class SyncResult:
    source: str
    ok: bool
    ts: float
    files: int = 0
    chunks: int = 0
    message: str = ""
    trigger: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


def _ping_redis() -> bool:
    global _redis_ok
    if _redis_ok is not None:
        return _redis_ok
    try:
        Redis.from_url(settings.redis_url, socket_connect_timeout=2).ping()
        _redis_ok = True
    except Exception as exc:
        logger.warning("Redis unavailable for doc_sync: %s", exc)
        _redis_ok = False
    return _redis_ok


def _save_sync(result: SyncResult) -> None:
    global _mem_sync
    data = result.to_dict()
    _mem_sync = data
    if _ping_redis():
        try:
            Redis.from_url(settings.redis_url, decode_responses=True).set(
                SYNC_KEY,
                json.dumps(data, ensure_ascii=False),
            )
        except Exception:
            pass


def get_last_sync() -> dict | None:
    if _ping_redis():
        try:
            raw = Redis.from_url(settings.redis_url, decode_responses=True).get(SYNC_KEY)
            if raw:
                return json.loads(raw)
        except Exception:
            pass
    return _mem_sync


def run_reindex(source: str, trigger: str = "manual", clear: bool = False) -> SyncResult:
    """Переиндексация после Git push / Confluence / ручной кнопки."""
    try:
        stats = index_all(clear=clear)
        result = SyncResult(
            source=source,
            ok=True,
            ts=time.time(),
            files=stats.files,
            chunks=stats.chunks,
            message=f"Проиндексировано {stats.files} файлов, {stats.chunks} фрагментов",
            trigger=trigger,
        )
    except Exception as exc:
        logger.exception("doc sync failed")
        result = SyncResult(
            source=source,
            ok=False,
            ts=time.time(),
            message=str(exc),
            trigger=trigger,
        )
    _save_sync(result)
    return result


def handle_git_webhook(payload: dict | None = None) -> SyncResult:
    ref = (payload or {}).get("ref", "refs/heads/main")
    commits = len((payload or {}).get("commits") or [])
    trigger = f"git push {ref}" + (f" ({commits} commits)" if commits else "")
    clear = settings.sync_reindex_clear
    return run_reindex("git", trigger=trigger, clear=clear)


def handle_confluence_webhook(payload: dict | None = None) -> SyncResult:
    page = (payload or {}).get("page_title") or (payload or {}).get("title") or "Confluence"
    trigger = f"confluence update: {page}"
    return run_reindex("confluence", trigger=trigger, clear=False)
