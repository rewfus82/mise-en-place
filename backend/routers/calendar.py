from __future__ import annotations
import calendar
import sqlite3

from fastapi import APIRouter, Depends, HTTPException

from backend.database import get_db
from backend.schemas.calendar import MealDayOut, MealPrepOut

router = APIRouter(tags=["calendar"])


def _fetch_month(year: int, month: int, conn: sqlite3.Connection) -> list[MealDayOut]:
    _, last_day = calendar.monthrange(year, month)
    start = f"{year:04d}-{month:02d}-01"
    end = f"{year:04d}-{month:02d}-{last_day:02d}"

    days = conn.execute(
        "SELECT * FROM meal_days WHERE date BETWEEN ? AND ? ORDER BY date",
        (start, end),
    ).fetchall()

    result = []
    for day in days:
        meals = conn.execute(
            "SELECT * FROM day_meals WHERE day_id = ? ORDER BY meal_number",
            (day["id"],),
        ).fetchall()
        meal_list = []
        for meal in meals:
            ingredients = conn.execute(
                "SELECT * FROM meal_ingredients WHERE meal_id = ?",
                (meal["id"],),
            ).fetchall()
            meal_dict = dict(meal)
            meal_dict["eaten"] = bool(meal_dict["eaten"])
            meal_dict["skipped"] = bool(meal_dict["skipped"])
            meal_dict["ingredients"] = [dict(i) for i in ingredients]
            meal_list.append(meal_dict)
        day_dict = dict(day)
        day_dict["meals"] = meal_list
        result.append(MealDayOut(**day_dict))
    return result


@router.get("/{year}/{month}", response_model=list[MealDayOut])
def get_month(year: int, month: int, conn: sqlite3.Connection = Depends(get_db)):
    return _fetch_month(year, month, conn)


@router.delete("/{date}", response_model=dict)
def delete_day(date: str, conn: sqlite3.Connection = Depends(get_db)):
    row = conn.execute("SELECT id FROM meal_days WHERE date = ?", (date,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Day not found")
    conn.execute("DELETE FROM meal_days WHERE date = ?", (date,))
    conn.commit()
    return {"deleted": date}


@router.get("/unconfirmed", response_model=list[MealDayOut])
def get_unconfirmed(conn: sqlite3.Connection = Depends(get_db)):
    from datetime import date
    today = date.today().isoformat()
    days = conn.execute(
        """SELECT * FROM meal_days
           WHERE date < ? AND status = 'planned' AND skipped_at IS NULL
           ORDER BY date ASC""",
        (today,),
    ).fetchall()
    result = []
    for day in days:
        meals = conn.execute(
            "SELECT * FROM day_meals WHERE day_id = ? ORDER BY meal_number",
            (day["id"],),
        ).fetchall()
        day_dict = dict(day)
        day_dict["meals"] = [
            {**dict(m), "eaten": bool(m["eaten"]), "skipped": bool(m["skipped"]), "ingredients": []}
            for m in meals
        ]
        result.append(MealDayOut(**day_dict))
    return result


@router.post("/{date}/skip", response_model=dict)
def skip_day(date: str, conn: sqlite3.Connection = Depends(get_db)):
    from datetime import datetime
    row = conn.execute("SELECT id FROM meal_days WHERE date = ?", (date,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Day not found")
    conn.execute(
        "UPDATE meal_days SET skipped_at = ? WHERE date = ?",
        (datetime.utcnow().isoformat(), date),
    )
    conn.commit()
    return {"skipped": date}


@router.get("/meal-preps", response_model=list[MealPrepOut])
def list_meal_preps(conn: sqlite3.Connection = Depends(get_db)):
    rows = conn.execute(
        "SELECT * FROM meal_preps WHERE servings_remaining > 0 ORDER BY prep_date DESC"
    ).fetchall()
    return [MealPrepOut(**dict(r)) for r in rows]
