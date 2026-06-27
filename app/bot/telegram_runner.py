"""Фоновый supervisor: переподключение Telegram после сбоев и рестарта."""
from __future__ import annotations

import asyncio
import logging

from app.config import settings

logger = logging.getLogger(__name__)

_tg_app = None
_stop_event: asyncio.Event | None = None
_supervisor_task: asyncio.Task | None = None


async def _shutdown_app() -> None:
    global _tg_app
    if _tg_app is None:
        return
    try:
        if _tg_app.updater and _tg_app.updater.running:
            await _tg_app.updater.stop()
        await _tg_app.stop()
        await _tg_app.shutdown()
    except Exception as exc:
        logger.debug("Telegram shutdown: %s", exc)
    _tg_app = None


async def _supervisor(stop: asyncio.Event, status: dict[str, object]) -> None:
    global _tg_app
    from app.bot.telegram_bot import build_application

    delay = 10
    max_delay = 120

    while not stop.is_set():
        if not settings.telegram_enabled or not settings.telegram_bot_token.strip():
            status["running"] = False
            status["error"] = "disabled"
            try:
                await asyncio.wait_for(stop.wait(), timeout=60)
            except asyncio.TimeoutError:
                pass
            continue

        try:
            if _tg_app is None:
                _tg_app = build_application()
                await _tg_app.initialize()
                await _tg_app.start()
                if _tg_app.updater:
                    await _tg_app.updater.start_polling(drop_pending_updates=True)
                status["running"] = True
                status["error"] = None
                delay = 10
                logger.info("Telegram bot connected")

            elif _tg_app.updater and not _tg_app.updater.running:
                raise RuntimeError("Telegram polling stopped")

            try:
                await asyncio.wait_for(stop.wait(), timeout=30)
            except asyncio.TimeoutError:
                pass
            continue

        except asyncio.CancelledError:
            raise
        except Exception as exc:
            status["running"] = False
            status["error"] = str(exc)
            logger.warning("Telegram offline, retry in %ss: %s", delay, exc)
            await _shutdown_app()
            try:
                await asyncio.wait_for(stop.wait(), timeout=delay)
                break
            except asyncio.TimeoutError:
                pass
            delay = min(delay * 2, max_delay)


def start_supervisor(status: dict[str, object]) -> asyncio.Task:
    global _stop_event, _supervisor_task
    _stop_event = asyncio.Event()
    _supervisor_task = asyncio.create_task(_supervisor(_stop_event, status))
    return _supervisor_task


async def stop_supervisor() -> None:
    global _stop_event, _supervisor_task
    if _stop_event:
        _stop_event.set()
    if _supervisor_task:
        _supervisor_task.cancel()
        try:
            await _supervisor_task
        except asyncio.CancelledError:
            pass
        _supervisor_task = None
    await _shutdown_app()
    _stop_event = None
