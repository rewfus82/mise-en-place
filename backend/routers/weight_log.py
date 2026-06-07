from __future__ import annotations
import sqlite3
from datetime import date as Date

from fastapi import APIRouter, Depends, HTTPException

from backend.database import get_db
from backend.schemas.weight_log import MeasuredTdeeOut, WeightEntryIn, WeightEntryOut

router = APIRouter(tags=["weight_log"])


@router.get("", response_model=list[WeightEntryOut])
def list_entries(conn: sqlite3.Connection = Depends(get_db)):
    rows = conn.execute(
        "SELECT id, date, weight_kg, notes FROM weight_log ORDER BY date DESC"
    ).fetchall()
    return [WeightEntryOut(**dict(r)) for r in rows]


@router.post("", response_model=WeightEntryOut)
def upsert_entry(body: WeightEntryIn, conn: sqlite3.Connection = Depends(get_db)):
    conn.execute(
        """
        INSERT INTO weight_log (date, weight_kg, notes)
        VALUES (?, ?, ?)
        ON CONFLICT(date) DO UPDATE SET weight_kg = excluded.weight_kg, notes = excluded.notes
        """,
        (body.date, body.weight_kg, body.notes),
    )
    conn.commit()
    row = conn.execute(
        "SELECT id, date, weight_kg, notes FROM weight_log WHERE date = ?", (body.date,)
    ).fetchone()
    return WeightEntryOut(**dict(row))


@router.delete("/{entry_date}", status_code=204)
def delete_entry(entry_date: str, conn: sqlite3.Connection = Depends(get_db)):
    conn.execute("DELETE FROM weight_log WHERE date = ?", (entry_date,))
    conn.commit()


@router.get("/measured-tdee", response_model=MeasuredTdeeOut | None)
def get_measured_tdee(conn: sqlite3.Connection = Depends(get_db)):
    weights = conn.execute(
        "SELECT date, weight_kg FROM weight_log ORDER BY date"
    ).fetchall()

    if len(weights) < 2:
        return None

    w_start = dict(weights[0])
    w_end = dict(weights[-1])
    days = (Date.fromisoformat(w_end["date"]) - Date.fromisoformat(w_start["date"])).days

    if days < 7:
        return None

    # Avg daily calories from confirmed/eaten meals in the window
    rows = conn.execute(
        """
        SELECT dm.calories_est
        FROM day_meals dm
        JOIN meal_days md ON dm.day_id = md.id
        WHERE md.date >= ? AND md.date <= ?
          AND dm.eaten = 1
          AND dm.calories_est IS NOT NULL
        """,
        (w_start["date"], w_end["date"]),
    ).fetchall()

    if not rows:
        return None

    # Count unique tracked days
    day_count = conn.execute(
        """
        SELECT COUNT(DISTINCT md.date) as cnt
        FROM day_meals dm
        JOIN meal_days md ON dm.day_id = md.id
        WHERE md.date >= ? AND md.date <= ?
          AND dm.eaten = 1
          AND dm.calories_est IS NOT NULL
        """,
        (w_start["date"], w_end["date"]),
    ).fetchone()["cnt"]

    if day_count < 7:
        return None

    total_calories = sum(r["calories_est"] for r in rows)
    avg_calories = total_calories / day_count
    weight_change_kg = w_end["weight_kg"] - w_start["weight_kg"]

    # true_maintenance = avg_calories - (weight_change × 7700 / days)
    measured_tdee = avg_calories - (weight_change_kg * 7700 / days)

    return MeasuredTdeeOut(
        measured_tdee=round(measured_tdee),
        window_days=days,
        tracked_days=day_count,
        start_date=w_start["date"],
        end_date=w_end["date"],
        start_weight_kg=w_start["weight_kg"],
        end_weight_kg=w_end["weight_kg"],
        avg_daily_calories=round(avg_calories),
    )
