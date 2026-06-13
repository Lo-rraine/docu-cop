#!/usr/bin/env python3
"""Quick import test."""
import sys
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

try:
    import ingest
    print("[OK] ingest.py imports successfully")
    print(f"  - Embedding model: {ingest.EMBEDDING_MODEL}")
    print(f"  - Max tokens: {ingest.MAX_TOKENS_PER_CHUNK}")
    print(f"  - Embedding dims: {ingest.EMBEDDING_DIMENSIONS}")
except Exception as e:
    print(f"[FAIL] Import failed: {e}")
    import traceback
    traceback.print_exc()
    exit(1)
