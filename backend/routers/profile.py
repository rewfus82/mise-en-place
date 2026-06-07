from __future__ import annotations
import json
import sqlite3

from fastapi import APIRouter, Depends

from backend.database import get_db
from backend.schemas.profile import TdeeResponse, UserProfileOut, UserProfileUpdate
from backend.services.tdee_service import (
    calculate_tdee,
    recommended_macros,
    suggest_meals_per_day,
)

router = APIRouter(tags=["profile"])

_BODY_METRIC_FIELDS = {"height_cm", "weight_kg", "age", "sex", "activity_level", "body_fat_pct", "goal"}


def _get_or_create(conn: sqlite3.Connection) -> sqlite3.Row:
    row = conn.execute("SELECT * FROM user_profile WHERE id = 1").fetchone()
    if row is None:
        conn.execute("INSERT INTO user_profile (id) VALUES (1)")
        conn.commit()
        row = conn.execute("SELECT * FROM user_profile WHERE id = 1").fetchone()
    return row


def _row_to_profile(row: sqlite3.Row) -> UserProfileOut:
    d = dict(row)
    d["dietary_restrictions"] = json.loads(d.get("dietary_restrictions") or "[]")
    return UserProfileOut(**d)


@router.get("", response_model=UserProfileOut)
def get_profile(conn: sqlite3.Connection = Depends(get_db)):
    return _row_to_profile(_get_or_create(conn))


@router.put("", response_model=UserProfileOut)
def update_profile(
    body: UserProfileUpdate,
    conn: sqlite3.Connection = Depends(get_db),
):
    _get_or_create(conn)
    updates = body.model_dump(exclude_none=True)

    if "dietary_restrictions" in updates:
        updates["dietary_restrictions"] = json.dumps(updates["dietary_restrictions"])

    # Manual TDEE override takes precedence over formula
    if "tdee_override" in updates:
        updates["tdee_calculated"] = updates.pop("tdee_override")

    # Recalculate TDEE if any body metric changed (and no manual override in this request)
    body_fields_changed = _BODY_METRIC_FIELDS & set(updates.keys())
    if body_fields_changed and "tdee_calculated" not in updates:
        current = dict(conn.execute("SELECT * FROM user_profile WHERE id = 1").fetchone())
        merged = {**current, **updates}
        if all(merged.get(f) for f in ("weight_kg", "height_cm", "age", "sex", "activity_level")):
            tdee = calculate_tdee(
                merged["weight_kg"],
                merged["height_cm"],
                merged["age"],
                merged["sex"],
                merged["activity_level"],
                merged.get("body_fat_pct"),
            )
            updates["tdee_calculated"] = tdee
            goal = merged.get("goal", "maintain")
            macros = recommended_macros(tdee, goal, merged["weight_kg"], merged.get("body_fat_pct"))
            # Always recalculate calorie/protein targets when body metrics or goal change.
            # Users who want manual targets override them in MacroTargets (those requests
            # send calorie_target directly and don't go through this TDEE path).
            updates["calorie_target"] = macros["calories"]
            updates["protein_target_g"] = macros["protein_g"]
            updates["carbs_target_g"] = macros["carbs_g"]
            updates["fat_target_g"] = macros["fat_g"]

    if not updates:
        return _row_to_profile(conn.execute("SELECT * FROM user_profile WHERE id = 1").fetchone())

    set_clause = ", ".join(f"{k} = ?" for k in updates)
    conn.execute(f"UPDATE user_profile SET {set_clause} WHERE id = 1", list(updates.values()))
    conn.commit()
    return _row_to_profile(conn.execute("SELECT * FROM user_profile WHERE id = 1").fetchone())


@router.get("/tdee", response_model=TdeeResponse)
def get_tdee(conn: sqlite3.Connection = Depends(get_db)):
    row = dict(_get_or_create(conn))
    required = ("weight_kg", "height_cm", "age", "sex", "activity_level")
    if not all(row.get(f) for f in required):
        return TdeeResponse(
            tdee=0,
            recommended_calories=0,
            recommended_protein_g=0,
            recommended_carbs_g=0,
            recommended_fat_g=0,
            suggested_meals_per_day=3,
        )
    tdee = calculate_tdee(row["weight_kg"], row["height_cm"], row["age"], row["sex"], row["activity_level"], row.get("body_fat_pct"))
    macros = recommended_macros(tdee, row.get("goal", "maintain"), row["weight_kg"], row.get("body_fat_pct"))
    return TdeeResponse(
        tdee=tdee,
        recommended_calories=macros["calories"],
        recommended_protein_g=macros["protein_g"],
        recommended_carbs_g=macros["carbs_g"],
        recommended_fat_g=macros["fat_g"],
        suggested_meals_per_day=suggest_meals_per_day(macros["calories"]),
    )
