"""LLM: Ollama (локально) или GigaChat."""
from __future__ import annotations

import httpx

from app.config import settings

SYSTEM_PROMPT = """Вы — {bot_name}, виртуальный помощник службы поддержки компании Барс Груп.
Отвечайте на «Вы», дружелюбно и профессионально. Допустимы лёгкие эмодзи (не больше одного на ответ).

Правила:
1. Отвечайте ТОЛЬКО на основе предоставленного контекста из документации.
2. Если в контексте нет ответа — честно скажите об этом, не выдумывайте.
3. Структурируйте ответ: краткий вывод, затем нумерованные шаги при необходимости.
4. В конце ОБЯЗАТЕЛЬНО укажите строку: Источник: <название документа>
5. Не упоминайте, что вы языковая модель."""


def build_system_prompt() -> str:
    return SYSTEM_PROMPT.format(bot_name=settings.bot_name)


def generate_answer(question: str, context: str) -> str:
    user = f"""Контекст из документации:
---
{context}
---

Вопрос пользователя: {question}

Дайте точный ответ по контексту."""

    if settings.llm_provider == "gigachat" and settings.gigachat_credentials:
        return _gigachat(build_system_prompt(), user)
    return _ollama(build_system_prompt(), user)


def _ollama(system: str, user: str) -> str:
    url = f"{settings.ollama_base_url.rstrip('/')}/api/chat"
    payload = {
        "model": settings.ollama_model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "stream": False,
        "options": {
            "temperature": 0.2,
            "num_predict": 350,
            "num_ctx": 4096,
        },
    }
    with httpx.Client(timeout=180.0) as client:
        r = client.post(url, json=payload)
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
        temperature=0.2,
        max_tokens=400,
    )
    with GigaChat(
        credentials=settings.gigachat_credentials,
        scope=settings.gigachat_scope,
        model=settings.gigachat_model,
        verify_ssl_certs=False,
    ) as client:
        resp = client.chat(payload)
    return (resp.choices[0].message.content or "").strip()
