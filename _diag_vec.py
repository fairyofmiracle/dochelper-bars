import sys, io, math
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
from qdrant_client import QdrantClient
from app.config import settings
from app.rag.embedder import embed_query, embed_texts

c = QdrantClient(url=settings.qdrant_url, check_compatibility=False)
pts, _ = c.scroll(collection_name=settings.qdrant_collection, limit=5, with_vectors=True, with_payload=True)
print("=== stored points ===")
for p in pts:
    v = p.vector
    norm = math.sqrt(sum(x*x for x in v)) if v else 0
    kind = (p.payload or {}).get("kind")
    src = (p.payload or {}).get("source")
    txt = ((p.payload or {}).get("text") or "")[:50].replace(chr(10)," ")
    print("norm=%.4f dim=%s kind=%s src=%s :: %s" % (norm, len(v) if v else 0, kind, src, txt))

print("\n=== query vector ===")
qv = embed_query("Кто согласовывает БП Командировка?")
qn = math.sqrt(sum(x*x for x in qv))
print("query norm=%.4f dim=%d first5=%s" % (qn, len(qv), [round(x,3) for x in qv[:5]]))

# manual cosine between query and stored
print("\n=== manual cosine vs stored ===")
for p in pts:
    v = p.vector
    dot = sum(a*b for a,b in zip(qv, v))
    print("dot=%.4f src=%s" % (dot, (p.payload or {}).get("source")))
