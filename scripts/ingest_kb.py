"""Build the knowledge base from data/kb_sources/*.md into data/knowledge.db.

Offline, reproducible, idempotent: a full rebuild (DROP + recreate) so the
committed knowledge.db is always a pure function of the source markdown. Run:

    python -m scripts.ingest_kb

The resulting knowledge.db is committed to the repo so the deployed app needs no
ingestion step and no API key at runtime.
"""
from __future__ import annotations

import sys
from pathlib import Path

# Allow `python scripts/ingest_kb.py` as well as `-m scripts.ingest_kb`.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from meal_planner.rag import store  # noqa: E402
from meal_planner.rag.chunking import chunk_document  # noqa: E402
from meal_planner.rag.embedder import embed  # noqa: E402

KB_SOURCES = Path(__file__).resolve().parents[1] / "data" / "kb_sources"


def main() -> int:
    sources = sorted(KB_SOURCES.glob("*.md"))
    if not sources:
        print(f"No source documents found in {KB_SOURCES}")
        return 1

    # Parse + chunk every source first so we can batch-embed in one pass.
    all_chunks = []
    for path in sources:
        raw = path.read_text(encoding="utf-8")
        doc_chunks = chunk_document(raw, fallback_id=path.stem)
        all_chunks.extend(doc_chunks)
        print(f"  {path.name}: {len(doc_chunks)} chunks")

    if not all_chunks:
        print("Sources contained no chunkable text.")
        return 1

    print(f"Embedding {len(all_chunks)} chunks...")
    vectors = embed([c.text for c in all_chunks])

    conn = store.connect()
    store.reset(conn)
    for chunk, vec in zip(all_chunks, vectors):
        store.insert_chunk(conn, chunk, vec)
    conn.commit()
    store.rebuild_fts(conn)

    sources_n = len({c.source_id for c in all_chunks})
    print(
        f"Built {store.KB_PATH} — {len(all_chunks)} chunks "
        f"from {sources_n} sources."
    )
    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
