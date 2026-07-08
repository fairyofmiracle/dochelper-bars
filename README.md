# DocHelper Барс

**AI-агент первой линии поддержки** по корпоративной документации · кейс **АО «Барс Груп»** · хакатон **«Королева Кода»**

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](requirements.txt)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-green.svg)](https://fastapi.tiangolo.com/)
[![RAG](https://img.shields.io/badge/RAG-Qdrant%20%2B%20e5-purple.svg)](app/rag/)
[![Brief tests](https://img.shields.io/badge/brief%20tests-94%25-brightgreen.svg)](TEST_REPORT.md)

---

## О проекте

**DocHelper** — orchestrated **RAG pipeline** из шести AI-агентов. Сотрудник задаёт вопрос в **Telegram** или **Web** — система ищет ответ в docx, отвечает **только по найденным фрагментам**, указывает **источник** и прикладывает **иллюстрации из документа**. При низкой уверенности — **эскалация к оператору**.

| Метрика | Значение |
|---------|----------|
| Автоответы на брифе | **94%** (16/17), цель **≥ 40%** |
| Среднее время ответа | **~1,6 с** |
| Каналы | Telegram · Web · Operator panel |

Отчёт по тестам: [TEST_REPORT.md](TEST_REPORT.md)

---

## Возможности

- RAG по docx / pdf / md — **Qdrant** + `multilingual-e5-base`
- Распознавание текста в **картинках docx** (vision + OCR)
- **Confidence gate** — без галлюцинаций
- Telegram: текст, голос (Whisper), фото (vision → RAG)
- Web-чат: источник, скачивание docx, схемы
- Панель оператора, analytics, rate limit
- **GigaChat** (demo) / **Ollama** (закрытый контур)

---

## Архитектура

```
Telegram / Web → FastAPI Orchestrator
  → Speech → Retriever (e5+Qdrant) → Generator (LLM) → Evaluator
  → Escalation (operator) · Analytics (Redis)
```

**Хранение:** docx на диске · векторы — **Qdrant** · сессии — **Redis**

---

## Быстрый старт

**Требования:** Python 3.10+, Docker (Qdrant, Redis, Ollama), ~8 GB RAM

```powershell
git clone https://github.com/fairyofmiracle/dochelper-bars.git
cd dochelper-bars

python -m venv .venv
.\.venv\Scripts\pip install -r requirements.txt
copy .env.example .env
```

1. Положите docx в `data/docs/` (см. [data/docs/README.md](data/docs/README.md))
2. Запустите Docker: `.\scripts\docker_up.ps1`
3. Индексация: `.\.venv\Scripts\python scripts\ingest.py --clear`
4. Запуск: `.\scripts\start_local.ps1`

| URL | Назначение |
|-----|------------|
| http://127.0.0.1:8026 | Web-чат |
| http://127.0.0.1:8026/operator | Панель оператора |
| http://127.0.0.1:8026/presentation | Презентация |
| http://127.0.0.1:8026/api/health | Health-check |

Тесты брифа: `python scripts\test_brief_cases.py`

---

## Telegram

Токен [@BotFather](https://t.me/BotFather) → `TELEGRAM_BOT_TOKEN` в `.env`.  
Команды: `/start`, `/help`, `/operator`.

---

## Стек

Python · FastAPI · Qdrant · Redis · sentence-transformers · GigaChat / Ollama · faster-whisper · python-telegram-bot · Docker Compose

---

## Структура

```
app/rag/      — парсинг, embeddings, Qdrant, vision
app/llm/      — GigaChat / Ollama
app/services/ — RAG, analytics, эскалация
app/bot/      — Telegram
static/       — Web UI, operator, presentation
scripts/      — ingest, тесты, docker
```

---

## Автор

**one_commit** · [github.com/fairyofmiracle/dochelper-bars](https://github.com/fairyofmiracle/dochelper-bars)

Корпоративные docx и `.env` в репозиторий **не входят** (см. `.gitignore`).
