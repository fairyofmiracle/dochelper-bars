"""Эскалация в Telegram-чат поддержки."""
from __future__ import annotations

import httpx

from app.config import settings
from app.services.session import format_history_for_escalation


async def notify_support(session_id: str, user_label: str, last_message: str = "") -> bool:
    chat_id = settings.telegram_support_chat_id.strip()
    token = settings.telegram_bot_token.strip()
    if not chat_id or not token:
        return False

    history = format_history_for_escalation(session_id)
    text = (
        f"🆘 Эскалация от {user_label}\n"
        f"Session: {session_id}\n\n"
        f"{history}"
    )
    if last_message:
        text += f"\n\nПоследнее сообщение: {last_message}"

    if len(text) > 4000:
        text = text[:3990] + "…"

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.post(url, json={"chat_id": chat_id, "text": text})
        return r.status_code == 200
