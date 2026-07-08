#!/usr/bin/env python3
"""Recalculate average response time from brief test cases."""
from __future__ import annotations

import json
import statistics
import time
import urllib.request

from test_brief_cases import CASES, BASE


def ask(q: str, session_id: str) -> dict:
    body = json.dumps({"message": q, "session_id": session_id}, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(BASE, data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=90) as r:
        return json.loads(r.read().decode())


def main() -> None:
    times: list[float] = []
    auto_times: list[float] = []
    for i, q in enumerate(CASES, 1):
        t0 = time.time()
        r = ask(q, f"brief-timing-{i}")
        dt = time.time() - t0
        times.append(dt)
        auto = not r.get("needs_operator")
        if auto and not r.get("rate_limited"):
            auto_times.append(dt)
        flag = "auto" if auto else "esc"
        if r.get("rate_limited"):
            flag += "+rate"
        print(f"[{i:02d}] {dt:4.2f}s {flag}")

    print()
    print(f"Все {len(times)} кейсов:  avg={statistics.mean(times):.2f}s  median={statistics.median(times):.2f}s")
    if auto_times:
        print(
            f"Авто {len(auto_times)} кейсов: avg={statistics.mean(auto_times):.2f}s  "
            f"median={statistics.median(auto_times):.2f}s"
        )


if __name__ == "__main__":
    main()
