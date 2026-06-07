"""
Tests for the pantry MCP server.
Uses an in-memory SQLite DB so tests are isolated and leave no files behind.
"""
import sqlite3
from unittest.mock import patch

import pytest

from meal_planner.mcp_servers import pantry_server


@pytest.fixture(autouse=True)
def _in_memory_db(tmp_path, monkeypatch):
    """Redirect all DB operations to a fresh temp file for each test."""
    db_file = tmp_path / "pantry_test.db"
    monkeypatch.setattr(pantry_server, "DB_PATH", db_file)
    yield


def test_empty_inventory():
    assert pantry_server.get_inventory() == []


def test_add_and_retrieve():
    items = [
        {"item": "chicken breast", "quantity": "2 lbs", "category": "protein"},
        {"item": "garlic", "quantity": "1 bulb", "category": "produce"},
    ]
    result = pantry_server.add_items(items)
    assert set(result["added"]) == {"chicken breast", "garlic"}
    assert result["skipped"] == []

    inventory = pantry_server.get_inventory()
    names = {i["item"] for i in inventory}
    assert names == {"chicken breast", "garlic"}


def test_add_skips_duplicates():
    pantry_server.add_items([{"item": "olive oil", "quantity": "1 bottle", "category": "condiments"}])
    result = pantry_server.add_items([{"item": "olive oil", "quantity": "2 bottles", "category": "condiments"}])
    assert result["skipped"] == ["olive oil"]
    assert len(pantry_server.get_inventory()) == 1


def test_remove_items():
    pantry_server.add_items([
        {"item": "pasta", "quantity": "1 box", "category": "grains"},
        {"item": "tomatoes", "quantity": "3", "category": "produce"},
    ])
    result = pantry_server.remove_items(["pasta"])
    assert result["removed"] == ["pasta"]
    assert result["not_found"] == []
    assert len(pantry_server.get_inventory()) == 1


def test_remove_not_found():
    result = pantry_server.remove_items(["unicorn meat"])
    assert result["not_found"] == ["unicorn meat"]
    assert result["removed"] == []


def test_check_item_present():
    pantry_server.add_items([{"item": "eggs", "quantity": "1 dozen", "category": "protein"}])
    assert pantry_server.check_item("eggs") is True
    assert pantry_server.check_item("EGGS") is True  # case-insensitive


def test_check_item_absent():
    assert pantry_server.check_item("truffles") is False


def test_clear_inventory():
    pantry_server.add_items([
        {"item": "butter", "quantity": "1 stick", "category": "dairy"},
        {"item": "flour", "quantity": "2 cups", "category": "grains"},
    ])
    result = pantry_server.clear_inventory()
    assert result["cleared"] is True
    assert pantry_server.get_inventory() == []
