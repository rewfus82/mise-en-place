"""Shared pytest fixtures for backend integration tests.

Each test gets an isolated temp calendar.db so tests never touch real data.
We patch backend.database._DB_PATH (read at call time by get_db) and create the
schema against it, then hand back a FastAPI TestClient.
"""
import sqlite3

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(tmp_path, monkeypatch):
    import backend.database as database

    db_file = tmp_path / "calendar.db"
    monkeypatch.setattr(database, "_DB_PATH", db_file)
    database.create_tables()

    # Import app lazily so it picks up the patched path via get_db.
    from backend.main import app

    # No `with` — we skip startup events (graph pre-warm) and rely on the
    # schema we created above. get_db reads the patched module global per request.
    yield TestClient(app)


@pytest.fixture
def seed_eaten_day(tmp_path):
    """Return a helper that inserts a meal_day with one eaten meal at given calories."""
    db_file = tmp_path / "calendar.db"

    def _seed(date: str, calories: float = 2000.0, eaten: bool = True):
        conn = sqlite3.connect(str(db_file))
        try:
            conn.execute(
                "INSERT OR IGNORE INTO meal_days (date, status) VALUES (?, 'completed')",
                (date,),
            )
            day_id = conn.execute(
                "SELECT id FROM meal_days WHERE date = ?", (date,)
            ).fetchone()[0]
            conn.execute(
                """INSERT INTO day_meals (day_id, meal_number, recipe_name,
                       calories_est, eaten)
                   VALUES (?, 1, 'Test Meal', ?, ?)""",
                (day_id, calories, 1 if eaten else 0),
            )
            conn.commit()
        finally:
            conn.close()

    return _seed
