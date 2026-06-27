"""LLM: Ollama (локально) или GigaChat."""
from __future__ import annotations

import base64
import binascii

import httpx

from app.config import settings

SYSTEM_PROMPT = """Вы — {bot_name}, дружелюбный помощник по документации Барс Груп. Общайтесь как живой коллега в корпоративном чате: тепло, просто, на «Вы», без канцелярита.

Правила:
1. Отвечайте ТОЛЬКО по контексту из документации — не выдумывайте.
2. Сразу дайте суть: 2–4 коротких абзаца или понятный список шагов.
3. Пересказывайте своими словами — как объяснили бы новичку за соседним столом. Не копируйте абзацы из документа, оглавление, «Exported on», «Содержание».
4. Можно начать с короткой фразы вроде «Коротко:» или «Вот как это устроено:» — но без заголовков «Краткий ответ», без emoji и без строки «Источник:» (источник покажет интерфейс).
5. Если есть роли, статусы, шаги — назовите их явно и по-человечески.
6. Не упоминайте, что вы нейросеть или языковая модель."""


def build_system_prompt() -> str:
    return SYSTEM_PROMPT.format(bot_name=settings.bot_name)


def _gigachat_credentials() -> str:
    """GigaChat API: Authorization key = base64(client_id:client_secret)."""
    if settings.gigachat_client_id.strip() and settings.gigachat_client_secret.strip():
        pair = f"{settings.gigachat_client_id.strip()}:{settings.gigachat_client_secret.strip()}"
        return base64.b64encode(pair.encode()).decode()

    raw = settings.gigachat_credentials.strip()
    if not raw:
        return raw
    try:
        base64.b64decode(raw, validate=True)
        return raw
    except (ValueError, binascii.Error):
        pass
    if ":" not in raw and "." in raw:
        client_id, client_secret = raw.split(".", 1)
        raw = f"{client_id}:{client_secret}"
    return base64.b64encode(raw.encode()).decode()


def generate_answer(question: str, context: str) -> str:
    user = f"""Контекст из документации:
---
{context}
---

Вопрос пользователя: {question}

Ответьте по контексту живым языком — перескажите, не цитируйте документ дословно."""

    if settings.llm_provider == "gigachat" and (
        settings.gigachat_credentials.strip()
        or (settings.gigachat_client_id.strip() and settings.gigachat_client_secret.strip())
    ):
        return _gigachat(build_system_prompt(), user)
    return _ollama(build_system_prompt(), user)


def _ollama(system: str, user: str) -> str:
    from app.llm.ollama_http import ollama_post

    url = f"{settings.ollama_base_url.rstrip('/')}/api/chat"
    payload = {
        "model": settings.ollama_model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "stream": False,
        "options": {
            "temperature": 0.35,
            "num_predict": 450,
            "num_ctx": 2048,
            "num_thread": 2,
        },
    }
    r = ollama_post(url, json=payload, timeout=180.0)
    r.raise_for_status()
    return r.json()["message"]["content"].strip()


def _gigachat(system: str, user: str) -> str:
    from gigachat import GigaChat
    from gigachat.models import Chat, Messages, MessagesRole

    payload = Chat(
        messages=[
            Messages(role=MessagesRole.SYSTEM, content=system),
            Messages(role=MessagesRole.USER, content=user),
        ],
        temperature=0.35,
        max_tokens=450,
    )
    with GigaChat(
        credentials=_gigachat_credentials(),
        scope=settings.gigachat_scope,
        model=settings.gigachat_model,
        verify_ssl_certs=False,
    ) as client:
        resp = client.chat(payload)
    return (resp.choices[0].message.content or "").strip()
