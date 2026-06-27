"""Текст из разделов docx, где содержимое хранится в иллюстрациях."""
from __future__ import annotations

from pathlib import Path

from docx import Document
from docx.text.paragraph import Paragraph

from app.rag.parser import _iter_block_items
from app.rag.vision import describe_image

# OCR-текст слайдов «Ценности компании» (newbiePage.docx, image8–image17)
_NEWBIE_VALUES: dict[str, str] = {
    "image8.png": (
        "Мы всегда достигаем результата. "
        "В «БАРС Груп» принято ставить амбициозные цели и достигать их быстро и точно. "
        "Скорость — важный навык, а точность ещё важнее. "
        "Мы несём ответственность за результат нашей работы, и если что-то пойдёт не так — обязательно исправим."
    ),
    "image9.png": (
        "Мы работаем в команде. "
        "Команда — главный актив «БАРС Груп». "
        "Наша сила — в команде; командная работа продуктивнее, чем в одиночку. "
        "Мы видим и ценим вклад каждого и уважаем, поддерживаем друг друга."
    ),
    "image10.png": (
        "Мы правильно расставляем приоритеты. "
        "Умеем отделять главное от срочного. "
        "Выполнение нужных задач к нужному сроку — гарантия нашей успешности."
    ),
    "image11.png": (
        "Мы постоянно развиваемся. "
        "Мир динамичен — совершенствуем навыки, технологии и процессы. "
        "С благодарностью принимаем обратную связь от клиентов и коллег."
    ),
    "image12.png": (
        "Мы делимся знаниями. "
        "Коллективный разум сильнее самого умного индивида. "
        "Принято делиться знаниями и идеями, помогать коллегам развиваться."
    ),
    "image13.png": (
        "Мы выполняем обещания. "
        "Не даём пустых обещаний — то, что пообещали, всегда выполняем. "
        "Слово, которое мы дали, — для нас закон."
    ),
    "image14.png": (
        "Мы творчески решаем задачи. "
        "Принято мыслить нестандартно и креативно, предлагать новые идеи и подходы, "
        "раздвигая границы возможного."
    ),
    "image15.png": (
        "Мы уважаем интересы наших клиентов и партнёров. "
        "С уважением выстраиваем сотрудничество и при этом защищаем интересы компании."
    ),
    "image16.png": (
        "Мы живём и работаем в России. "
        "Строго соблюдаем российские законы, чтим традиции и работаем на благо людей вокруг нас."
    ),
    "image17.png": (
        "Мы любим то, что делаем, и делаем то, что любим. "
        "Работа в «БАРС Груп» — значимая часть жизни, место созидания, силы, признания и взаимоуважения. "
        "Помогаем друг другу развиваться; совместные результаты меняют жизни людей к лучшему."
    ),
}

_SECTION_IMAGE_TEXT: dict[tuple[str, str], str] = {
    (source, img): text for source in ("newbiePage.docx",) for img, text in _NEWBIE_VALUES.items()
}


def _image_text(source: str, image_name: str, image_bytes: bytes, heading: str) -> str:
    cached = _SECTION_IMAGE_TEXT.get((source, image_name))
    if cached:
        return cached
    return describe_image(image_bytes, source, image_name)


def _images_by_name(path: Path) -> dict[str, bytes]:
    import zipfile

    out: dict[str, bytes] = {}
    try:
        with zipfile.ZipFile(path) as zf:
            for name in zf.namelist():
                if name.startswith("word/media/") and not name.endswith("/"):
                    data = zf.read(name)
                    if len(data) > 500:
                        out[Path(name).name] = data
    except zipfile.BadZipFile:
        pass
    return out


def _section_image_names(path: Path) -> list[tuple[str, list[str]]]:
    """Заголовок абзаца → картинки в этом и следующих абзацах до нового заголовка."""
    doc = Document(path)
    by_heading: dict[str, list[str]] = {}
    current = ""

    for block in _iter_block_items(doc):
        if not isinstance(block, Paragraph):
            continue
        text = block.text.strip()
        if text:
            current = text
            by_heading.setdefault(current, [])
        if not current:
            continue
        for run in block.runs:
            for blip in run._element.iter(
                "{http://schemas.openxmlformats.org/drawingml/2006/main}blip"
            ):
                embed = blip.get(
                    "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}embed"
                )
                if embed:
                    rel = doc.part.rels[embed]
                    name = Path(rel.target_ref).name
                    if name not in by_heading[current]:
                        by_heading[current].append(name)

    return [(h, imgs) for h, imgs in by_heading.items() if imgs]


def enrich_parsed_text(path: Path, base_text: str) -> str:
    """Добавляет текст из иллюстраций под заголовками разделов."""
    source = path.name
    media = _images_by_name(path)
    blocks: list[str] = [base_text]

    for heading, image_names in _section_image_names(path):
        if not image_names:
            continue
        parts: list[str] = []
        for name in image_names:
            data = media.get(name)
            if not data:
                continue
            text = _image_text(source, name, data, heading)
            if text.startswith("[Иллюстрация"):
                continue
            parts.append(text)
        if parts:
            blocks.append(f"{heading}\n\n" + "\n\n".join(parts))

    return "\n\n".join(blocks)


def values_image_names(source: str) -> list[str]:
    if source != "newbiePage.docx":
        return []
    return list(_NEWBIE_VALUES.keys())
