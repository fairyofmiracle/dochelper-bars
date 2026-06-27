# DocHelper Барс

AI-агент первой линии поддержки для кейса **АО «Барс Груп»**, хакатон **«Королева Кода»** (команда **one_commit**).

RAG-бот по корпоративной документации: **Telegram** + **Web**, эскалация на оператора, аналитика.

| Материалы | Файл |
|-----------|------|
| Сдача проекта (описание, AI-раскрытие, чеклист) | [SUBMISSION.md](SUBMISSION.md) |
| Презентация (текст слайдов) | [PRESENTATION.md](PRESENTATION.md) |
| Речь на защиту | [SPEECH.md](SPEECH.md) |
| HTML-презентация | http://127.0.0.1:8026/presentation (после запуска) |

**Репозиторий:** https://tatarsan.space/one_commit/bars_support_bot

---

## Соответствие брифу

### MVP (из брифа) — что требовалось

| Требование брифа | Статус | Реализация |
|------------------|--------|------------|
| Приём **текстовых** сообщений в Telegram | ✅ | `app/bot/telegram_bot.py` |
| Семантический поиск по docx / pdf / md | ✅ | Qdrant + `multilingual-e5-base` |
| **Скрины, схемы, таблицы из базы знаний** (не от пользователя) | ✅ | Картинки из docx при индексации; в ответе Web — при визуальных вопросах |
| RAG: ответ LLM + ссылка на документ | ✅ | GigaChat / Ollama, блок источника в UI |
| Уверенность → «не нашёл» + кнопка оператора | ✅ | `CONFIDENCE_THRESHOLD`, inline-кнопка |
| Эскалация: история → чат поддержки / оператор | ✅ | Очередь + панель `/operator` (вместо email в MVP — web-оператор) |
| Базовая аналитика | ✅ | `/api/analytics`, панель оператора |
| Антиспам / лимиты | ✅ | `app/services/rate_limit.py`, Redis + Web/TG |
| Аналитика трендов / слабых мест доков | ✅ | `weak_spots`, тренд по дням, растущие темы |
| Закрытый контур (LLM локально) | ✅ | Ollama + embeddings + Qdrant без обязательного интернета |

### Будущие возможности (из брифа) — не MVP, roadmap

| Требование брифа | Статус | Комментарий |
|------------------|--------|-------------|
| **Jira / Zendesk / Usedesk** — тикет из диалога | ⚠️ | Mock-тикет при эскалации + панель оператора; реальный API Usedesk по ключам |
| Авто-reindex Confluence / Git | ⚠️ | Webhook `/api/integrations/webhooks/git`, кнопка «Симулировать push» в `/operator` |
| **Скриншот пользователя** (ошибка на экране) | ⚠️ | Web + TG: vision + тип изображения; нужен `OLLAMA_VISION_MODEL` |

### Сверх брифа (наше усиление MVP)

| Функция | Статус | Комментарий |
|---------|--------|-------------|
| **Голосовые** в Telegram | ✅ | **В брифе MVP не было** — добавили Whisper для demo |
| Web-чат + презентация | ✅ | Платформа брифа — «стационарная версия» |
| Панель оператора с demo-очередью | ✅ | Удобнее для защиты, чем только TG-чат |

**Тест-кейсы заказчика (17 вопросов):** `python scripts\test_brief_cases.py`  
**Последний прогон:** 27.06.2026 → **16/17 (94%)** — [TEST_REPORT.md](TEST_REPORT.md)

---

## Требования

- **Windows 10/11** или Linux
- **Python 3.10+**
- **Docker Desktop** (Qdrant, Redis, Ollama)
- **~8 GB RAM** (embeddings + Ollama 3B; 7B — лучше на GPU/VM)
- Диск **`D:/bars-support-bot-data`** (или свой `DATA_ROOT`) — модели **не в Git**

---

## Установка и запуск (Windows)

### 1. Клонировать репозиторий

```powershell
git clone ssh://git@tatarsan.space/one_commit/bars_support_bot.git
cd bars_support_bot
```

### 2. Документы кейса

Положите 4 docx из брифа в `data/docs/`:

- `Functionalnie.docx` (или `Functionalnie.docx` из материалов)
- `Komandirovka.docx`
- `ReestrMebeli.docx`
- `newbiePage.docx`

Или скопируйте из папки материалов хакатона:

