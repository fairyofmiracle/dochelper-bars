#!/usr/bin/env python3
"""CLI: индексация документов в Qdrant."""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.rag.indexer import index_all


def main():
    p = argparse.ArgumentParser(description="Index docs into Qdrant")
    p.add_argument("--clear", action="store_true", help="Recreate collection")
    args = p.parse_args()
    stats = index_all(clear=args.clear)
    print(stats)


if __name__ == "__main__":
    main()
