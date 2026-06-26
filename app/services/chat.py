"""RAG-диалог: поиск → LLM → уверенность."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from app.config import ESCALATION_WORDS, settings
from app.llm.client import generate_answer
from app.rag.search import SearchHit, best_confidence, search
from app.services.analytics import record_query


@dataclass
class ChatResult:
    answer: str
    confidence: float
    sources: list[str]
    escalated: bool
    needs_operator: bool


LOW_CONFIDENCE_MSG = (
    "Я пока не нашёл точного ответа. Переключить на оператора?"
)


def is_escalation_request(text: str) -> bool:
    lower = text.lower()
    return any(w in lower for w in ESCALATION_WORDS)


def _format_context(hits: list[SearchHit]) -> str:
    parts = []
    for i, h in enumerate(hits, 1):
        parts.append(f"[Фрагмент {i} | {h.source} | score={h.score:.2f}]\n{h.text}")
    return "\n\n---\n\n".join(parts)


def _ensure_source_line(answer: str, sources: list[str]) -> str:
    if "источник:" in answer.lower():
        return answer
    if sources:
        return f"{answer}\n\nИсточник: {sources[0]}"
    return answer


def ask(
    question: str,
    force_escalate: bool = False,
    on_phase: Callable[[str], None] | None = None,
) -> ChatResult:
    q = question.strip()
    if not q:
        return ChatResult("Задайте вопрос по документации.", 0.0, [], False, False)

    if force_escalate or is_escalation_request(q):
        record_query(q, False, 0.0)
        return ChatResult(
            "Передаю диалог оператору. История сохранена.",
            0.0,
            [],
            True,
            True,
        )

    if on_phase:
        on_phase("search")
    hits = search(q)
    confidence = best_confidence(hits)
    sources = list(dict.fromkeys(h.source for h in hits if h.source))

    if confidence < settings.confidence_threshold or not hits:
        record_query(q, False, confidence)
        return ChatResult(LOW_CONFIDENCE_MSG, confidence, sources, False, True)

    context = _format_context(hits)
    try:
        if on_phase:
            on_phase("llm")
        answer = generate_answer(q, context)
    except Exception as exc:
        record_query(q, False, confidence)
        return ChatResult(
            f"Ошибка LLM: {exc}. Попробуйте позже или напишите «оператор».",
            confidence,
            sources,
            False,
            True,
        )

    answer = _ensure_source_line(answer, sources)
    record_query(q, True, confidence, sources[0] if sources else "")
    return ChatResult(answer, confidence, sources, False, False)
