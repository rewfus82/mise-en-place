"""Recipe retrieval over a TheMealDB corpus — real dishes used as inspiration
anchors for meal generation.

Kept in a separate `data/recipes.db` from the Coach's ISSN literature so the two
retrieval domains never cross (a protein question shouldn't surface a casserole).
Reuses the same hybrid engine as the Coach: sqlite-vec dense + FTS5 BM25 fused with
RRF, embedded by the same local model2vec model.
"""
from __future__ import annotations

import sqlite3
from functools import lru_cache
from pathlib import Path

from sqlite_vec import serialize_float32

from meal_planner.rag import retriever, store
from meal_planner.rag.embedder import EMBED_DIM

RECIPES_PATH = Path(__file__).resolve().parents[2] / "data" / "recipes.db"


def connect(path: str | Path | None = None) -> sqlite3.Connection:
    return store.connect(path or RECIPES_PATH)


def create_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS recipes (
            id           INTEGER PRIMARY KEY,
            meal_id      TEXT,
            name         TEXT NOT NULL,
            category     TEXT,
            area         TEXT,
            ingredients  TEXT,
            url          TEXT,
            search_text  TEXT NOT NULL
        );
        """
    )
    conn.execute(
        f"CREATE VIRTUAL TABLE IF NOT EXISTS recipes_vec "
        f"USING vec0(recipe_id INTEGER PRIMARY KEY, embedding float[{EMBED_DIM}])"
    )
    conn.execute(
        "CREATE VIRTUAL TABLE IF NOT EXISTS recipes_fts "
        "USING fts5(search_text, content='recipes', content_rowid='id')"
    )
    conn.commit()


def reset(conn: sqlite3.Connection) -> None:
    conn.executescript(
        "DROP TABLE IF EXISTS recipes_fts; DROP TABLE IF EXISTS recipes_vec; DROP TABLE IF EXISTS recipes;"
    )
    conn.commit()
    create_schema(conn)


def insert_recipe(conn: sqlite3.Connection, recipe: dict, embedding) -> int:
    cur = conn.execute(
        "INSERT INTO recipes (meal_id, name, category, area, ingredients, url, search_text) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (
            recipe.get("meal_id"),
            recipe["name"],
            recipe.get("category"),
            recipe.get("area"),
            recipe.get("ingredients"),
            recipe.get("url"),
            recipe["search_text"],
        ),
    )
    rid = cur.lastrowid
    conn.execute(
        "INSERT INTO recipes_vec (recipe_id, embedding) VALUES (?, ?)",
        (rid, serialize_float32(list(embedding))),
    )
    return rid


def rebuild_fts(conn: sqlite3.Connection) -> None:
    conn.execute("INSERT INTO recipes_fts(recipes_fts) VALUES('rebuild')")
    conn.commit()


@lru_cache(maxsize=1)
def _conn() -> sqlite3.Connection:
    return connect()


def retrieve_recipes(
    query: str, *, k: int = 5, pool: int = 20, conn: sqlite3.Connection | None = None
) -> list[dict]:
    """Top-k real recipes for `query`, fused from dense + sparse retrieval."""
    query = (query or "").strip()
    if not query:
        return []
    conn = conn or _conn()

    dense = retriever.dense_ids(conn, query, vec_table="recipes_vec", id_col="recipe_id", pool=pool)
    sparse = retriever.sparse_ids(conn, query, fts_table="recipes_fts", pool=pool)
    fused = retriever._rrf([dense, sparse])
    if not fused:
        return []
    top = sorted(fused, key=lambda rid: fused[rid], reverse=True)[:k]

    placeholders = ",".join("?" * len(top))
    rows = conn.execute(
        f"SELECT id, name, category, area, ingredients, url FROM recipes WHERE id IN ({placeholders})",
        top,
    ).fetchall()
    by_id = {r["id"]: r for r in rows}
    out = []
    for rid in top:
        r = by_id.get(rid)
        if r:
            out.append(dict(r))
    return out


_MEAT_CATEGORIES = {"Beef", "Chicken", "Pork", "Seafood", "Lamb", "Goat"}


def recipe_anchor_block(query: str, *, k: int = 4, restrictions: list[str] | None = None) -> str:
    """A compact prompt block of real recipe ideas to anchor meal generation.

    Best-effort: returns "" if the recipe DB is missing/unreachable, so generation
    never depends on it. For vegan/vegetarian users, meat-category recipes are
    filtered out so the inspiration doesn't contradict the diet.
    """
    veg = any((r or "").lower() in ("vegan", "vegetarian") for r in (restrictions or []))
    try:
        hits = retrieve_recipes(query, k=k * 2 if veg else k)
    except Exception:  # noqa: BLE001 — anchors are a nicety, never fatal
        return ""
    if veg:
        hits = [h for h in hits if h.get("category") not in _MEAT_CATEGORIES]
    hits = hits[:k]
    if not hits:
        return ""

    items = []
    for h in hits:
        ings = h.get("ingredients") or ""
        if len(ings) > 130:
            ings = ings[:130].rsplit(",", 1)[0] + "…"
        descriptor = " ".join(p for p in (h.get("area"), h.get("category")) if p)
        items.append(f"{h['name']} ({descriptor}; uses {ings})")
    listed = "; ".join(items)
    return (
        "Real recipe ideas for inspiration (adapt freely and scale portions to hit "
        f"the macro targets — you need not use them): {listed}."
    )
