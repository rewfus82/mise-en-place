"""Build data/recipes.db from TheMealDB — a free, no-key recipe API.

Enumerates every meal (search by each letter a-z), keeps savory mains (drops
desserts), and embeds each into the recipe store for hybrid retrieval. The recipes
provide *names, cuisines, and ingredients* as inspiration anchors for meal
generation — the LLM still adapts portions and estimates macros, so no nutrition
data is needed from the source.

Run:  python -m scripts.ingest_recipes   (needs network)
The resulting recipes.db is committed so the deployed app needs no fetch at runtime.
"""
from __future__ import annotations

import string
import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from meal_planner.rag import recipes  # noqa: E402
from meal_planner.rag.embedder import embed  # noqa: E402

_API = "https://www.themealdb.com/api/json/v1/1/search.php?f={}"
_EXCLUDE_CATEGORIES = {"Dessert"}


def _fetch_all() -> list[dict]:
    meals: list[dict] = []
    with httpx.Client(timeout=30) as client:
        for letter in string.ascii_lowercase:
            resp = client.get(_API.format(letter))
            resp.raise_for_status()
            meals.extend(resp.json().get("meals") or [])
    return meals


def _build_recipe(meal: dict) -> dict:
    names, parts = [], []
    for i in range(1, 21):
        ing = (meal.get(f"strIngredient{i}") or "").strip()
        meas = (meal.get(f"strMeasure{i}") or "").strip()
        if ing:
            names.append(ing)
            parts.append(f"{meas} {ing}".strip())
    name = (meal.get("strMeal") or "").strip()
    category = (meal.get("strCategory") or "").strip()
    area = (meal.get("strArea") or "").strip()
    return {
        "meal_id": meal.get("idMeal"),
        "name": name,
        "category": category,
        "area": area,
        "ingredients": ", ".join(parts),
        "url": meal.get("strSource") or f"https://www.themealdb.com/meal/{meal.get('idMeal')}",
        "search_text": f"{name}. {category}. {area} cuisine. Ingredients: {', '.join(names)}.",
    }


def main() -> int:
    print("Fetching TheMealDB…")
    raw = _fetch_all()
    seen: set[str] = set()
    recs: list[dict] = []
    for meal in raw:
        if (meal.get("strCategory") or "") in _EXCLUDE_CATEGORIES:
            continue
        r = _build_recipe(meal)
        key = r["name"].lower()
        if not r["name"] or key in seen:
            continue
        seen.add(key)
        recs.append(r)

    if not recs:
        print("No recipes fetched.")
        return 1

    print(f"Embedding {len(recs)} recipes…")
    vectors = embed([r["search_text"] for r in recs])

    conn = recipes.connect()
    recipes.reset(conn)
    for r, vec in zip(recs, vectors):
        recipes.insert_recipe(conn, r, vec)
    conn.commit()
    recipes.rebuild_fts(conn)
    cats = sorted({r["category"] for r in recs if r["category"]})
    print(f"Built {recipes.RECIPES_PATH} — {len(recs)} recipes across {len(cats)} categories: {', '.join(cats)}")
    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
