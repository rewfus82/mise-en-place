from __future__ import annotations


def calculate_tdee(
    weight_kg: float,
    height_cm: float,
    age: int,
    sex: str,
    activity_level: str,
    body_fat_pct: float | None = None,
) -> int:
    """
    Uses Katch-McArdle when body_fat_pct is provided (lean-mass based, more accurate
    for trained athletes). Falls back to Mifflin-St Jeor otherwise.
    """
    multipliers = {
        "sedentary": 1.2,
        "lightly_active": 1.375,
        "moderately_active": 1.55,
        "very_active": 1.725,
        "extra_active": 1.9,
    }
    factor = multipliers.get(activity_level, 1.55)

    if body_fat_pct is not None:
        # Katch-McArdle: BMR = 370 + 21.6 × LBM(kg)
        lbm_kg = weight_kg * (1 - body_fat_pct / 100)
        bmr = 370 + 21.6 * lbm_kg
    else:
        # Mifflin-St Jeor
        if sex == "male":
            bmr = 10 * weight_kg + 6.25 * height_cm - 5 * age + 5
        else:
            bmr = 10 * weight_kg + 6.25 * height_cm - 5 * age - 161

    return round(bmr * factor)


def recommended_macros(
    tdee: int,
    goal: str,
    weight_kg: float,
    body_fat_pct: float | None = None,
) -> dict:
    weight_lbs = weight_kg * 2.20462

    if goal == "bulk":
        calories = round(tdee * 1.15)
        if body_fat_pct is not None:
            lean_lbs = weight_lbs * (1 - body_fat_pct / 100)
            protein_g = round(lean_lbs * 1.0)
        else:
            protein_g = round(weight_lbs * 0.85)
    elif goal == "cut":
        calories = round(tdee * 0.80)
        if body_fat_pct is not None:
            lean_lbs = weight_lbs * (1 - body_fat_pct / 100)
            protein_g = round(lean_lbs * 1.2)
        else:
            protein_g = round(weight_lbs * 1.2)
    elif goal == "recomp":
        calories = tdee
        if body_fat_pct is not None:
            lean_lbs = weight_lbs * (1 - body_fat_pct / 100)
            protein_g = round(lean_lbs * 1.1)
        else:
            protein_g = round(weight_lbs * 1.0)
    else:  # maintain
        calories = tdee
        protein_g = round(weight_lbs * 0.8)

    fat_g = round(calories * 0.25 / 9)
    remaining = calories - protein_g * 4
    carbs_g = round((remaining - fat_g * 9) / 4)

    return {
        "calories": calories,
        "protein_g": protein_g,
        "carbs_g": max(carbs_g, 0),
        "fat_g": fat_g,
    }


def suggest_meals_per_day(calorie_target: int) -> int:
    if calorie_target < 2500:
        return 3
    elif calorie_target < 3500:
        return 4
    else:
        return 5
