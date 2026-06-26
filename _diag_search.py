import sys, io, time
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
from app.rag.search import search, best_confidence

qs = [
    "Как работает фильтр документа?",
    "Кто согласовывает БП Командировка?",
    "Какие ценности у компании Барс Груп?",
    "Какие статусы мебели перечислены в реестре техники?",
    "Что делать в первый рабочий день?",
]
for q in qs:
    t = time.time()
    hits = search(q)
    dt = time.time() - t
    print("Q:", q, "| best=%.3f | %.2fs" % (best_confidence(hits), dt))
    for h in hits:
        print("   score=%.3f src=%s :: %s" % (h.score, h.source, h.text[:90].replace(chr(10), " ")))
    print()
