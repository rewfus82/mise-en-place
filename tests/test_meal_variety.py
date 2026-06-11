"""Tests for meal-slot labels and per-day diversity seeding."""
from meal_planner.agents import meal_planner as mp


def test_meal_structure_three_is_bld():
    line = mp._meal_structure_line(3)
    assert "Meal 1 = Breakfast" in line
    assert "Meal 2 = Lunch" in line
    assert "Meal 3 = Dinner" in line


def test_meal_structure_five_has_snacks():
    line = mp._meal_structure_line(5)
    assert "Morning Snack" in line and "Afternoon Snack" in line


def test_meal_structure_unusual_count_is_generic():
    assert mp._meal_structure_line(7) == "Plan them as Meal 1 … Meal 7."


def test_allowed_proteins_vegan_excludes_meat():
    pool = mp._allowed_proteins(["vegan"], "")
    assert "chicken" not in pool
    assert any("tofu" in p or "lentils" in p for p in pool)


def test_allowed_proteins_vegetarian_allows_eggs_not_meat():
    pool = mp._allowed_proteins(["vegetarian"], "")
    assert "chicken" not in pool
    assert "eggs" in pool


def test_allowed_proteins_drops_allergens():
    pool = mp._allowed_proteins([], "allergic to shellfish and fish")
    assert "shrimp" not in pool
    assert "salmon" not in pool
    assert "white fish" not in pool
    assert "chicken" in pool


def test_allowed_proteins_never_empty():
    # Even contradictory restrictions yield a usable fallback.
    pool = mp._allowed_proteins(["vegan"], "allergic to soy")
    assert pool  # non-empty


def test_diversity_directive_varies_by_index():
    d0 = mp._diversity_directive(0, [], "")
    d1 = mp._diversity_directive(1, [], "")
    assert d0 != d1
    assert "primary protein" in d0
