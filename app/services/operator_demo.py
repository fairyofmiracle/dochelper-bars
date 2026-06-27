"""Демо-обращения для панели оператора (закрытые диалоги)."""
from __future__ import annotations

import logging
import time

from app.services.escalation_queue import enqueue, resolve
from app.services.session import append_message, get_history

logger = logging.getLogger(__name__)

DEMO_FLAG = "demo:operator_seeded"

_DEMO_CHATS: tuple[dict, ...] = (
    {
        "session_id": "demo-tg-anna",
        "user_label": "Анна · Telegram",
        "question": "Как работает фильтр документа?",
        "age_hours": 5,
        "messages": [
            ("user", "Как работает фильтр документа?"),
            (
                "assistant",
                "Фильтр документа — это окно, где можно отобрать записи по полям. "
                "Настроили условия → нажали «Применить». Сохранённый фильтр можно выбрать позже "
                "через «Выбор сохранённого фильтра».\n\n"
                "Если нужно — могу подсказать подробнее по конкретному полю.",
            ),
            ("user", "А как сохранить фильтр? Не вижу кнопку"),
            (
                "assistant",
                "К сожалению, я пока не нашёл точного ответа в документации.\n\n"
                "Могу переключить Вас на оператора — он продолжит с учётом истории диалога.",
            ),
            ("user", "Переключить на оператора"),
            (
                "assistant",
                "Понял, подключаю специалиста поддержки — он уже видит нашу переписку и скоро ответит.",
            ),
            (
                "operator",
                "Здравствуйте, Анна! Подключилась к диалогу.\n\n"
                "Чтобы сохранить фильтр: в редакторе фильтра задайте условия, "
                "нажмите «Применить», затем в том же окне — «Сохранить» и введите название. "
                "Потом фильтр появится в «Выбор сохранённого фильтра».\n\n"
                "Если кнопки не видно — проверьте, что фильтр уже применён хотя бы раз. "
                "Напишите, если что-то не получится — помогу.",
            ),
            ("user", "Спасибо, нашла! Всё работает"),
            ("operator", "Отлично, рада была помочь! Хорошего дня 🙂"),
        ],
    },
    {
        "session_id": "demo-web-ivan",
        "user_label": "Иван · Web",
        "question": "Кто согласовывает БП Командировка?",
        "age_hours": 28,
        "messages": [
            ("user", "Кто согласовывает БП Командировка?"),
            (
                "assistant",
                "По документу «Komandirovka.docx» маршрут такой: сначала непосредственный руководитель, "
                "затем финансовый контролёр и HR. Точный список ролей зависит от суммы и направления.\n\n"
                "Если нужны имена конкретных согласующих в вашем подразделении — лучше уточнить у оператора.",
            ),
            ("user", "оператор"),
            (
                "assistant",
                "Понял, подключаю специалиста поддержки — он уже видит нашу переписку и скоро ответит.",
            ),
            (
                "operator",
                "Иван, добрый день!\n\n"
                "Для стандартной командировки в вашем кейсе цепочка такая:\n"
                "1. Руководитель подразделения\n"
                "2. Бухгалтерия (лимит расходов)\n"
                "3. HR (оформление приказа)\n\n"
                "Если сумма выше порога — добавляется финансовый директор. "
                "Подробная схема — в «Komandirovka.docx», раздел «Маршрут согласования».",
            ),
            ("user", "Понял, спасибо"),
            ("operator", "Обращение закрыто. Обращайтесь, если появятся вопросы!"),
        ],
    },
    {
        "session_id": "demo-tg-max",
        "user_label": "Максим · Telegram",
        "question": "Что делать в первый рабочий день?",
        "age_hours": 72,
        "messages": [
            ("user", "Что делать в первый рабочий день?"),
            (
                "assistant",
                "В первый день обычно: получить пропуск, настроить рабочее место, "
                "познакомиться с наставником и пройти вводный инструктаж.\n\n"
                "Подробный чек-лист — в документе «newbiePage.docx».",
            ),
            ("user", "А где взять доступ к БАРС-Офис?"),
            (
                "assistant",
                "К сожалению, я пока не нашёл точного ответа в документации.\n\n"
                "Могу переключить Вас на оператора — он продолжит с учётом истории диалога.",
            ),
            ("user", "оператор"),
            (
                "operator",
                "Максим, привет! 👋\n\n"
                "Доступ к БАРС-Офис оформляет IT через заявку в ServiceDesk — "
                "обычно наставник подаёт её в ваш первый день. "
                "Логин приходит на корпоративную почту в течение пары часов.\n\n"
                "Пока ждёте — можно пройти блок «Знакомство с компанией» на портале новичка.",
            ),
            ("user", "Ок, наставник уже оформил"),
            ("operator", "Супер! Тогда после входа загляните в раздел «Мои задачи» — там будут первые поручения."),
        ],
    },
)


def _already_seeded() -> bool:
    from redis import Redis

    from app.config import settings
    from app.services.escalation_queue import _ping_redis

    if not _ping_redis():
        return any(get_history(d["session_id"]) for d in _DEMO_CHATS)

    try:
        return bool(Redis.from_url(settings.redis_url, decode_responses=True).get(DEMO_FLAG))
    except Exception:
        return False


def seed_demo_sessions(force: bool = False) -> None:
    """Создаёт три закрытых демо-диалога для панели оператора."""
    if not force and _already_seeded():
        return

    from app.services.session import clear_session

    for chat in _DEMO_CHATS:
        clear_session(chat["session_id"])
        _remove_queue_item(chat["session_id"])

    now = time.time()
    for chat in _DEMO_CHATS:
        sid = chat["session_id"]
        for role, content in chat["messages"]:
            append_message(sid, role, content)
        enqueue(sid, chat["user_label"], chat["question"])
        resolve(sid)
        _patch_ts(sid, now - chat["age_hours"] * 3600)

    from redis import Redis

    from app.config import settings
    from app.services.escalation_queue import _ping_redis

    if _ping_redis():
        try:
            Redis.from_url(settings.redis_url, decode_responses=True).set(DEMO_FLAG, "1")
        except Exception as exc:
            logger.debug("demo flag not set: %s", exc)

    logger.info("Operator demo sessions seeded (%d chats)", len(_DEMO_CHATS))


def _remove_queue_item(session_id: str) -> None:
    import json

    from redis import Redis

    from app.config import settings
    from app.services.escalation_queue import QUEUE_KEY, _mem_queue, _ping_redis

    if _ping_redis():
        try:
            Redis.from_url(settings.redis_url, decode_responses=True).hdel(QUEUE_KEY, session_id)
        except Exception:
            pass
    _mem_queue[:] = [row for row in _mem_queue if row["session_id"] != session_id]


def _patch_ts(session_id: str, ts: float) -> None:
    import json

    from redis import Redis

    from app.config import settings
    from app.services.escalation_queue import QUEUE_KEY, _ping_redis

    if not _ping_redis():
        return
    try:
        r = Redis.from_url(settings.redis_url, decode_responses=True)
        raw = r.hget(QUEUE_KEY, session_id)
        if raw:
            item = json.loads(raw)
            item["ts"] = ts
            r.hset(QUEUE_KEY, session_id, json.dumps(item, ensure_ascii=False))
    except Exception:
        pass
