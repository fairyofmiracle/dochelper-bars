"""Async-обёртка над sync RAG (LLM/embeddings блокируют поток)."""
from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable

from app.services.chat import ChatResult, ask, ask_from_image

PhaseCallback = Callable[[str], Awaitable[None] | None]


async def ask_async(
    question: str,
    force_escalate: bool = False,
    on_phase: PhaseCallback | None = None,
) -> ChatResult:
    loop = asyncio.get_running_loop()

    def sync_on_phase(phase: str) -> None:
        if not on_phase:
            return
        result = on_phase(phase)
        if asyncio.iscoroutine(result):
            asyncio.run_coroutine_threadsafe(result, loop)

    return await asyncio.to_thread(ask, question, force_escalate, sync_on_phase)


async def ask_from_image_async(image_bytes: bytes, caption: str = "") -> ChatResult:
    return await asyncio.to_thread(ask_from_image, image_bytes, caption)
