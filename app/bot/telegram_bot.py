"""Telegram-бот DocHelper Барс."""
from __future__ import annotations

import asyncio
import logging

from telegram import BotCommand, InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup, Update
from telegram.constants import ChatAction, ParseMode
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes, MessageHandler, filters

from app.branding import welcome_message
from app.config import settings, telegram_proxy_url
from app.rag.image_store import resolve_doc_image
from app.rag.vision import vision_ready
from app.services.chat_async import ask_async, ask_from_image_async
from app.services.escalation import notify_support
from app.services.escalation_queue import enqueue
from app.services.session import append_message
from app.services.speech import transcribe_bytes, whisper_ready

logger = logging.getLogger(__name__)

STATUS_LLM = "Формирую ответ..."

BTN_ASK = "Задать вопрос"
BTN_CANCEL = "Отмена"
BTN_OPERATOR = "Переключить на оператора"

MAIN_KEYBOARD = ReplyKeyboardMarkup(
    [
        [KeyboardButton(BTN_ASK)],
        [KeyboardButton(BTN_CANCEL)],
    ],
    resize_keyboard=True,
    is_persistent=True,
)

_user_locks: dict[str, asyncio.Lock] = {}


def operator_inline_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton(BTN_OPERATOR, callback_data="escalate")]]
    )


def _session_id(update: Update) -> str:
    user = update.effective_user
    return f"tg-{user.id}" if user else "tg-anon"


def _user_lock(session_id: str) -> asyncio.Lock:
    if session_id not in _user_locks:
        _user_locks[session_id] = asyncio.Lock()
    return _user_locks[session_id]


async def _keep_typing(chat, stop: asyncio.Event) -> None:
    while not stop.is_set():
        try:
            await chat.send_action(ChatAction.TYPING)
        except Exception:
            pass
        try:
            await asyncio.wait_for(stop.wait(), timeout=4.0)
        except asyncio.TimeoutError:
            continue


def _trim_text(text: str) -> str:
    if len(text) > 4000:
        return text[:3990] + "…"
    return text


async def _send_doc_images(update: Update, image_urls: list[str]) -> None:
    message = update.effective_message
    if not message or not image_urls:
        return
    for url in image_urls[:2]:
        rel = url.removeprefix("/api/doc-images/").lstrip("/")
        path = resolve_doc_image(rel)
        if not path:
            continue
        try:
            with path.open("rb") as fh:
                await message.reply_photo(photo=fh, caption="Иллюстрация из документации")
        except Exception:
            logger.debug("reply_photo failed for %s", path, exc_info=True)


async def _send_result(
    update: Update,
    text: str,
    needs_operator: bool,
    *,
    edit_message=None,
    images: list[str] | None = None,
) -> None:
    text = _trim_text(text)
    inline = operator_inline_keyboard() if needs_operator else None

    if edit_message is not None:
        try:
            await edit_message.edit_text(text, reply_markup=inline)
            await _send_doc_images(update, images or [])
            return
        except Exception:
            logger.debug("edit_text failed, sending new message", exc_info=True)

    message = update.effective_message
    if not message:
        return
    await message.reply_text(text, reply_markup=inline)
    await _send_doc_images(update, images or [])


