#!/usr/bin/env bash
# После копирования docx в data/docs — полная переиндексация и отчёт.
set -euo pipefail
cd "$(dirname "$0")/.."

DOCS_DIR="data/docs"
EXPECTED=(Functionalnie.docx Komandirovka.docx newbiePage.docx ReestrMebeli.docx)

echo "=== Документы в $DOCS_DIR ==="
ls -lh "$DOCS_DIR"/*.docx 2>/dev/null || { echo "Нет docx! Скопируйте файлы в $DOCS_DIR"; exit 1; }

missing=0
for f in "${EXPECTED[@]}"; do
  if [[ ! -f "$DOCS_DIR/$f" ]]; then
    echo "ОТСУТСТВУЕТ: $f"
    missing=1
  fi
done
[[ "$missing" -eq 0 ]] || echo "Предупреждение: не все 4 файла кейса на месте"

echo
echo "=== Индексация ==="
docker exec bars_support_bot-app-1 python scripts/ingest.py --clear

echo
echo "=== Health ==="
curl -s http://localhost:8026/api/health | python3 -m json.tool

echo
echo "=== Qdrant ==="
curl -s "http://localhost:6333/collections/bars_docs" | python3 -c "
import sys, json
d = json.load(sys.stdin)['result']
print('points_count:', d['points_count'])
print('vector_size:', d['config']['params']['vectors']['size'])
"
