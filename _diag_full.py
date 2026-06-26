import sys, io, time
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
from app.services.chat import ask

qs = [
    "Кто согласовывает БП Командировка?",
    "Какие ценности у компании Барс Груп?",
]
for q in qs:
    t = time.time()
    r = ask(q)
    dt = time.time() - t
    print("=== Q:", q)
    print("time=%.1fs conf=%.2f sources=%s needs_op=%s" % (dt, r.confidence, r.sources, r.needs_operator))
    print(r.answer)
    print()