async def _process_question(update: Update, context: ContextTypes.DEFAULT_TYPE, question: str) -> None:
    sid = _session_id(update)
    context.user_data.pop("awaiting_question", None)

    async with _user_lock(sid):
        message = update.effective_message
        status_msg = None
        stop_typing = asyncio.Event()
        typing_task = None

        if message:
            status_msg = await message.reply_text(STATUS_LLM)
            typing_task = asyncio.create_task(_keep_typing(message.chat, stop_typing))

        append_message(sid, "user", question)
        try:
            result = await ask_async(question)
        except Exception as exc:
            logger.exception("ask_async failed")
            append_message(sid, "assistant", f"Ошибка: {exc}")
            if typing_task:
                stop_typing.set()
                await typing_task
            err_text = (
                "Не удалось получить ответ — возможно, проблема с сетью или сервисом.\n\n"
                "Нажмите кнопку ниже, чтобы переключиться на оператора."
            )
            await _send_result(update, err_text, True, edit_message=status_msg)
            return
        finally:
            stop_typing.set()
            if typing_task:
                await typing_task

        append_message(sid, "assistant", result.answer)

        if result.escalated:
            user = update.effective_user
            label = user.full_name if user else "unknown"
            await notify_support(sid, label, question)
            enqueue(sid, label, question)

        await _send_result(
            update,
            result.answer,
            result.needs_operator and not result.escalated,
            edit_message=status_msg,
            images=result.images,
        )


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    context.user_data.pop("awaiting_question", None)
    await update.message.reply_text(
        welcome_message(),
        reply_markup=MAIN_KEYBOARD,
    )
    await update.message.reply_text(
        "Напишите вопрос текстом, *голосовым* или *скриншотом*.\n"
        "Кнопка «Задать вопрос» — чтобы явно начать диалог.\n\n"
        "Если не найду ответ в документации — предложу оператора.",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=MAIN_KEYBOARD,
    )


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    voice_line = (
        "🎤 Голосовое — Whisper распознает и отвечает.\n"
        "🖼 Фото/скриншот — распознаю и ищу в документации.\n"
        if whisper_ready()
        else "🎤 Голос: faster-whisper + ffmpeg.\n🖼 Фото: нужен OLLAMA_VISION_MODEL.\n"
    )
    await update.message.reply_text(
        f"«{BTN_ASK}» — задать вопрос по документации\n"
        f"«{BTN_CANCEL}» — отменить текущее действие\n"
        f"/operator — связаться с оператором (если бот не помог)\n"
        f"{voice_line}\n"
        "Команды: /start, /help, /operator",
        reply_markup=MAIN_KEYBOARD,
    )


async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.message
    if not message:
        return
    voice = message.voice or message.audio
    if not voice:
        return

    if not whisper_ready():
        await message.reply_text(
            "Голосовые пока недоступны (Whisper не установлен).\n"
            "Напишите вопрос текстом или нажмите «Задать вопрос».",
            reply_markup=MAIN_KEYBOARD,
        )
        return

    status = await message.reply_text("🎤 Распознаю голос…")
    try:
        tg_file = await context.bot.get_file(voice.file_id)
        audio_bytes = bytes(await tg_file.download_as_bytearray())
        text = await asyncio.to_thread(transcribe_bytes, audio_bytes, ".ogg")
    except Exception as exc:
        logger.exception("voice transcribe failed")
        await status.edit_text(
            "Не удалось распознать голос (нужен ffmpeg в PATH).\n"
            "Напишите текстом или нажмите «Переключить на оператора».",
            reply_markup=operator_inline_keyboard(),
        )
        return

    if not text.strip():
        await status.edit_text(
            "Не разобрал речь. Повторите медленнее или напишите текстом.",
            reply_markup=MAIN_KEYBOARD,
        )
        return

    preview = text if len(text) <= 400 else text[:397] + "…"
    await status.edit_text(f"🎤 Распознано:\n«{preview}»")
    await _process_question(update, context, text)


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.message
    if not message or not message.photo:
        return

    photo = message.photo[-1]
    caption = (message.caption or "").strip()
    sid = _session_id(update)

    if not vision_ready():
        await message.reply_text(
            "🖼 Распознавание скриншотов пока недоступно.\n"
            "На сервере задайте OLLAMA_VISION_MODEL=qwen2-vl:7b и выполните "
            "`ollama pull qwen2-vl:7b`.\n\n"
            "Или опишите проблему текстом.",
            reply_markup=MAIN_KEYBOARD,
        )
        return

    status = await message.reply_text("🖼 Анализирую изображение…")
    async with _user_lock(sid):
        try:
            tg_file = await context.bot.get_file(photo.file_id)
            image_bytes = bytes(await tg_file.download_as_bytearray())
            append_message(sid, "user", f"[фото] {caption or 'скриншот'}")
            result = await ask_from_image_async(image_bytes, caption)
        except Exception as exc:
            logger.exception("photo failed")
            await status.edit_text(
                "Не удалось обработать изображение. Опишите текстом или нажмите «Оператор».",
                reply_markup=operator_inline_keyboard(),
            )
            return

        append_message(sid, "assistant", result.answer)
        if result.escalated:
            user = update.effective_user
            await notify_support(sid, user.full_name if user else "unknown", caption or "[фото]")
            enqueue(sid, user.full_name if user else "unknown", caption or "[фото]")

        await _send_result(
            update,
            result.answer,
            result.needs_operator and not result.escalated,
            edit_message=status,
            images=result.images,
        )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.message.text:
        return
    text = update.message.text.strip()

    if text.lower() in ("старт", "start", "начать"):
        await start(update, context)
        return

    if text == BTN_ASK:
        context.user_data["awaiting_question"] = True
        await update.message.reply_text(
            "Напишите Ваш вопрос одним сообщением — я найду ответ в базе документов.",
            reply_markup=MAIN_KEYBOARD,
        )
        return

    if text == BTN_CANCEL:
        context.user_data.pop("awaiting_question", None)
        await update.message.reply_text(
            "Действие отменено. Нажмите «Задать вопрос» или напишите вопрос текстом.",
            reply_markup=MAIN_KEYBOARD,
        )
        return

    if text in (BTN_OPERATOR, "Оператор", "оператор"):
        await operator_cmd(update, context)
        return

    if context.user_data.get("awaiting_question"):
        await _process_question(update, context, text)
        return

    # Прямой вопрос без нажатия «Задать вопрос»
    if len(text) > 12 and text.endswith("?"):
        await _process_question(update, context, text)
        return

    await update.message.reply_text(
        f"Напишите вопрос текстом или нажмите «{BTN_ASK}».",
        reply_markup=MAIN_KEYBOARD,
    )


