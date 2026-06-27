#!/usr/bin/env bash
# Копирует docx кейса в data/docs (Linux-аналог copy_docs.ps1)
set -euo pipefail
cd "$(dirname "$0")/.."

SRC="${1:-../AO_BARS_GRUP/Additional}"
DST="data/docs"

if [[ ! -d "$SRC" ]]; then
  echo "Не найдена папка: $SRC"
  echo "Использование: $0 [/path/to/AO_BARS_GRUP/Additional]"
  exit 1
fi

mkdir -p "$DST"
cp -v "$SRC"/*.docx "$DST"/
echo
echo "=== Файлы в $DST ==="
ls -lh "$DST"/*.docx

EXPECTED=(Functionalnie.docx Komandirovka.docx newbiePage.docx ReestrMebeli.docx)
for f in "${EXPECTED[@]}"; do
  [[ -f "$DST/$f" ]] || echo "ОТСУТСТВУЕТ: $f"
done

echo
echo "=== Индексация ==="
DATA_ROOT="${DATA_ROOT:-/opt/bars-support-bot-data}" \
HF_HOME="${HF_HOME:-/opt/bars-support-bot-data/huggingface}" \
.venv/bin/python scripts/ingest.py --clear

echo
echo "=== Health ==="
curl -s "http://127.0.0.1:${APP_PORT:-8026}/api/health" | python3 -m json.tool
