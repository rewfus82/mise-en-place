from __future__ import annotations
from pydantic import BaseModel


class UserProfileOut(BaseModel):
    id: int
    skill_level: str
    max_cook_time_minutes: int
    weekly_budget: float | None
    dietary_restrictions: list[str]
    food_allergies: str
    meal_style: str
    meals_per_day: int
    height_cm: float | None
    weight_kg: float | None
    age: int | None
    sex: str | None
    activity_level: str
    body_fat_pct: float | None
    goal: str
    tdee_calculated: int | None
    calorie_target: int | None
    protein_target_g: int | None
    carbs_target_g: int | None
    fat_target_g: int | None
    theme: str


class UserProfileUpdate(BaseModel):
    skill_level: str | None = None
    max_cook_time_minutes: int | None = None
    weekly_budget: float | None = None
    dietary_restrictions: list[str] | None = None
    food_allergies: str | None = None
    meal_style: str | None = None
    meals_per_day: int | None = None
    height_cm: float | None = None
    weight_kg: float | None = None
    age: int | None = None
    sex: str | None = None
    activity_level: str | None = None
    body_fat_pct: float | None = None
    goal: str | None = None
    calorie_target: int | None = None
    protein_target_g: int | None = None
    carbs_target_g: int | None = None
    fat_target_g: int | None = None
    theme: str | None = None
    tdee_override: int | None = None  # set to bypass formula entirely


class TdeeResponse(BaseModel):
    tdee: int
    recommended_calories: int
    recommended_protein_g: int
    recommended_carbs_g: int
    recommended_fat_g: int
    suggested_meals_per_day: int
