import json
import sqlite3
from pathlib import Path

from fastmcp import FastMCP

DB_PATH = Path(__file__).parent.parent.parent / "data" / "pantry.db"

mcp = FastMCP("pantry-server")


def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS pantry (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            item TEXT NOT NULL,
            quantity TEXT DEFAULT 'unknown',
            category TEXT DEFAULT 'other'
        )
    """)
    conn.commit()
    return conn


@mcp.tool()
def get_inventory() -> list[dict]:
    """Return all items currently in the pantry."""
    with _get_conn() as conn:
        rows = conn.execute("SELECT id, item, quantity, category FROM pantry").fetchall()
    return [{"id": r[0], "item": r[1], "quantity": r[2], "category": r[3]} for r in rows]


@mcp.tool()
def add_items(items: list[dict]) -> dict:
    """
    Add parsed food items to the pantry.

    Each item must have: item (str), quantity (str), category (str).
    Skips duplicates by item name.
    """
    added = []
    skipped = []

    with _get_conn() as conn:
        existing = {
            r[0].lower()
            for r in conn.execute("SELECT item FROM pantry").fetchall()
        }
        for entry in items:
            name = entry.get("item", "").strip()
            if not name:
                continue
            if name.lower() in existing:
                skipped.append(name)
                continue
            conn.execute(
                "INSERT INTO pantry (item, quantity, category) VALUES (?, ?, ?)",
                (name, entry.get("quantity", "unknown"), entry.get("category", "other")),
            )
            added.append(name)
        conn.commit()

    return {"added": added, "skipped": skipped}


@mcp.tool()
def update_quantity(item_name: str, quantity: str) -> dict:
    """Set the quantity for an existing pantry item (case-insensitive)."""
    with _get_conn() as conn:
        cur = conn.execute(
            "UPDATE pantry SET quantity = ? WHERE LOWER(item) = LOWER(?)",
            (quantity, item_name),
        )
        conn.commit()
    return {"updated": cur.rowcount > 0}


@mcp.tool()
def remove_items(item_names: list[str]) -> dict:
    """Remove items from the pantry by name (case-insensitive)."""
    removed = []
    not_found = []

    with _get_conn() as conn:
        for name in item_names:
            cursor = conn.execute(
                "DELETE FROM pantry WHERE LOWER(item) = LOWER(?)", (name,)
            )
            if cursor.rowcount > 0:
                removed.append(name)
            else:
                not_found.append(name)
        conn.commit()

    return {"removed": removed, "not_found": not_found}


@mcp.tool()
def check_item(item_name: str) -> bool:
    """Check whether a specific item exists in the pantry (case-insensitive)."""
    with _get_conn() as conn:
        row = conn.execute(
            "SELECT 1 FROM pantry WHERE LOWER(item) = LOWER(?)", (item_name,)
        ).fetchone()
    return row is not None


@mcp.tool()
def clear_inventory() -> dict:
    """Remove all items from the pantry. Use at the start of a new session."""
    with _get_conn() as conn:
        conn.execute("DELETE FROM pantry")
        conn.commit()
    return {"cleared": True}


if __name__ == "__main__":
    mcp.run()
