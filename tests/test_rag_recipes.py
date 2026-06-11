"""Tests for recipe retrieval and anchor blocks (against the committed recipes.db)."""
from meal_planner.rag import recipes
from meal_planner.rag.recipes import recipe_anchor_block, retrieve_recipes


def test_retrieve_returns_recipes():
    hits = retrieve_recipes("chicken dinner", k=3)
    assert hits
    assert all("name" in h for h in hits)
    assert len(hits) <= 3


def test_empty_query_returns_empty():
    assert retrieve_recipes("", k=3) == []


def test_anchor_block_formats():
    block = recipe_anchor_block("beef stew", k=3)
    assert block.startswith("Real recipe ideas")
    assert "uses" in block


def test_anchor_block_vegetarian_excludes_meat(monkeypatch):
    # Synthetic hits with known categories — assert meat-category dishes are dropped.
    hits = [
        {"name": "Beef Stew", "category": "Beef", "area": "Irish", "ingredients": "beef, potato"},
        {"name": "Lentil Dahl", "category": "Vegetarian", "area": "Indian", "ingredients": "lentils, spices"},
        {"name": "Grilled Salmon", "category": "Seafood", "area": "Norwegian", "ingredients": "salmon"},
        {"name": "Veg Stir Fry", "category": "Vegan", "area": "Thai", "ingredients": "tofu, veg"},
    ]
    monkeypatch.setattr(recipes, "retrieve_recipes", lambda *a, **k: hits)
    block = recipe_anchor_block("protein dinner", k=4, restrictions=["vegetarian"])
    assert "Beef Stew" not in block
    assert "Grilled Salmon" not in block
    assert "Lentil Dahl" in block
    assert "Veg Stir Fry" in block


def test_anchor_block_degrades_on_error(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("db gone")

    monkeypatch.setattr(recipes, "retrieve_recipes", boom)
    assert recipe_anchor_block("anything") == ""
