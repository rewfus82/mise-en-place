from __future__ import annotations
import json
import sqlite3

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from backend.database import get_db
from backend.routers.profile import _get_or_create
from fastapi import HTTPException

from backend.schemas.planning import PlanDayRequest, PlanRangeRequest, ResumePlanRequest
from backend.services import planning_service

router = APIRouter(tags=["planning"])

_SSE_HEADERS = {
    "Cache-Control": "no-cache",
    "X-Accel-Buffering": "no",
    "Connection": "keep-alive",
}


@router.post("/range")
async def plan_range(
    req: PlanRangeRequest,
    conn: sqlite3.Connection = Depends(get_db),
):
    profile = dict(_get_or_create(conn))

    async def generator():
        async for chunk in planning_service.stream_plan(req, profile, conn):
            yield chunk

    return StreamingResponse(generator(), media_type="text/event-stream", headers=_SSE_HEADERS)


@router.post("/day", response_model=dict)
def plan_day(req: PlanDayRequest, conn: sqlite3.Connection = Depends(get_db)):
    """Regenerate a single day's meals (synchronous)."""
    profile = dict(_get_or_create(conn))
    try:
        meal_count = planning_service.regenerate_day(req.date, profile, conn, req.special_requests)
    except ValueError as exc:
        raise HTTPException(status_code=502, detail=str(exc))
    return {"date": req.date, "meal_count": meal_count}


@router.post("/range/resume")
async def resume_range(
    req: ResumePlanRequest,
    conn: sqlite3.Connection = Depends(get_db),
):
    async def generator():
        async for chunk in planning_service.resume_plan(req, conn):
            yield chunk

    return StreamingResponse(generator(), media_type="text/event-stream", headers=_SSE_HEADERS)
