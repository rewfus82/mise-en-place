"""Diagnostics / troubleshooting endpoints.

GET /health           — fast liveness probe (for load balancers / uptime checks)
GET /health/detailed  — deep subsystem check (DB, checkpoints, graph, API key)
"""
from __future__ import annotations

import os
import sqlite3
from pathlib import Path

from fastapi import APIRouter

router = APIRouter(tags=["diagnostics"])

_DATA = Path(__file__).parent.parent.parent / "data"
_CALENDAR_DB = _DATA / "calendar.db"
_CHECKPOINTS_DB = _DATA / "checkpoints.db"

_EXPECTED_TABLES = {
    "user_profile", "meal_preps", "meal_days", "day_meals",
    "meal_ingredients", "grocery_overrides", "weight_log",
}


def _check_sqlite(path: Path, expected_tables: set[str] | None = None) -> dict:
    if not path.exists():
        return {"status": "error", "detail": f"{path.name} does not exist"}
    try:
        conn = sqlite3.connect(str(path))
        try:
            conn.execute("SELECT 1").fetchone()
            rows = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
            tables = {r[0] for r in rows}
        finally:
            conn.close()
    except sqlite3.Error as exc:
        return {"status": "error", "detail": str(exc)}

    result = {"status": "ok", "tables": sorted(tables)}
    if expected_tables:
        missing = expected_tables - tables
        if missing:
            result["status"] = "error"
            result["detail"] = f"missing tables: {sorted(missing)}"
    return result


def _check_graph() -> dict:
    try:
        from backend.services.planning_service import get_graph

        graph = get_graph()
        nodes = [n for n in graph.get_graph().nodes if not n.startswith("__")]
        return {"status": "ok", "nodes": nodes}
    except Exception as exc:  # noqa: BLE001 — surface any build failure
        return {"status": "error", "detail": str(exc)}


def _check_langgraph_version() -> str | None:
    try:
        import langgraph.version

        return langgraph.version.__version__
    except Exception:  # noqa: BLE001
        return None


@router.get("/health")
def health() -> dict:
    """Fast liveness probe — does not touch the DB or graph."""
    return {"status": "ok"}


@router.get("/health/detailed")
def health_detailed() -> dict:
    checks = {
        "database": _check_sqlite(_CALENDAR_DB, _EXPECTED_TABLES),
        "checkpoints": _check_sqlite(_CHECKPOINTS_DB),
        "graph": _check_graph(),
        "anthropic_api_key": {
            "status": "ok" if os.getenv("ANTHROPIC_API_KEY") else "error",
            "detail": None if os.getenv("ANTHROPIC_API_KEY") else "ANTHROPIC_API_KEY not set",
        },
    }
    overall = "ok" if all(c["status"] == "ok" for c in checks.values()) else "degraded"
    return {
        "status": overall,
        "langgraph_version": _check_langgraph_version(),
        "checks": checks,
    }
