from __future__ import annotations
from pydantic import BaseModel


class PlanRangeRequest(BaseModel):
    start_date: str       # ISO date "2026-06-10"
    num_days: int
    bulk_prep_enabled: bool = False
    bulk_prep_pct: float = 0.0
    bulk_repeat_all_days: bool = False
    special_requests: str = ""
    thread_id: str | None = None   # if None, auto-generated


class ResumePlanRequest(BaseModel):
    thread_id: str
    feedback: str         # "approve" or revision instructions


class PlanDayRequest(BaseModel):
    date: str             # ISO date of the day to (re)generate
    special_requests: str = ""


class GroceryItemOut(BaseModel):
    ingredient: str
    quantity_needed: str
    unit: str | None
    needed_by_date: str
    deficit_calculable: bool
    quantity_type: str | None


class MarkBoughtRequest(BaseModel):
    item: str
    quantity: str
    category: str = "other"
