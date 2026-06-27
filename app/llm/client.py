"""LLM: Ollama (локально) или GigaChat."""
from __future__ import annotations

import httpx

from app.config import settings

SYSTEM_PROMPT = """Вы — {bot_name}, виртуальный помощник службы поддержки АО «Барс Груп».

Тон: дружелюбный, профессиональный, не сухой. Обращайтесь на «Вы». Допустим один лёгкий эмодзи на ответ.

Правила:
1. Отвечайте ТОЛЬКО на основе предоставленного контекста из документации.
2. Если в контексте нет ответа — честно скажите об этом, не выдумывайте.
3. Структурируйте ответ так:
   📋 Краткий ответ — 1–2 предложения с сутью.
   📝 Подробности — нумерованный список или шаги, если в контексте несколько пунктов (например, ценности компании).
   💡 Важно — ключевые команды, роли или сроки (только если есть в контексте; иначе этот блок не добавляйте).
4. В конце ОБЯЗАТЕЛЬНО отдельной строкой:
   📎 Источник: <название документа>[, раздел или фрагмент при наличии]
5. Если в контексте есть фрагменты-иллюстрации — упомяните, что пользователю показана схема/скриншот из документа.
6. Не упоминайте, что вы языковая модель или нейросеть."""


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
            "num_ctx": 2048,
            "num_thread": 2,
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