async def operator_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    sid = _session_id(update)
    context.user_data.pop("awaiting_question", None)
    async with _user_lock(sid):
        append_message(sid, "user", BTN_OPERATOR)
        result = await ask_async("оператор", force_escalate=True)
        user = update.effective_user
        await notify_support(sid, user.full_name if user else "unknown")
        enqueue(sid, user.full_name if user else "unknown", BTN_OPERATOR)
        await _send_result(update, result.answer, False)


async def callback_escalate(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    sid = _session_id(update)
    context.user_data.pop("awaiting_question", None)
    async with _user_lock(sid):
        append_message(sid, "user", BTN_OPERATOR)
        result = await ask_async("оператор", force_escalate=True)
        user = update.effective_user
        await notify_support(sid, user.full_name if user else "unknown")
        enqueue(sid, user.full_name if user else "unknown", BTN_OPERATOR)
        if query.message:
            await query.message.reply_text(result.answer, reply_markup=MAIN_KEYBOARD)
        else:
            await _send_result(update, result.answer, False)


async def _post_init(application: Application) -> None:
    await application.bot.set_my_commands(
        [
            BotCommand("start", "Подсказка и меню"),
            BotCommand("help", "Справка по кнопкам"),
            BotCommand("operator", "Связаться с оператором"),
        ]
    )


def build_application() -> Application:
    token = settings.telegram_bot_token.strip()
    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN не задан")
    builder = (
        Application.builder()
        .token(token)
        .connect_timeout(30.0)
        .read_timeout(30.0)
        .write_timeout(30.0)
    )
    proxy = telegram_proxy_url()
    if proxy:
        logger.info("Telegram proxy: %s", proxy)
        builder = builder.proxy_url(proxy).get_updates_proxy_url(proxy)
    app = builder.post_init(_post_init).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("operator", operator_cmd))
    app.add_handler(CallbackQueryHandler(callback_escalate, pattern="^escalate$"))
    app.add_handler(MessageHandler(filters.VOICE | filters.AUDIO, handle_voice))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    return app
