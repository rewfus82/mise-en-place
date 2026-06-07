from __future__ import annotations
from pydantic import BaseModel


class WeightEntryOut(BaseModel):
    id: int
    date: str
    weight_kg: float
    notes: str | None


class WeightEntryIn(BaseModel):
    date: str
    weight_kg: float
    notes: str | None = None


class MeasuredTdeeOut(BaseModel):
    measured_tdee: int
    window_days: int
    tracked_days: int
    start_date: str
    end_date: str
    start_weight_kg: float
    end_weight_kg: float
    avg_daily_calories: int
