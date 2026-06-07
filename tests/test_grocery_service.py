"""Tests for the grocery deficit logic (parsing, matching, deficit math)."""
import sqlite3

import pytest

from backend.services import grocery_service as gs


class TestHelpers:
    @pytest.mark.parametrize("raw,expected", [
        ("2", 2.0), ("1.5", 1.5), ("1/4", 0.25), ("1 1/2", 1.5),
        ("some", None), ("", None), (None, None),
    ])
    def test_parse_amount(self, raw, expected):
        assert gs._parse_amount(raw) == expected

    def test_norm_name_strips_parentheticals_and_plurals(self):
        assert gs._norm_name("rice (cooked)") == "rice"
        assert gs._norm_name("Chicken Breasts") == "chicken breast"
        assert gs._norm_name("eggs") == "egg"

    def test_norm_unit_singularizes_first_word(self):
        assert gs._norm_unit("cups chopped") == "cup"
        assert gs._norm_unit("lbs") == "lb"
        assert gs._norm_unit("") is None

    def test_parse_numeric_combined_string(self):
        assert gs._parse_numeric("10 lb") == (10.0, "lb")
        assert gs._parse_numeric("1/2 cup") == (0.5, "cup")

    def test_to_grams(self):
        assert gs._to_grams(2, "lb") == pytest.approx(907.184)
        assert gs._to_grams(1, "kg") == 1000
        assert gs._to_grams(2, "whole") is None  # count units aren't mass


def _make_db(meal_ingredients, pantry, monkeypatch):
    """Build an in-memory calendar DB with one planned future day + ingredients,
    and stub the pantry inventory."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE meal_days (id INTEGER PRIMARY KEY, date TEXT, status TEXT);
        CREATE TABLE day_meals (id INTEGER PRIMARY KEY, day_id INTEGER);
        CREATE TABLE meal_ingredients (
            id INTEGER PRIMARY KEY, meal_id INTEGER,
            item TEXT, quantity TEXT, unit TEXT, quantity_type TEXT
        );
        CREATE TABLE grocery_overrides (item TEXT PRIMARY KEY, ignored INTEGER DEFAULT 1);
        """
    )
    conn.execute("INSERT INTO meal_days (id, date, status) VALUES (1, '2099-01-01', 'planned')")
    conn.execute("INSERT INTO day_meals (id, day_id) VALUES (1, 1)")
    for item, qty, unit, qtype in meal_ingredients:
        conn.execute(
            "INSERT INTO meal_ingredients (meal_id, item, quantity, unit, quantity_type) VALUES (1,?,?,?,?)",
            (item, qty, unit, qtype),
        )
    conn.commit()
    monkeypatch.setattr(gs, "get_inventory", lambda: pantry)
    return conn


class TestComputeDeficit:
    def test_trace_ingredients_excluded(self, monkeypatch):
        conn = _make_db(
            [("salt", "1", "tsp", "trace")],
            pantry=[],
            monkeypatch=monkeypatch,
        )
        assert gs.compute_deficit(conn) == []

    def test_owned_non_comparable_item_suppressed(self, monkeypatch):
        # Need 1/2 whole onion; pantry has 5 lb onion. Different dimensions but owned.
        conn = _make_db(
            [("onion", "1/2", "whole", "exact")],
            pantry=[{"item": "onion", "quantity": "5 lb"}],
            monkeypatch=monkeypatch,
        )
        assert gs.compute_deficit(conn) == []

    def test_missing_item_listed_with_amount(self, monkeypatch):
        conn = _make_db(
            [("sesame oil", "1", "tsp", "exact")],
            pantry=[],
            monkeypatch=monkeypatch,
        )
        res = gs.compute_deficit(conn)
        assert len(res) == 1
        assert res[0]["ingredient"] == "sesame oil"
        assert res[0]["deficit_calculable"] is True

    def test_name_normalization_matches_pantry(self, monkeypatch):
        # 'rice (cooked)' should match pantry 'rice' and be covered (lots on hand).
        conn = _make_db(
            [("rice (cooked)", "1", "cup", "exact")],
            pantry=[{"item": "rice", "quantity": "10 lb"}],
            monkeypatch=monkeypatch,
        )
        assert gs.compute_deficit(conn) == []

    def test_real_deficit_when_short(self, monkeypatch):
        # Need 10 lb chicken, have 2 lb -> 8 lb deficit.
        conn = _make_db(
            [("chicken breast", "10", "lb", "exact")],
            pantry=[{"item": "chicken breast", "quantity": "2 lb"}],
            monkeypatch=monkeypatch,
        )
        res = gs.compute_deficit(conn)
        assert len(res) == 1
        assert float(res[0]["quantity_needed"]) == pytest.approx(8.0, abs=0.1)
        assert res[0]["unit"] == "lb"

    def test_accumulates_across_meals(self, monkeypatch):
        conn = _make_db(
            [("olive oil", "2", "tbsp", "exact"), ("olive oil", "2", "tbsp", "exact")],
            pantry=[],
            monkeypatch=monkeypatch,
        )
        res = gs.compute_deficit(conn)
        assert len(res) == 1
        assert float(res[0]["quantity_needed"]) == pytest.approx(4.0, abs=0.01)

    def test_ignored_items_excluded(self, monkeypatch):
        conn = _make_db(
            [("sesame oil", "1", "tsp", "exact")],
            pantry=[],
            monkeypatch=monkeypatch,
        )
        conn.execute("INSERT INTO grocery_overrides (item, ignored) VALUES ('sesame oil', 1)")
        conn.commit()
        assert gs.compute_deficit(conn) == []
