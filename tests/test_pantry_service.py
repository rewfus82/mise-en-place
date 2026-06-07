"""Tests for pantry depletion on End Day (compute_depletion)."""
import sqlite3

import pytest

from backend.services import pantry_service as ps


def _make_db(ingredients, eaten=True):
    """One eaten meal on a day, with the given (item, qty, unit, qty_type) ingredients."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE meal_days (id INTEGER PRIMARY KEY, date TEXT, status TEXT);
        CREATE TABLE day_meals (id INTEGER PRIMARY KEY, day_id INTEGER, eaten INTEGER);
        CREATE TABLE meal_ingredients (
            id INTEGER PRIMARY KEY, meal_id INTEGER,
            item TEXT, quantity TEXT, unit TEXT, quantity_type TEXT
        );
        """
    )
    conn.execute("INSERT INTO meal_days (id, date, status) VALUES (1, '2099-01-01', 'planned')")
    conn.execute("INSERT INTO day_meals (id, day_id, eaten) VALUES (1, 1, ?)", (1 if eaten else 0,))
    for item, qty, unit, qtype in ingredients:
        conn.execute(
            "INSERT INTO meal_ingredients (meal_id, item, quantity, unit, quantity_type) VALUES (1,?,?,?,?)",
            (item, qty, unit, qtype),
        )
    conn.commit()
    return conn


@pytest.fixture
def stub_pantry(monkeypatch):
    """Stub the pantry server functions and record update/remove calls."""
    state = {"inventory": [], "updates": [], "removes": []}
    monkeypatch.setattr(ps, "get_inventory", lambda: state["inventory"])
    monkeypatch.setattr(ps, "update_quantity",
                        lambda item, qty: state["updates"].append((item, qty)))
    monkeypatch.setattr(ps, "remove_items",
                        lambda items: state["removes"].extend(items))
    return state


class TestComputeDepletion:
    def test_trace_skipped(self, stub_pantry):
        conn = _make_db([("salt", "1", "tsp", "trace")])
        out = ps.compute_depletion(1, conn)
        assert out == {"auto_deducted": [], "needs_confirmation": []}

    def test_partial_needs_confirmation(self, stub_pantry):
        stub_pantry["inventory"] = [{"item": "onion", "quantity": "5 lb"}]
        conn = _make_db([("onion", "1/2", "whole", "partial")])
        out = ps.compute_depletion(1, conn)
        assert out["auto_deducted"] == []
        assert out["needs_confirmation"][0]["item"] == "onion"

    def test_mass_deduction_updates_pantry(self, stub_pantry):
        stub_pantry["inventory"] = [{"item": "chicken breast", "quantity": "10 lb"}]
        conn = _make_db([("chicken breast", "2", "lb", "exact")])
        out = ps.compute_depletion(1, conn)
        assert len(out["auto_deducted"]) == 1
        assert stub_pantry["updates"] == [("chicken breast", "8.0 lb")]
        assert stub_pantry["removes"] == []

    def test_mass_fully_consumed_removes(self, stub_pantry):
        stub_pantry["inventory"] = [{"item": "chicken breast", "quantity": "2 lb"}]
        conn = _make_db([("chicken breast", "2", "lb", "exact")])
        ps.compute_depletion(1, conn)
        assert stub_pantry["removes"] == ["chicken breast"]

    def test_fuzzy_name_match(self, stub_pantry):
        # 'rice (cooked)' should match pantry 'rice'.
        stub_pantry["inventory"] = [{"item": "rice", "quantity": "10 lb"}]
        conn = _make_db([("rice (cooked)", "1", "cup", "exact")])
        out = ps.compute_depletion(1, conn)
        assert len(out["auto_deducted"]) == 1
        assert stub_pantry["updates"] and stub_pantry["updates"][0][0] == "rice"

    def test_not_in_pantry_needs_confirmation(self, stub_pantry):
        stub_pantry["inventory"] = []
        conn = _make_db([("sesame oil", "1", "tsp", "exact")])
        out = ps.compute_depletion(1, conn)
        assert out["needs_confirmation"][0]["item"] == "sesame oil"

    def test_count_deduction(self, stub_pantry):
        stub_pantry["inventory"] = [{"item": "egg", "quantity": "12"}]
        conn = _make_db([("egg", "2", "whole", "exact")])
        out = ps.compute_depletion(1, conn)
        # 'whole' isn't a mass unit; pantry '12' is count -> dimensions mismatch
        # (need has a unit, pantry doesn't) -> needs confirmation, not silent wrong math.
        assert out["needs_confirmation"][0]["item"] == "egg"

    def test_uneaten_meals_ignored(self, stub_pantry):
        stub_pantry["inventory"] = [{"item": "chicken breast", "quantity": "10 lb"}]
        conn = _make_db([("chicken breast", "2", "lb", "exact")], eaten=False)
        out = ps.compute_depletion(1, conn)
        assert out == {"auto_deducted": [], "needs_confirmation": []}
