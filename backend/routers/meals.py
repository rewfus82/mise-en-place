from __future__ import annotations
import sqlite3
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException

from backend.database import get_db
from backend.schemas.calendar import (
    DepletePantryRequest,
    EndDayResponse,
    ToggleEatenRequest,
    ToggleSkippedRequest,
)
from backend.services.pantry_service import compute_depletion

router = APIRouter(tags=["meals"])


def _get_day_id(date: str, conn: sqlite3.Connection) -> int:
    row = conn.execute("SELECT id FROM meal_days WHERE date = ?", (date,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Day not found")
    return row["id"]


@router.patch("/{date}/meals/{meal_id}/eaten", response_model=dict)
def toggle_eaten(
    date: str,
    meal_id: int,
    body: ToggleEatenRequest,
    conn: sqlite3.Connection = Depends(get_db),
):
    day_id = _get_day_id(date, conn)
    conn.execute(
        "UPDATE day_meals SET eaten = ? WHERE id = ? AND day_id = ?",
        (int(body.eaten), meal_id, day_id),
    )
    conn.commit()
    return {"meal_id": meal_id, "eaten": body.eaten}


@router.patch("/{date}/meals/{meal_id}/skipped", response_model=dict)
def toggle_skipped(
    date: str,
    meal_id: int,
    body: ToggleSkippedRequest,
    conn: sqlite3.Connection = Depends(get_db),
):
    day_id = _get_day_id(date, conn)
    conn.execute(
        "UPDATE day_meals SET skipped = ? WHERE id = ? AND day_id = ?",
        (int(body.skipped), meal_id, day_id),
    )
    conn.commit()
    return {"meal_id": meal_id, "skipped": body.skipped}


@router.post("/{date}/end", response_model=EndDayResponse)
def end_day(date: str, conn: sqlite3.Connection = Depends(get_db)):
    day_id = _get_day_id(date, conn)

    # Verify all meals are addressed
    unaddressed = conn.execute(
        "SELECT COUNT(*) FROM day_meals WHERE day_id = ? AND eaten = 0 AND skipped = 0",
        (day_id,),
    ).fetchone()[0]
    if unaddressed > 0:
        raise HTTPException(status_code=400, detail="Not all meals have been addressed")

    result = compute_depletion(day_id, conn)

    # Decrement bulk prep servings for eaten meals with prep_id
    prep_meals = conn.execute(
        "SELECT prep_id FROM day_meals WHERE day_id = ? AND eaten = 1 AND prep_id IS NOT NULL",
        (day_id,),
    ).fetchall()
    for pm in prep_meals:
        conn.execute(
            "UPDATE meal_preps SET servings_remaining = MAX(0, servings_remaining - 1) WHERE id = ?",
            (pm["prep_id"],),
        )

    conn.execute(
        "UPDATE meal_days SET status = 'completed', confirmed_at = ? WHERE id = ?",
        (datetime.utcnow().isoformat(), day_id),
    )
    conn.commit()

    return EndDayResponse(**result)
