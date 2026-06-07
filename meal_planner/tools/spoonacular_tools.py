import os

import httpx
from langchain_core.tools import tool

_BASE = "https://api.spoonacular.com"


def _key() -> str:
    key = os.getenv("SPOONACULAR_API_KEY")
    if not key:
        raise EnvironmentError("SPOONACULAR_API_KEY not set")
    return key


@tool
def tool_search_recipes(
    query: str,
    max_ready_time: int = 60,
    number: int = 5,
    include_ingredients: str = "",
) -> list[dict]:
    """
    Search Spoonacular for recipes. Returns id, title, readyInMinutes, servings.
    include_ingredients: comma-separated pantry items to prioritize.
    """
    params: dict = {
        "apiKey": _key(),
        "query": query,
        "maxReadyTime": max_ready_time,
        "number": number,
        "addRecipeInformation": True,
    }
    if include_ingredients:
        params["includeIngredients"] = include_ingredients

    resp = httpx.get(f"{_BASE}/recipes/complexSearch", params=params, timeout=15)
    resp.raise_for_status()

    return [
        {
            "id": r["id"],
            "title": r["title"],
            "ready_in_minutes": r.get("readyInMinutes", 0),
            "servings": r.get("servings", 4),
            "price_per_serving": round(r.get("pricePerServing", 0) / 100, 2),
        }
        for r in resp.json().get("results", [])
    ]


@tool
def tool_get_recipe_details(recipe_id: int) -> dict:
    """Get full recipe details: ingredients list, instructions, and cost per serving."""
    params = {"apiKey": _key()}
    resp = httpx.get(
        f"{_BASE}/recipes/{recipe_id}/information", params=params, timeout=15
    )
    resp.raise_for_status()
    r = resp.json()

    return {
        "id": r["id"],
        "title": r["title"],
        "ready_in_minutes": r.get("readyInMinutes", 0),
        "servings": r.get("servings", 4),
        "price_per_serving": round(r.get("pricePerServing", 0) / 100, 2),
        "ingredients": [
            {
                "name": ing["name"],
                "amount": ing["amount"],
                "unit": ing["unit"],
            }
            for ing in r.get("extendedIngredients", [])
        ],
        "instructions": r.get("instructions", ""),
    }


@tool
def tool_get_recipe_nutrition(recipe_id: int) -> dict:
    """Get macro nutrition per serving: calories, protein, carbs, fat, fiber."""
    params = {"apiKey": _key()}
    resp = httpx.get(
        f"{_BASE}/recipes/{recipe_id}/nutritionWidget.json", params=params, timeout=15
    )
    resp.raise_for_status()
    nutrients = resp.json().get("nutrients", [])

    def _get(name: str) -> float:
        for n in nutrients:
            if n["name"].lower() == name.lower():
                return float(n["amount"])
        return 0.0

    return {
        "recipe_id": recipe_id,
        "calories": _get("Calories"),
        "protein_g": _get("Protein"),
        "carbs_g": _get("Carbohydrates"),
        "fat_g": _get("Fat"),
        "fiber_g": _get("Fiber"),
    }


SPOONACULAR_TOOLS = [tool_search_recipes, tool_get_recipe_details, tool_get_recipe_nutrition]
