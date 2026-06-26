import sys, io, math
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
from app.rag.indexer import index_all, get_client
from app.config import settings

print("Reindexing (clear=True)...")
stats = index_all(clear=True)
print("files=%s chunks=%s images=%s" % (stats.files, stats.chunks, stats.images))
if stats.errors:
    print("errors:", stats.errors)

c = get_client()
pts, _ = c.scroll(collection_name=settings.qdrant_collection, limit=5, with_vectors=True)
print("\n=== verify norms ===")
for p in pts:
    v = p.vector
    norm = math.sqrt(sum(x*x for x in v)) if v else 0
    print("norm=%.4f dim=%s" % (norm, len(v) if v else 0))
