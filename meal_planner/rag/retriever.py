"""Hybrid retrieval: dense (sqlite-vec) + sparse (FTS5 BM25) fused with Reciprocal
Rank Fusion.

Why hybrid: dense vectors capture paraphrase/semantic matches ("how much protein
to build muscle" -> a passage about grams per kilogram), while BM25 nails exact
terminology and rare tokens ("beta-alanine", "CYP1A2"). Fusing the two ranked
lists with RRF gives better top-k than either alone, with no model to train and no
score-normalization headache — RRF combines *ranks*, not raw scores, so the
incomparable vec-distance and BM25 scales never have to be reconciled.
"""
from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass
from functools import lru_cache

from sqlite_vec import serialize_float32

from meal_planner.rag import store
from meal_planner.rag.embedder import embed_one

# RRF damping constant. 60 is the value from the original Cormack et al. paper and
# the de-facto default; it keeps any single list from dominating the fusion.
_RRF_K = 60


@dataclass
class RetrievedChunk:
    chunk_id: int
    source_id: str
    title: str | None
    authors: str | None
    year: int | None
    journal: str | None
    doi: str | None
    url: str | None
    license: str | None
    section: str | None
    text: str
    score: float  # fused RRF score (higher = better)

    def citation(self) -> str:
        """Short human-readable citation, e.g. 'Jäger R, et al. (2017)'."""
        author = (self.authors or "").split(",")[0].strip()
        if author and self.authors and "," in self.authors:
            author = f"{author}, et al."
        year = f" ({self.year})" if self.year else ""
        return f"{author or self.title or self.source_id}{year}".strip()


@lru_cache(maxsize=1)
def _conn() -> sqlite3.Connection:
    """Process-wide read connection to the knowledge base (opened lazily)."""
    return store.connect()


def dense_ids(conn: sqlite3.Connection, query: str, *, vec_table: str, id_col: str, pool: int) -> list[int]:
    """Top-`pool` row ids from a sqlite-vec table by vector distance, best first.

    Generic over the table/id column so the same dense search serves both the
    knowledge base (chunks) and the recipe corpus (recipes).
    """
    qv = serialize_float32(list(embed_one(query)))
    rows = conn.execute(
        f"SELECT {id_col} FROM {vec_table} WHERE embedding MATCH ? ORDER BY distance LIMIT ?",
        (qv, pool),
    ).fetchall()
    return [r[0] for r in rows]


def sparse_ids(conn: sqlite3.Connection, query: str, *, fts_table: str, pool: int) -> list[int]:
    """Top-`pool` row ids from an FTS5 table by BM25, best first. Empty query -> []."""
    match = _fts_query(query)
    if not match:
        return []
    rows = conn.execute(
        f"SELECT rowid FROM {fts_table} WHERE {fts_table} MATCH ? ORDER BY bm25({fts_table}) LIMIT ?",
        (match, pool),
    ).fetchall()
    return [r[0] for r in rows]


def _dense(conn: sqlite3.Connection, query: str, pool: int) -> list[int]:
    """Knowledge-base dense search (used directly by the eval harness)."""
    return dense_ids(conn, query, vec_table="chunks_vec", id_col="chunk_id", pool=pool)


def _fts_query(query: str) -> str:
    """Turn free text into a safe FTS5 MATCH expression.

    Raw user text can contain characters that are FTS5 operators (`?`, `"`, `:`,
    `*`), so we extract bare word tokens and OR them as quoted terms. OR semantics
    suit retrieval — BM25 still ranks documents matching more/rarer terms higher.
    """
    tokens = re.findall(r"[A-Za-z0-9]+", query.lower())
    return " OR ".join(f'"{t}"' for t in tokens)


def _sparse(conn: sqlite3.Connection, query: str, pool: int) -> list[int]:
    """Knowledge-base sparse search (used directly by the eval harness)."""
    return sparse_ids(conn, query, fts_table="chunks_fts", pool=pool)


def _rrf(ranked_lists: list[list[int]]) -> dict[int, float]:
    """Reciprocal Rank Fusion over several best-first id lists -> {id: score}."""
    scores: dict[int, float] = {}
    for ids in ranked_lists:
        for rank, cid in enumerate(ids, start=1):
            scores[cid] = scores.get(cid, 0.0) + 1.0 / (_RRF_K + rank)
    return scores


def retrieve(
    query: str,
    *,
    k: int = 5,
    pool: int = 20,
    conn: sqlite3.Connection | None = None,
) -> list[RetrievedChunk]:
    """Return the top-`k` chunks for `query`, fused from dense + sparse retrieval.

    `pool` is how deep each retriever goes before fusion; `k` is how many fused
    results come back. Hydrates full citation metadata for the survivors only.
    """
    query = (query or "").strip()
    if not query:
        return []
    conn = conn or _conn()

    dense_ids = _dense(conn, query, pool)
    sparse_ids = _sparse(conn, query, pool)
    fused = _rrf([dense_ids, sparse_ids])
    if not fused:
        return []

    top_ids = sorted(fused, key=lambda cid: fused[cid], reverse=True)[:k]
    placeholders = ",".join("?" * len(top_ids))
    rows = conn.execute(
        f"SELECT id, source_id, title, authors, year, journal, doi, url, "
        f"license, section, text FROM chunks WHERE id IN ({placeholders})",
        top_ids,
    ).fetchall()
    by_id = {r["id"]: r for r in rows}

    results: list[RetrievedChunk] = []
    for cid in top_ids:  # preserve fused order
        r = by_id.get(cid)
        if r is None:
            continue
        results.append(
            RetrievedChunk(
                chunk_id=cid,
                source_id=r["source_id"],
                title=r["title"],
                authors=r["authors"],
                year=r["year"],
                journal=r["journal"],
                doi=r["doi"],
                url=r["url"],
                license=r["license"],
                section=r["section"],
                text=r["text"],
                score=fused[cid],
            )
        )
    return results
