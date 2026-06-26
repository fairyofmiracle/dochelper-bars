#!/usr/bin/env python3
"""Прогон тест-кейсов из брифа через /api/chat."""
from __future__ import annotations

import json
import sys
import time
import urllib.request

CASES = [
    "Как выглядит интерфейс БО ? Где найти в нем производственный календарь?",
    "Как работает фильтр документа? Опиши шаг действий для настройки фильтра",
    'Почему не работает фильтр в БО "!> 200" ?',
    "Мне прислали ссылку https://bo.bars.group//#mainmenuitemclick&bars_office&byudjeetsdelki&id&=&6DF3B1B8B2F249368E5F9749С10CD2AC что с ней делать ?",
    "Мне необходимо узнать, кто согласовывает БП Командировки?",
    "Мне не отвечает офис-менеджер, какой у него график работы?",
    "Почему не могу выбрать сделку 2334-26, у которой статус воронки 30% в поле Номер пресейла?",
    "Смогу ли я запустить БП Командировка, если не заложил средств в бюджет сделки?",
    "Какие могут быть условия в выборе следующего согласующего лица БП Командировка?",
    "Какие функциональные кнопки есть в реестре мебели? Как они выглядят?",
    "Опиши поэтапно как в БО добавить запись в реестр техники?",
    "Какие статусы мебели перечислены в реестре техники?",
    "Какие ценности у компании Барс Груп ? Можешь подробно рассказать про каждую из них?",
    "Что делать в первый рабочий день?",
    "Какие бонусы и корпоративные скидки есть в компании? Есть ли скидка в s7 airlines и какой размер скидки?",
    "У меня проблема с техникой, к кому обратиться?",
    "Через месяц отпуск, что делать?",
]

BASE = "http://127.0.0.1:8026/api/chat"


def ask(q: str) -> dict:
    body = json.dumps({"message": q, "session_id": "brief-test"}, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(BASE, data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=90) as r:
        return json.loads(r.read().decode())


def main() -> int:
    ok = fail = low = 0
    for i, q in enumerate(CASES, 1):
        t = time.time()
        try:
            r = ask(q)
            dt = time.time() - t
            conf = r["confidence"]
            auto = not r["needs_operator"]
            if auto:
                ok += 1
                mark = "OK"
            elif conf < 0.45:
                low += 1
                mark = "LOW"
            else:
                fail += 1
                mark = "??"
            src = (r.get("sources") or ["—"])[0]
            print(f"[{i:02d}] {mark} {dt:4.1f}s conf={conf:.2f} src={src}")
            print(f"     Q: {q[:70]}{'…' if len(q) > 70 else ''}")
            print(f"     A: {r['answer'][:120].replace(chr(10), ' ')}…")
            print()
        except Exception as exc:
            print(f"[{i:02d}] ERR {exc}")
            fail += 1
    total = len(CASES)
    print(f"Итого: авто={ok}/{total} ({ok/total*100:.0f}%) | low_conf={low} | err={fail}")
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
