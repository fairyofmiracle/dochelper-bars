# DocHelper Барс

**AI-агент первой линии поддержки** для корпоративной документации АО «Барс Груп»

Хакатон **«Королева Кода»** · кейс **Барс Груп** · команда **one_commit** (solo)

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](requirements.txt)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-green.svg)](https://fastapi.tiangolo.com/)
[![RAG](https://img.shields.io/badge/RAG-Qdrant%20%2B%20e5-purple.svg)](app/rag/)
[![Brief tests](https://img.shields.io/badge/brief%20tests-94%25-brightgreen.svg)](TEST_REPORT.md)

---

## О проекте

**DocHelper** — не «чат с ChatGPT», а **orchestrated RAG pipeline** из шести AI-агентов: сотрудник задаёт вопрос в **Telegram** или **Web**, система ищет ответ в docx заказчика, формирует ответ **только по найденным фрагментам**, указывает **источник** и при необходимости прикладывает **иллюстрацию из документа**. Если уверенность низкая или темы нет в базе — **эскалация к оператору** без галлюцинаций.

Проект создан за время хакатона **одним участником** (команда **one_commit**): backend, RAG, Telegram-бот, web-интерфейс, панель оператора, analytics, индексация docx с картинками, презентация и прогон 17 тест-кейсов брифа.

### Ключевые результаты

| Метрика | Значение |
|---------|----------|
| Автоответы на брифе | **94%** (16/17) при цели **≥ 40%** |
| Среднее время ответа | **~1,6 с** |
| AI-агентов в pipeline | **6** (+ vision при индексации) |
| Каналы | **Telegram** + **Web** + **Operator panel** |

Подробный отчёт: [TEST_REPORT.md](TEST_REPORT.md)

---

## Что умеет

- **RAG** по docx / pdf / md — Qdrant + `multilingual-e5-base`
- **Распознавание текста в картинках docx** — vision + OCR для слайдов «Ценности»
- **Confidence gate** — ниже порога → оператор, не выдумка
- **Telegram** — текст, голос (Whisper), фото (vision → RAG)
- **Web-чат** — источник, скачивание docx, иллюстрации
- **Панель оператора** — очередь эскалаций, ответ пользователю, analytics
- **Analytics** — weak spots, тренды, % авто/эскалация
- **Rate limit** — защита от спама (Redis)
- **Dual LLM** — GigaChat (demo) / Ollama (закрытый контур prod)

---

## Архитектура

```
Telegram / Web
      ↓
 FastAPI Orchestrator
      ↓
 Speech → Retriever (e5+Qdrant) → Generator (LLM) → Evaluator
      ↓                              ↓
 Escalation (operator)          Analytics (Redis)
```

**Хранение:** docx на диске · векторы в **Qdrant** · сессии и analytics в **Redis** · картинки из docx в `DATA_ROOT/doc-images`

---

## Быстрый старт

### Требования

- Python **3.10+**
- **Docker Desktop** (Qdrant, Redis, Ollama)
- **~8 GB RAM**
- Каталог данных **`D:/bars-support-bot-data`** (или свой `DATA_ROOT`) — модели **не в Git**

### 1. Клонирование

```powershell
git clone https://github.com/YOUR_USERNAME/bars-support-bot.git
cd bars-support-bot
```

> Замените `YOUR_USERNAME` на свой GitHub после публикации репозитория.

### 2. Документы кейса

Положите 4 docx из материалов хакатона в `data/docs/`:

- `Functionalnie.docx`
- `Komandirovka.docx`
- `ReestrMebeli.docx`
- `newbiePage.docx`

```powershell
.\scripts\copy_docs.ps1   # если docx лежат в папке материалов AO_BARS_GRUP
```

### 3. Python и env

```powershell
python -m venv .venv
.\.venv\Scripts\pip install -r requirements.txt
copy .env.example .env
# Заполните: TELEGRAM_BOT_TOKEN, GIGACHAT_* или LLM_PROVIDER=ollama
```

### 4. Docker и модели

```powershell
.\scripts\setup_d_drive.ps1
.\scripts\docker_up.ps1
```

### 5. Индексация и запуск

```powershell
$env:DATA_ROOT="D:/bars-support-bot-data"
$env:QDRANT_URL="http://127.0.0.1:6333"
.\.venv\Scripts\python scripts\ingest.py --clear
.\scripts\start_local.ps1
```

| URL | Назначение |
|-----|------------|
| http://127.0.0.1:8026 | Web-чат |
| http://127.0.0.1:8026/operator | Панель оператора |
| http://127.0.0.1:8026/presentation | HTML-презентация |
| http://127.0.0.1:8026/api/health | Health-check |

```powershell
python scripts\test_brief_cases.py   # 17 кейсов брифа
.\scripts\check_ready.ps1
```

---

## Telegram

1. Токен от [@BotFather](https://t.me/BotFather) → `TELEGRAM_BOT_TOKEN` в `.env`
2. `/start` — меню · «Задать вопрос» · голос · фото
3. При низкой уверенности — кнопка **«Переключить на оператора»**

> Одновременно работает **только один** инстанс бота (локальный Python **или** Docker `app`).

---

## Стек технологий

| Слой | Технологии |
|------|------------|
| Backend | Python, FastAPI, Pydantic |
| RAG | Qdrant, sentence-transformers e5, chunking |
| LLM | GigaChat API / Ollama (qwen2.5) |
| Vision | Ollama qwen2.5vl (docx + скрины пользователя) |
| Speech | faster-whisper |
| Cache / sessions | Redis |
| Frontend | HTML/CSS/JS (чат, operator, presentation) |
| Bot | python-telegram-bot |
| Infra | Docker Compose |

---

## Структура репозитория

```
app/
  rag/           — парсинг docx, embeddings, Qdrant, vision, картинки
  llm/           — GigaChat / Ollama
  services/      — RAG-чат, analytics, эскалация, rate limit, Whisper
  bot/           — Telegram
  api/           — REST API
static/          — Web UI, operator, presentation
scripts/         — ingest, тесты брифа, docker, запуск
data/docs/       — docx для индексации (не в Git — см. data/docs/README.md)
```

---

## Материалы хакатона

| Документ | Описание |
|----------|----------|
| [SUBMISSION.md](SUBMISSION.md) | Описание для сдачи, AI-раскрытие, чеклист |
| [PRESENTATION.md](PRESENTATION.md) | Текст слайдов |
| [SPEECH_SHORT.md](SPEECH_SHORT.md) | Речь для защиты (по слайдам) |
| [DEFENSE_SCORING.md](DEFENSE_SCORING.md) | Защита по критериям жюри |
| [TEST_REPORT.md](TEST_REPORT.md) | Метрики 17 кейсов брифа |
| [DEFENSE.md](DEFENSE.md) | Q&A для проверяющего |

---

## Команда

**one_commit** — solo-проект на хакатоне «Королева Кода»

Один участник: проектирование, RAG, backend, Telegram, web UI, operator panel, индексация docx с vision, тесты брифа, презентация и защита.

---

## Лицензия и данные

- Исходный код — для демонстрации решения кейса хакатона.
- Корпоративные docx **не включены** в репозиторий — только инструкция в [data/docs/README.md](data/docs/README.md).
- **Не коммитьте** `.env` с токенами (уже в `.gitignore`).

---

## Публикация на GitHub

```powershell
# После создания пустого репозитория на github.com:
git remote add github https://github.com/YOUR_USERNAME/bars-support-bot.git
git add .
git commit -m "DocHelper: RAG support bot for Bars Group hackathon case"
git push -u github main
```

Перед push убедитесь: `.env` не в staging, docx не добавлены случайно.
