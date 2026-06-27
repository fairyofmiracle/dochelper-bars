"""RAG-диалог: поиск → LLM → уверенность → картинки из документации."""
from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from app.branding import EMPTY_QUESTION_MSG, ESCALATION_MSG, LOW_CONFIDENCE_MSG as _LOW_CONFIDENCE_MSG
from app.config import ESCALATION_WORDS, settings
from app.llm.client import generate_answer
from app.rag.docx_sections import values_image_names
from app.rag.image_store import image_api_url
from app.rag.search import SearchHit, best_confidence, find_doc_images, search, search_images
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
    "ценност",
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


def _pick_images(hits: list[SearchHit], question: str, text_hits: list[SearchHit]) -> list[str]:
    """Картинки из docx: приоритет — найденные иллюстрации из того же документа."""
    want_visual = _wants_visual(question)
    urls: list[str] = []
    seen: set[str] = set()

    primary_source = text_hits[0].source if text_hits else ""

    for h in sorted(hits, key=lambda x: -x.score):
        if not h.image_path:
            continue
        if h.kind == "image":
            pass
        elif not want_visual:
            continue
        elif primary_source and h.source != primary_source:
            continue
        elif h.score < settings.confidence_threshold * 0.85:
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


def _build_snippets(hits: list[SearchHit], question: str = "") -> list[SourceSnippet]:
    seen: set[str] = set()
    snippets: list[SourceSnippet] = []
    terms = [w for w in re.findall(r"[\w\u0400-\u04FF]+", question.lower()) if len(w) >= 5]
    for h in hits:
        if not h.source or h.kind != "text":
            continue
        key = f"{h.source}:{h.chunk_index}"
        if key in seen:
            continue
        seen.add(key)
        excerpt = _snippet_excerpt(h.text.strip(), terms)
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


def _snippet_excerpt(text: str, terms: list[str], max_len: int = 320) -> str:
    if len(text) <= max_len:
        return text
    low = text.lower()
    pos = -1
    for term in terms:
        idx = low.find(term)
        if idx >= 0:
            pos = idx
            break
    if pos < 0:
        for marker in ("ценност", "бизнес-процесс", "фильтр", "командиров"):
            idx = low.find(marker)
            if idx >= 0:
                pos = idx
                break
    if pos < 0:
        return text[: max_len - 1] + "…"
    start = max(0, pos - 50)
    piece = text[start : start + max_len].strip()
    if start > 0:
        piece = "…" + piece
    if start + max_len < len(text):
        piece = piece.rstrip() + "…"
    return piece


def _answer_body_without_source(answer: str) -> str:
    lines: list[str] = []
    for line in answer.splitlines():
        stripped = line.strip()
        if not stripped or stripped == "---":
            continue
        low = stripped.lower()
        if low.startswith("источник:") or ("источник" in low and stripped.startswith("📎")):
            continue
        lines.append(stripped)
    return "\n".join(lines)


def _is_insufficient_answer(answer: str) -> bool:
    body = _answer_body_without_source(answer)
    if len(body) < 35:
        return True
    low = body.lower()
    negative = (
        "нет информации",
        "нет данных",
        "не нашёл",
        "не нашел",
        "не найден",
        "нет в контексте",
        "нет ответа",
        "не могу ответить",
        "отсутствует в",
        "отсутствует информация",
        "не содержит",
        "нет раздела",
        "не указан",
        "не указаны",
        "не приведен",
        "не приведены",
        "в представленном контексте",
        "в данном фрагменте",
        "в контексте нет",
    )
    return any(p in low for p in negative)


def _hits_match_question(question: str, hits: list[SearchHit]) -> bool:
    terms = [w for w in re.findall(r"[\w\u0400-\u04FF]+", question.lower()) if len(w) >= 5]
    if not terms:
        return True
    blob = " ".join(h.text.lower() for h in hits if h.kind == "text")
    return any(t in blob for t in terms)


def _attach_values_images(hits: list[SearchHit], image_hits: list[SearchHit], question: str) -> list[str]:
    if "ценност" not in question.lower():
        return []
    if not any("ценност" in h.text.lower() for h in hits):
        return []
    source = next((h.source for h in hits if h.source), "")
    names = values_image_names(source)
    if not names:
        return []
    by_name = {Path(h.image_path).name: h for h in image_hits if h.image_path}
    urls: list[str] = []
    for name in names[:3]:
        hit = by_name.get(name)
        if hit and hit.image_path:
            urls.append(image_api_url(hit.image_path))
    if urls:
        return urls
    extra = find_doc_images(source, names[:3])
    for h in extra:
        if h.image_path:
            urls.append(image_api_url(h.image_path))
    return urls[:3]


def _strip_source_lines(answer: str) -> str:
    lines: list[str] = []
    for line in answer.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        low = stripped.lower()
        if low.startswith("источник:") or ("источник" in low and stripped.startswith("📎")):
            continue
        lines.append(line)
    return "\n".join(lines).rstrip()


def _ensure_source_line(answer: str, source: str) -> str:
    """Источник всегда из RAG-поиска, не из фантазии LLM."""
    if not source:
        return answer
    body = _strip_source_lines(answer)
    if body:
        return f"{body}\n\n📎 Источник: {source}"
    return f"📎 Источник: {source}"


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
    sources = list(dict.fromkeys(h.source for h in hits if h.source))
    img_k = 40 if "ценност" in q.lower() else 2
    image_hits = search_images(q, prefer_sources=sources, top_k=img_k, min_score=0.55)
    confidence = best_confidence(hits + image_hits)
    if not _hits_match_question(q, hits):
        confidence = min(confidence, settings.confidence_threshold - 0.05)
    snippets = _build_snippets(hits, q)
    images = _pick_images(image_hits + hits, q, hits)
    images = list(dict.fromkeys(images + _attach_values_images(hits, image_hits, q)))

    if confidence < settings.confidence_threshold or not hits:
        record_query(q, False, confidence)
        return ChatResult(
            LOW_CONFIDENCE_MSG, confidence, sources, False, True, images, snippets, q
        )

    context = _format_context(hits + image_hits)
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

    if _is_insufficient_answer(answer):
        record_query(q, False, min(confidence, settings.confidence_threshold - 0.01))
        return ChatResult(
            LOW_CONFIDENCE_MSG,
            min(confidence, settings.confidence_threshold - 0.01),
            sources,
            False,
            True,
            images,
            snippets,
            q,
        )

    answer = _ensure_source_line(answer, sources[0] if sources else "")
    if images:
        if "иллюстрац" not in answer.lower() and "скрин" not in answer.lower():
            answer += "\n\n📷 К ответу приложена иллюстрация из документации."
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
