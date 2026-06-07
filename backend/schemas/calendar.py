from __future__ import annotations
from pydantic import BaseModel


class IngredientOut(BaseModel):
    id: int
    meal_id: int
    item: str
    quantity: str | None
    unit: str | None
    quantity_type: str | None


class DayMealOut(BaseModel):
    id: int
    day_id: int
    meal_number: int
    recipe_name: str
    cook_time_minutes: int | None
    estimated_cost: float | None
    brief_description: str | None
    instructions: str | None = None
    calories_est: float | None
    protein_g_est: float | None
    carbs_g_est: float | None
    fat_g_est: float | None
    eaten: bool
    skipped: bool
    prep_id: int | None
    ingredients: list[IngredientOut] = []


class MealDayOut(BaseModel):
    id: int
    date: str
    status: str
    confirmed_at: str | None
    skipped_at: str | None
    meals: list[DayMealOut] = []


class MealPrepOut(BaseModel):
    id: int
    recipe_name: str
    brief_description: str | None
    total_servings: int
    servings_remaining: int
    prep_date: str
    calories_per_serving: float | None
    protein_g_per_serving: float | None
    carbs_g_per_serving: float | None
    fat_g_per_serving: float | None


class ToggleEatenRequest(BaseModel):
    eaten: bool


class ToggleSkippedRequest(BaseModel):
    skipped: bool


class EndDayResponse(BaseModel):
    auto_deducted: list[dict]
    needs_confirmation: list[dict]


class DepletePantryRequest(BaseModel):
    items: list[str]
