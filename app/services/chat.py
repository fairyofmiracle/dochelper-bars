"""RAG-диалог: поиск → LLM → уверенность → картинки из документации."""
from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass, field

from app.branding import EMPTY_QUESTION_MSG, ESCALATION_MSG, LOW_CONFIDENCE_MSG as _LOW_CONFIDENCE_MSG
from app.config import ESCALATION_WORDS, settings
from app.llm.client import generate_answer
from app.rag.image_store import image_api_url
from app.rag.search import SearchHit, best_confidence, search
from app.rag.vision import analyze_user_image, vision_ready
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
    image_type: str = ""
    image_preview: str = ""


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
        snippets.append(
            SourceSnippet(
                source=h.source,
                excerpt="",
                chunk_index=h.chunk_index,
                score=h.score,
                download_url=_doc_download_url(h.source),
            )
        )
    return snippets[:2]


def _polish_answer(answer: str, *, telegram: bool = False) -> str:
    """Убираем служебные строки. В вебе — также строку «Источник:» (показывает UI)."""
    lines: list[str] = []
    for line in answer.splitlines():
        low = line.strip().lower()
        if low.startswith("источник:") or low.startswith("📎"):
            continue
        if re.match(r"^exported on\b", low):
            continue
        if low in {"содержание", "content"}:
            continue
        cleaned = line.strip()
        cleaned = re.sub(r"\*\*(.+?)\*\*", r"\1", cleaned)
        if not telegram:
            cleaned = re.sub(
                r"^(краткий ответ|коротко|подробности|важно|вот как это устроено)\s*[—\-:]\s*",
                "",
                cleaned,
                flags=re.IGNORECASE,
            )
        if cleaned:
            lines.append(cleaned)
    text = "\n".join(lines).strip()
    return re.sub(r"\n{3,}", "\n\n", text)


def ask(
    question: str,
    force_escalate: bool = False,
    on_phase: Callable[[str], None] | None = None,
    channel: str = "web",
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
        answer = _polish_answer(generate_answer(q, context, channel=channel), telegram=channel == "telegram")
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
    if images:
        suffix = (
            "\n\n🖼 Ниже приложила схему из документации."
            if channel == "telegram"
            else "\n\nЕсли нужно — ниже приложила схему из документации."
        )
        answer += suffix
    record_query(q, True, confidence, sources[0] if sources else "")
    return ChatResult(answer, confidence, sources, False, False, images, snippets, q)


def ask_from_image(image_bytes: bytes, caption: str = "", channel: str = "web") -> ChatResult:
    """Скриншот пользователя → vision → RAG."""
    if not image_bytes:
        return ChatResult(EMPTY_QUESTION_MSG, 0.0, [], False, False)

    if not vision_ready():
        return ChatResult(
            "Распознавание изображений недоступно.\n"
            "Задайте OLLAMA_VISION_MODEL (например qwen2.5vl:3b) и перезапустите сервер,\n"
            "или опишите проблему текстом.",
            0.0,
            [],
            False,
            True,
        )

    analysis = analyze_user_image(image_bytes, caption)
    if not analysis:
        return ChatResult(
            "Не удалось распознать изображение. Опишите вопрос текстом или нажмите «Оператор».",
            0.0,
            [],
            False,
            True,
        )

    user_q = caption.strip() or "Что на скриншоте и как это связано с документацией?"
    search_q = analysis.search_query or user_q
    combined = (
        f"{user_q}\n\n"
        f"[Тип изображения: {analysis.type_label}]\n"
        f"[Распознано на изображении пользователя]\n{analysis.description}"
    )
    result = ask(combined, channel=channel)
    if analysis.search_query and analysis.search_query != user_q:
        alt = ask(search_q, channel=channel)
        if alt.confidence > result.confidence:
            result = alt

    preview = analysis.description if len(analysis.description) <= 300 else analysis.description[:297] + "…"
    result.answer = (
        f"Определено: {analysis.type_label}\n\n"
        f"Распознано на вашем изображении:\n{preview}\n\n---\n\n{result.answer}"
    )
    result.image_type = analysis.image_type
    result.image_preview = preview
    if not result.user_question:
        result.user_question = user_q
    return result
