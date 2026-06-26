# DocHelper Барс

Telegram + Web RAG-бот для хакатона Барс Груп. Ответы по docx/PDF из Confluence, локальная LLM (Ollama), Qdrant, Redis.

## Быстрый старт

```powershell
# 1. Ollama на хосте
ollama pull qwen2.5:7b-instruct

# 2. Документы кейса
.\scripts\copy_docs.ps1

# 3. Docker
docker compose up --build -d
```

- Web UI: http://127.0.0.1:8026  
- API docs: http://127.0.0.1:8026/docs  
- Health: http://127.0.0.1:8026/api/health  

## Локально без Docker

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
docker compose up -d qdrant redis
python scripts\ingest.py --clear
python main.py
```

## Telegram

1. Токен в `.env` → `TELEGRAM_BOT_TOKEN`
2. ID чата поддержки → `TELEGRAM_SUPPORT_CHAT_ID`
3. Бот стартует вместе с `main.py`

## Админка

Вкладка «Админка» на http://127.0.0.1:8026 — загрузка/удаление docx, переиндексация.

## Vision (схемы в docx)

```powershell
ollama pull qwen2-vl:7b
```

В `.env`: `OLLAMA_VISION_MODEL=qwen2-vl:7b`

## Структура

```
app/rag/       — парсинг, embeddings, Qdrant
app/llm/       — Ollama / GigaChat
app/services/  — chat, analytics, escalation
app/bot/       — Telegram
app/api/       — REST
static/        — Web UI
data/docs/     — база знаний
```

Подробнее: `QUICKSTART.md`, `MODELS.md`, `READINESS.md`
