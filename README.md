# DocHelper Барс

Telegram + Web RAG-бот — кейс **АО «Барс Групп»**, хакатон **«Королева Кода»** (команда **one_commit**).

> **Репозиторий:** `https://github.com/<ваш-логин>/bars-support-bot` ← вставьте ссылку после push

## Что умеет (MVP)

- RAG по docx/pdf/md с указанием **Источника**
- Telegram + Web UI + админка + аналитика с диаграммами
- GigaChat (быстрое демо) / Ollama (локальный закрытый контур)
- Эскалация на оператора с историей диалога
- **Голосовые** → Whisper (локально) → ответ нейросети

## Быстрый старт

```powershell
# 1. Инфраструктура (Qdrant, Redis, Ollama)
.\scripts\docker_up.ps1

# 2. Документы кейса → data/docs
.\scripts\copy_docs.ps1

# 3. Python + индекс
python -m venv .venv
.\.venv\Scripts\pip install -r requirements.txt
.\.venv\Scripts\python scripts\ingest.py --clear

# 4. Запуск (Telegram + Web)
.\scripts\start_local.ps1
```

- Web: http://127.0.0.1:8026  
- Health: http://127.0.0.1:8026/api/health  
- Тест-кейсы брифа: `python scripts\test_brief_cases.py`

## Модели — где лежат (не в Git!)

Все тяжёлые файлы на диске **`D:/bars-support-bot-data`** (`DATA_ROOT`):

| Что | Путь |
|---|---|
| Embeddings (e5) | `D:/bars-support-bot-data/huggingface` |
| Whisper | `D:/bars-support-bot-data/whisper` |
| Ollama LLM | `D:/bars-support-bot-data/ollama` |
| Qdrant | `D:/bars-support-bot-data/qdrant` |

**На VM:** смонтируйте тот же `DATA_ROOT` или заново скачайте модели на VM (см. ниже). В репозиторий модели **не коммитятся**.

```powershell
# Ollama на VM
docker compose exec ollama ollama pull qwen2.5:3b-instruct

# Whisper — скачается сам при первом голосовом (или заранее):
# WHISPER_MODEL=tiny  # быстрее на CPU, хуже качество
# WHISPER_MODEL=base  # баланс для демо
```

## Whisper — чтобы не «падал»

1. На CPU используйте `WHISPER_MODEL=tiny` или `base` (не `small`/`medium`)
2. Первое голосовое **долго** (~30–60 с) — идёт загрузка модели, это нормально
3. Нужны пакеты: `faster-whisper`, `imageio-ffmpeg` (ffmpeg в комплекте)
4. При ошибке бот предложит написать текстом или нажать «Оператор»

## Telegram

1. `TELEGRAM_BOT_TOKEN` в `.env`
2. `TELEGRAM_SUPPORT_CHAT_ID` — чат для эскалации
3. VPN, если `api.telegram.org` недоступен
4. `/start` — подсказка и кнопки: Задать вопрос / Отмена / Оператор

## `.env` (основное)

```env
LLM_PROVIDER=gigachat          # или ollama для закрытого контура
GIGACHAT_CREDENTIALS=...
WHISPER_ENABLED=true
WHISPER_MODEL=base
DATA_ROOT=D:/bars-support-bot-data
```

## Структура

```
app/rag/       — парсинг, embeddings, Qdrant
app/llm/       — Ollama / GigaChat
app/services/  — chat, analytics, escalation, speech (Whisper)
app/bot/       — Telegram
app/api/       — REST
static/        — Web UI
scripts/       — ingest, test_brief_cases, start_local
```

## Коммит для хакатона (пример сообщения)

```
feat: DocHelper Барс — RAG-бот первой линии поддержки для кейса Барс Групп

Telegram + Web, GigaChat/Ollama, Qdrant, эскалация, аналитика, Whisper для голосовых.
Хакатон «Королева Кода», команда one_commit.
```

Короткий вариант:

```
feat: MVP DocHelper Барс — RAG + Telegram + GigaChat + Whisper (Королева Кода)
```