```powershell
.\scripts\copy_docs.ps1
```

### 3. Окружение Python

```powershell
python -m venv .venv
.\.venv\Scripts\pip install -r requirements.txt
copy .env.example .env
# Отредактируйте .env: TELEGRAM_BOT_TOKEN, GIGACHAT_CREDENTIALS или LLM_PROVIDER=ollama
```

### 4. Инфраструктура Docker

```powershell
.\scripts\setup_d_drive.ps1    # один раз — каталоги на D:
.\scripts\docker_up.ps1        # Qdrant + Redis + Ollama + pull модели
```

### 5. Индексация базы знаний

```powershell
$env:DATA_ROOT="D:/bars-support-bot-data"
$env:QDRANT_URL="http://127.0.0.1:6333"
.\.venv\Scripts\python scripts\ingest.py --clear
```

### 6. Запуск бота

```powershell
.\scripts\start_local.ps1
```

| URL | Назначение |
|-----|------------|
| http://127.0.0.1:8026 | Web-чат пользователя |
| http://127.0.0.1:8026/operator | Панель оператора |
| http://127.0.0.1:8026/presentation | Презентация для защиты |
| http://127.0.0.1:8026/api/health | Статус сервисов |

Проверка готовности: `.\scripts\check_ready.ps1`

---

## Telegram

1. Создайте бота у [@BotFather](https://t.me/BotFather), токен в `.env` → `TELEGRAM_BOT_TOKEN`
2. Если `api.telegram.org` недоступен — **VPN** или `TELEGRAM_PROXY_URL` в `.env`
3. `/start` — приветствие; кнопки **«Задать вопрос»** и **«Отмена»**
4. Оператор: `/operator`, слово «оператор» или inline-кнопка при низкой уверенности
5. Голосовые и фото — поддерживаются (vision для фото — опционально)

**Важно:** одновременно может работать только **один** процесс Telegram-бота (локальный **или** Docker `app`).

---

## Настройка `.env` (основное)

```env
DATA_ROOT=D:/bars-support-bot-data

# LLM: gigachat (демо с интернетом) или ollama (закрытый контур)
LLM_PROVIDER=gigachat
GIGACHAT_CREDENTIALS=...

# или локально:
# LLM_PROVIDER=ollama
# OLLAMA_BASE_URL=http://127.0.0.1:11434
# OLLAMA_MODEL=qwen2.5:3b-instruct

TELEGRAM_BOT_TOKEN=...
TELEGRAM_ENABLED=true
CONFIDENCE_THRESHOLD=0.55
WHISPER_ENABLED=true
WHISPER_MODEL=base
BOT_NAME=DocHelper Барс
```

Полный пример: [.env.example](.env.example)

---

## Где лежат модели (не в Git)

| Компонент | Путь под `DATA_ROOT` |
|-----------|----------------------|
| Embeddings e5 | `huggingface/` |
| Whisper | `whisper/` |
| Ollama LLM | `ollama/` |
| Qdrant | `qdrant/` |
| Картинки из docx | `doc-images/` |

---

## Структура проекта

```
app/rag/          — парсинг docx, embeddings, Qdrant, иллюстрации
app/llm/          — GigaChat / Ollama
app/services/     — RAG-чат, аналитика, эскалация, Whisper
app/bot/          — Telegram
app/api/          — REST API
static/           — Web UI, оператор, презентация
scripts/          — ingest, тесты брифа, docker, запуск
data/docs/        — документы для индексации (не в Git, если большие)
```

---

## Положение хакатона — что сдаём

1. **Краткое описание** — [SUBMISSION.md](SUBMISSION.md) §1  
2. **Презентация** — [PRESENTATION.md](PRESENTATION.md) + `/presentation`  
3. **Работающий прототип** — Web + Telegram (live demo)  
4. **Исходный код** — этот репозиторий  
5. **Технологии** — SUBMISSION.md §5  
6. **Раскрытие AI** — SUBMISSION.md §6  

Критерии оценки (35 баллов) — таблица в [SUBMISSION.md](SUBMISSION.md#соответствие-критериям-оценки).

---

## Полезные команды

```powershell
python scripts\test_brief_cases.py   # 17 тест-кейсов брифа
.\scripts\stop_bot.ps1               # остановить локальный процесс
docker compose --profile full stop app  # не дублировать TG с Docker
```
