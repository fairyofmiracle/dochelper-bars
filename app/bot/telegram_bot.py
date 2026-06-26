"""Telegram-бот DocHelper Барс."""
from __future__ import annotations

import asyncio
import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ChatAction
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes, MessageHandler, filters

from app.config import settings
from app.services.chat_async import ask_async
from app.services.escalation import notify_support
from app.services.session import append_message

logger = logging.getLogger(__name__)

STATUS_LLM = "✍️ Формирую ответ..."

WELCOME = (
    "Здравствуйте! Я {name} 👋\n\n"
    "👩‍💻 Команда: one_commit\n"
    "🏆 Хакатон «Королева Кода» — конференция ТАТАР САН 2026, Казань\n"
    "🏢 Кейс: АО «Барс Групп»\n\n"
    "Я — AI-агент первой линии поддержки. Ищу ответы по всей базе "
    "корпоративных документов и указываю источник.\n\n"
    "Просто напишите ваш вопрос текстом в этот чат."
)

_user_locks: dict[str, asyncio.Lock] = {}


def operator_inline_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton("Переключить на оператора", callback_data="escalate")]]
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


async def _send_result(
    update: Update,
    text: str,
    needs_operator: bool,
    *,
    edit_message=None,
) -> None:
    text = _trim_text(text)
    inline = operator_inline_keyboard() if needs_operator else None

    if edit_message is not None:
        try:
            await edit_message.edit_text(text, reply_markup=inline)
            return
        except Exception:
            logger.debug("edit_text failed, sending new message", exc_info=True)

    message = update.effective_message
    if not message:
        return
    await message.reply_text(text, reply_markup=inline)


async def _process_question(update: Update, question: str) -> None:
    sid = _session_id(update)
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
        finally:
            stop_typing.set()
            if typing_task:
                await typing_task

        append_message(sid, "assistant", result.answer)

        if result.escalated:
            user = update.effective_user
            label = user.full_name if user else "unknown"
            await notify_support(sid, label, question)

        await _send_result(
            update,
            result.answer,
            result.needs_operator or result.escalated,
            edit_message=status_msg,
        )


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(WELCOME.format(name=settings.bot_name))


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Напишите вопрос текстом — поиск по всей базе документов.\n"
        "Команды: /start — приветствие, /operator — оператор",
    )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.message.text:
        return
    await _process_question(update, update.message.text.strip())


async def operator_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    sid = _session_id(update)
    async with _user_lock(sid):
        append_message(sid, "user", "/operator")
        result = await ask_async("оператор", force_escalate=True)
        user = update.effective_user
        await notify_support(sid, user.full_name if user else "unknown")
        await _send_result(update, result.answer, True)


async def callback_escalate(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    sid = _session_id(update)
    async with _user_lock(sid):
        result = await ask_async("оператор", force_escalate=True)
        user = update.effective_user
        await notify_support(sid, user.full_name if user else "unknown")
        await _send_result(update, result.answer, True)


def build_application() -> Application:
    token = settings.telegram_bot_token.strip()
    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN не задан")
    app = Application.builder().token(token).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("operator", operator_cmd))
    app.add_handler(CallbackQueryHandler(callback_escalate, pattern="^escalate$"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    return app
