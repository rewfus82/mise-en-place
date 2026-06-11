"""SQLite knowledge store: a `chunks` table plus a sqlite-vec dense index and an
FTS5 sparse index, all in one file (`data/knowledge.db`).

Keeping dense + sparse in the same SQLite file is the whole reason this fits a
free-tier box: no separate vector service, no extra process, and hybrid search is
two queries against one connection.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import sqlite_vec
from sqlite_vec import serialize_float32

from meal_planner.rag.embedder import EMBED_DIM

KB_PATH = Path(__file__).resolve().parents[2] / "data" / "knowledge.db"


def connect(path: str | Path | None = None) -> sqlite3.Connection:
    """Open a connection with the sqlite-vec extension loaded.

    Extension loading must be toggled on around the load; some stdlib sqlite3
    builds disable it by default. Linux (Render) and this Windows build both
    support it — verified at setup time.
    """
    p = Path(path) if path else KB_PATH
    p.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(p), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.enable_load_extension(True)
    sqlite_vec.load(conn)
    conn.enable_load_extension(False)
    return conn


def create_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS chunks (
            id        INTEGER PRIMARY KEY,
            source_id TEXT NOT NULL,
            title     TEXT,
            authors   TEXT,
            year      INTEGER,
            journal   TEXT,
            doi       TEXT,
            url       TEXT,
            license   TEXT,
            section   TEXT,
            ord       INTEGER,
            text      TEXT NOT NULL
        );
        """
    )
    # Dense index: one row per chunk, keyed by chunks.id.
    conn.execute(
        f"CREATE VIRTUAL TABLE IF NOT EXISTS chunks_vec "
        f"USING vec0(chunk_id INTEGER PRIMARY KEY, embedding float[{EMBED_DIM}])"
    )
    # Sparse index: external-content FTS5 mirrors chunks.text (content_rowid=id).
    conn.execute(
        "CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts "
        "USING fts5(text, content='chunks', content_rowid='id')"
    )
    conn.commit()


def reset(conn: sqlite3.Connection) -> None:
    """Drop everything for a clean, reproducible rebuild."""
    conn.executescript(
        """
        DROP TABLE IF EXISTS chunks_fts;
        DROP TABLE IF EXISTS chunks_vec;
        DROP TABLE IF EXISTS chunks;
        """
    )
    conn.commit()
    create_schema(conn)


def insert_chunk(conn: sqlite3.Connection, chunk, embedding) -> int:
    """Insert one chunk row + its dense vector. Returns the chunk id."""
    cur = conn.execute(
        """
        INSERT INTO chunks (source_id, title, authors, year, journal, doi, url,
                            license, section, ord, text)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            chunk.source_id,
            chunk.meta.get("title"),
            chunk.meta.get("authors"),
            chunk.meta.get("year"),
            chunk.meta.get("journal"),
            chunk.meta.get("doi"),
            chunk.meta.get("url"),
            chunk.meta.get("license"),
            chunk.section,
            chunk.ord,
            chunk.text,
        ),
    )
    chunk_id = cur.lastrowid
    conn.execute(
        "INSERT INTO chunks_vec (chunk_id, embedding) VALUES (?, ?)",
        (chunk_id, serialize_float32(list(embedding))),
    )
    return chunk_id


def rebuild_fts(conn: sqlite3.Connection) -> None:
    """Populate the external-content FTS5 index from the chunks table."""
    conn.execute("INSERT INTO chunks_fts(chunks_fts) VALUES('rebuild')")
    conn.commit()
