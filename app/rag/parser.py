"""Парсинг docx, pdf, md, txt + извлечение картинок."""
from __future__ import annotations

import io
import zipfile
from pathlib import Path

from docx import Document
from docx.table import Table
from docx.text.paragraph import Paragraph


SUPPORTED = {".docx", ".pdf", ".md", ".txt", ".markdown"}


def list_document_files(*dirs: Path) -> list[Path]:
    files: list[Path] = []
    for d in dirs:
        if not d.exists():
            continue
        for p in sorted(d.iterdir()):
            if p.is_file() and p.suffix.lower() in SUPPORTED:
                files.append(p)
    return files


def _iter_block_items(parent):
    from docx.document import Document as DocxDocument

    if isinstance(parent, DocxDocument):
        parent_elm = parent.element.body
    else:
        parent_elm = parent._element
    for child in parent_elm.iterchildren():
        tag = child.tag.split("}")[-1]
        if tag == "p":
            yield Paragraph(child, parent)
        elif tag == "tbl":
            yield Table(child, parent)


def _table_to_text(table: Table) -> str:
    rows: list[str] = []
    for row in table.rows:
        cells = [c.text.strip().replace("\n", " ") for c in row.cells if c.text.strip()]
        if cells:
            rows.append(" | ".join(cells))
    return "\n".join(rows)


def parse_docx(path: Path) -> tuple[str, list[tuple[str, bytes]]]:
    doc = Document(path)
    parts: list[str] = []
    for block in _iter_block_items(doc):
        if isinstance(block, Paragraph):
            text = block.text.strip()
            if text:
                parts.append(text)
        elif isinstance(block, Table):
            t = _table_to_text(block)
            if t:
                parts.append(f"[Таблица]\n{t}")

    images: list[tuple[str, bytes]] = []
    try:
        with zipfile.ZipFile(path) as zf:
            for name in zf.namelist():
                if name.startswith("word/media/") and not name.endswith("/"):
                    data = zf.read(name)
                    if len(data) > 500:
                        images.append((Path(name).name, data))
    except zipfile.BadZipFile:
        pass

    from app.rag.docx_sections import enrich_parsed_text

    return enrich_parsed_text(path, "\n\n".join(parts)), images


def parse_pdf(path: Path) -> str:
    import fitz

    doc = fitz.open(path)
    parts: list[str] = []
    for page in doc:
        text = page.get_text().strip()
        if text:
            parts.append(text)
    doc.close()
    return "\n\n".join(parts)


def parse_text_file(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore")


def parse_document(path: Path) -> tuple[str, list[tuple[str, bytes]]]:
    ext = path.suffix.lower()
    if ext == ".docx":
        return parse_docx(path)
    if ext == ".pdf":
        return parse_pdf(path), []
    if ext in {".md", ".txt", ".markdown"}:
        return parse_text_file(path), []
    raise ValueError(f"Unsupported format: {ext}")


def chunk_text(text: str, size: int, overlap: int) -> list[str]:
    text = text.strip()
    if not text:
        return []
    if len(text) <= size:
        return [text]

    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = start + size
        piece = text[start:end].strip()
        if piece:
            chunks.append(piece)
        if end >= len(text):
            break
        start = max(end - overlap, start + 1)
    return chunks
