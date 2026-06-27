"""RAG-диалог: поиск → LLM → уверенность → картинки из документации."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from app.branding import EMPTY_QUESTION_MSG, ESCALATION_MSG, LOW_CONFIDENCE_MSG as _LOW_CONFIDENCE_MSG
from app.config import ESCALATION_WORDS, settings
from app.llm.client import generate_answer
from app.rag.image_store import image_api_url
from app.rag.search import SearchHit, best_confidence, search
from app.rag.vision import describe_user_image, vision_ready
from app.services.analytics import record_query

VISUAL_KEYWORDS = (
    "скрин",
    "картин",
    "изображ",
    "схем",
    "интерфейс",
    "покаж",
    "выгляд",
    "кнопк",
    "screenshot",
    "рисун",
    "иллюстр",
    "окно",
    "форма",
    "меню",
    "экран",
    "вкладк",
    "фильтр",
    "где найти",
    "как выгляд",
)


@dataclass
class SourceSnippet:
    source: str
    excerpt: str
    chunk_index: int
    score: float
    download_url: str


@dataclass
class ChatResult:
    answer: str
    confidence: float
    sources: list[str]
    escalated: bool
    needs_operator: bool
    images: list[str] = field(default_factory=list)
    source_snippets: list[SourceSnippet] = field(default_factory=list)
    user_question: str = ""


LOW_CONFIDENCE_MSG = _LOW_CONFIDENCE_MSG


def is_escalation_request(text: str) -> bool:
    lower = text.lower()
    return any(w in lower for w in ESCALATION_WORDS)


def _wants_visual(question: str) -> bool:
    low = question.lower()
    return any(k in low for k in VISUAL_KEYWORDS)


def _pick_images(hits: list[SearchHit], question: str) -> list[str]:
    want_visual = _wants_visual(question)
    urls: list[str] = []
    seen: set[str] = set()
    for h in hits:
        if not h.image_path:
            continue
        if h.kind != "image" and not want_visual:
            continue
        if h.kind != "image" and h.score < settings.confidence_threshold * 0.9:
            continue
        url = image_api_url(h.image_path)
        if url not in seen:
            seen.add(url)
            urls.append(url)
    return urls[:2]


def _format_context(hits: list[SearchHit]) -> str:
    parts = []
    for i, h in enumerate(hits, 1):
        kind = "иллюстрация" if h.kind == "image" else "текст"
        parts.append(f"[Фрагмент {i} | {h.source} | {kind} | score={h.score:.2f}]\n{h.text}")
    return "\n\n---\n\n".join(parts)


def _doc_download_url(source: str) -> str:
    from urllib.parse import quote

    return f"/api/documents/{quote(source)}"


def _build_snippets(hits: list[SearchHit]) -> list[SourceSnippet]:
    seen: set[str] = set()
    snippets: list[SourceSnippet] = []
    for h in hits:
        if not h.source or h.kind != "text":
            continue
        key = f"{h.source}:{h.chunk_index}"
        if key in seen:
            continue
        seen.add(key)
        excerpt = h.text.strip()
        if len(excerpt) > 320:
            excerpt = excerpt[:317] + "…"
        snippets.append(
            SourceSnippet(
                source=h.source,
                excerpt=excerpt,
                chunk_index=h.chunk_index,
                score=h.score,
                download_url=_doc_download_url(h.source),
            )
        )
    return snippets[:3]


def _ensure_source_line(answer: str, sources: list[str]) -> str:
    lower = answer.lower()
    if "источник:" in lower:
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
        return ChatResult(EMPTY_QUESTION_MSG, 0.0, [], False, False, user_question=q)

    if force_escalate or is_escalation_request(q):
        record_query(q, False, 0.0)
        return ChatResult(ESCALATION_MSG, 0.0, [], True, True, user_question=q)

    if on_phase:
        on_phase("search")
    hits = search(q)
    confidence = best_confidence(hits)
    sources = list(dict.fromkeys(h.source for h in hits if h.source))
    snippets = _build_snippets(hits)
    images = _pick_images(hits, q)

    if confidence < settings.confidence_threshold or not hits:
        record_query(q, False, confidence)
        return ChatResult(
            LOW_CONFIDENCE_MSG, confidence, sources, False, True, images, snippets, q
        )

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
            images,
            snippets,
            q,
        )

    answer = _ensure_source_line(answer, sources)
    if images and "иллюстрац" not in answer.lower():
        answer += "\n\nК иллюстрации из документации — см. вложение ниже."
    record_query(q, True, confidence, sources[0] if sources else "")
    return ChatResult(answer, confidence, sources, False, False, images, snippets, q)


def ask_from_image(image_bytes: bytes, caption: str = "") -> ChatResult:
    """Скриншот пользователя → vision → RAG."""
    if not image_bytes:
        return ChatResult(EMPTY_QUESTION_MSG, 0.0, [], False, False)

    if not vision_ready():
        return ChatResult(
            "Распознавание изображений недоступно.\n"
            "Задайте OLLAMA_VISION_MODEL (например qwen2-vl:7b) и перезапустите сервер,\n"
            "или опишите проблему текстом.",
            0.0,
            [],
            False,
            True,
        )

    desc = describe_user_image(image_bytes)
    if not desc or desc.startswith("["):
        return ChatResult(
            "Не удалось распознать изображение. Опишите вопрос текстом или нажмите «Оператор».",
            0.0,
            [],
            False,
            True,
        )

    user_q = caption.strip() or "Что на скриншоте и как это связано с документацией?"
    combined = f"{user_q}\n\n[Распознано на изображении пользователя]\n{desc}"
    result = ask(combined)
    preview = desc if len(desc) <= 300 else desc[:297] + "…"
    result.answer = f"Распознано на вашем изображении:\n{preview}\n\n---\n\n{result.answer}"
    if not result.user_question:
        result.user_question = user_q
    return result
