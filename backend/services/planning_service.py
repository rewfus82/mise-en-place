from __future__ import annotations
import asyncio
import json
import logging
import sqlite3
from threading import Thread

from backend.schemas.planning import PlanRangeRequest, ResumePlanRequest
from meal_planner.llm import (
    LLMConfigError,
    normalize_provider,
    reset_request_creds,
    set_request_creds,
)
from meal_planner.mcp_servers.pantry_server import get_inventory

logger = logging.getLogger(__name__)


def _validate_creds(provider: str, api_key: str) -> tuple[str, str]:
    """Normalize the provider and require a key. Raises LLMConfigError if bad.

    The key is NOT placed in the graph config — LangGraph's checkpointer persists
    config.configurable to disk. It is carried in a request-scoped ContextVar
    (see set_request_creds) instead, and never logged.
    """
    norm = normalize_provider(provider)
    if not api_key or not api_key.strip():
        raise LLMConfigError("No API key provided for the selected AI provider.")
    return norm, api_key


_graph = None
_graph_lock = asyncio.Lock()
_range_locks: dict[str, asyncio.Lock] = {}


def get_graph():
    global _graph
    if _graph is None:
        from meal_planner.graph import build_range_graph
        _graph = build_range_graph()
    return _graph


def _resolve_targets(profile: dict) -> tuple[int, int]:
    """Return (calorie_target, protein_target_g) — never None."""
    from backend.services.tdee_service import calculate_tdee, recommended_macros

    calorie = profile.get("calorie_target")
    protein = profile.get("protein_target_g")

    if calorie and protein:
        return calorie, protein

    if all(profile.get(f) for f in ("weight_kg", "height_cm", "age", "sex", "activity_level")):
        tdee = calculate_tdee(
            profile["weight_kg"], profile["height_cm"],
            profile["age"], profile["sex"], profile["activity_level"],
        )
        macros = recommended_macros(
            tdee, profile.get("goal", "maintain"),
            profile["weight_kg"], profile.get("body_fat_pct"),
        )
        calorie = calorie or macros["calories"]
        protein = protein or macros["protein_g"]
    else:
        calorie = calorie or 2200
        protein = protein or 150

    return calorie, protein


def _build_initial_state(req: PlanRangeRequest, profile: dict, pantry: list) -> dict:
    import json as _json
    calorie_target, protein_target_g = _resolve_targets(profile)
    restrictions = profile.get("dietary_restrictions", "[]")
    if isinstance(restrictions, str):
        restrictions = _json.loads(restrictions)

    return {
        "messages": [],
        "skill_level": profile.get("skill_level", "intermediate"),
        "max_cook_time_minutes": profile.get("max_cook_time_minutes", 60),
        "daily_budget": profile.get("weekly_budget"),
        "dietary_restrictions": restrictions,
        "food_allergies": profile.get("food_allergies", ""),
        "calorie_target": calorie_target,
        "protein_target_g": protein_target_g,
        "carbs_target_g": profile.get("carbs_target_g"),
        "fat_target_g": profile.get("fat_target_g"),
        "meal_style": profile.get("meal_style", "simple"),
        "meals_per_day": profile.get("meals_per_day", 3),
        "start_date": req.start_date,
        "num_days": req.num_days,
        "bulk_prep_enabled": req.bulk_prep_enabled,
        "bulk_prep_pct": req.bulk_prep_pct,
        "bulk_repeat_all_days": req.bulk_repeat_all_days,
        "special_requests": req.special_requests or "",
        "pantry_inventory": pantry,
        "planned_days": [],
        "nutrition_summaries": [],
        "awaiting_human_approval": False,
        "human_feedback": None,
        "current_agent": "orchestrator",
        "error": None,
    }


def _sse(data: dict) -> str:
    return f"data: {json.dumps(data)}\n\n"


def _persist_plan(planned_days: list[dict], db: sqlite3.Connection) -> None:
    """Write approved plan to calendar.db."""
    for day_plan in planned_days:
        date = day_plan["date"]
        db.execute(
            "INSERT OR IGNORE INTO meal_days (date, status) VALUES (?, 'planned')",
            (date,),
        )
        day_row = db.execute("SELECT id FROM meal_days WHERE date = ?", (date,)).fetchone()
        day_id = day_row["id"]

        for meal in day_plan.get("meals", []):
            # Handle bulk prep
            prep_id = None
            if meal.get("is_bulk_prep") and meal.get("bulk_servings", 1) > 1:
                cur = db.execute(
                    """INSERT INTO meal_preps
                       (recipe_name, brief_description, total_servings, servings_remaining,
                        prep_date, calories_per_serving, protein_g_per_serving,
                        carbs_g_per_serving, fat_g_per_serving)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        meal["recipe_name"],
                        meal.get("brief_description", ""),
                        meal["bulk_servings"],
                        meal["bulk_servings"],
                        date,
                        meal.get("calories_est"),
                        meal.get("protein_g_est"),
                        meal.get("carbs_g_est"),
                        meal.get("fat_g_est"),
                    ),
                )
                prep_id = cur.lastrowid

            instructions = meal.get("instructions") or []
            instructions_text = "\n".join(instructions) if isinstance(instructions, list) else str(instructions)

            cur = db.execute(
                """INSERT INTO day_meals
                   (day_id, meal_number, recipe_name, cook_time_minutes, estimated_cost,
                    brief_description, instructions, calories_est, protein_g_est, carbs_g_est,
                    fat_g_est, prep_id)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    day_id,
                    meal["meal_number"],
                    meal["recipe_name"],
                    meal.get("cook_time_minutes"),
                    meal.get("estimated_cost"),
                    meal.get("brief_description", ""),
                    instructions_text,
                    meal.get("calories_est"),
                    meal.get("protein_g_est"),
                    meal.get("carbs_g_est"),
                    meal.get("fat_g_est"),
                    prep_id,
                ),
            )
            meal_id = cur.lastrowid

            for ing in meal.get("ingredients", []):
                db.execute(
                    """INSERT INTO meal_ingredients (meal_id, item, quantity, unit, quantity_type)
                       VALUES (?, ?, ?, ?, ?)""",
                    (meal_id, ing["item"], ing.get("quantity"), ing.get("unit"), ing.get("quantity_type")),
                )

    db.commit()


def regenerate_day(
    date: str,
    profile: dict,
    db: sqlite3.Connection,
    special_requests: str = "",
    provider: str = "",
    api_key: str = "",
) -> int:
    """Re-run generation for a single day and replace its meals. Returns meal count.

    Synchronous (single blocking LLM call ~10–15s). Only the one day's meals are
    replaced; the meal_days row (and its status) is preserved/created as 'planned'.
    """
    from meal_planner.agents.meal_planner import meal_planner_node

    req = PlanRangeRequest(start_date=date, num_days=1, special_requests=special_requests)
    state = _build_initial_state(req, profile, get_inventory())

    norm_provider, api_key = _validate_creds(provider, api_key)
    token = set_request_creds(norm_provider, api_key)
    try:
        out = meal_planner_node(state)
    finally:
        reset_request_creds(token)
    planned_days = out.get("planned_days") or []
    if not planned_days or not planned_days[0].get("meals"):
        raise ValueError("Generation produced no meals")
    planned_days[0]["date"] = date

    row = db.execute("SELECT id FROM meal_days WHERE date = ?", (date,)).fetchone()
    if row:
        db.execute("DELETE FROM day_meals WHERE day_id = ?", (row["id"],))
        db.execute("UPDATE meal_days SET status = 'planned', confirmed_at = NULL WHERE id = ?", (row["id"],))
    db.commit()

    _persist_plan(planned_days, db)
    return len(planned_days[0]["meals"])


async def stream_plan(
    req: PlanRangeRequest,
    profile: dict,
    db: sqlite3.Connection,
    provider: str = "",
    api_key: str = "",
):
    thread_id = req.thread_id or f"range-{req.start_date}-{req.num_days}"
    range_key = thread_id

    try:
        norm_provider, api_key = _validate_creds(provider, api_key)
    except LLMConfigError as exc:
        yield _sse({"type": "error", "message": str(exc)})
        return

    config = {"configurable": {"thread_id": thread_id}}

    if range_key not in _range_locks:
        _range_locks[range_key] = asyncio.Lock()

    async with _range_locks[range_key]:
        graph = get_graph()
        initial_state = _build_initial_state(req, profile, get_inventory())

        queue: asyncio.Queue = asyncio.Queue()
        loop = asyncio.get_event_loop()

        def _run_sync():
            # ContextVar must be set in THIS thread (the one running the graph), as
            # new threads start with a fresh context.
            token = set_request_creds(norm_provider, api_key)
            try:
                try:
                    for chunk in graph.stream(initial_state, config, stream_mode="updates"):
                        for node_name, state_update in chunk.items():
                            if node_name == "__interrupt__":
                                continue
                            msg = ""
                            if "messages" in state_update:
                                msgs = state_update["messages"]
                                if msgs:
                                    msg = msgs[-1].content if hasattr(msgs[-1], "content") else str(msgs[-1])
                            loop.call_soon_threadsafe(
                                queue.put_nowait,
                                {"type": "progress", "agent": node_name, "message": msg},
                            )
                except Exception as exc:
                    logger.exception("Planning stream failed for thread %s", thread_id)
                    loop.call_soon_threadsafe(queue.put_nowait, {"type": "_stream_done", "exc": str(exc)})
                    return
                loop.call_soon_threadsafe(queue.put_nowait, {"type": "_stream_done", "exc": None})
            finally:
                reset_request_creds(token)

        thread = Thread(target=_run_sync, daemon=True)
        thread.start()

        stream_error = None
        while True:
            event = await queue.get()
            if event["type"] == "_stream_done":
                stream_error = event.get("exc")
                break
            yield _sse(event)

        if stream_error:
            yield _sse({
                "type": "error",
                "message": f"Planning failed: {stream_error}",
            })
            return

        # Check if graph is paused at human_review interrupt
        snapshot = graph.get_state(config)
        if snapshot.next:
            planned_days = snapshot.values.get("planned_days", [])
            nutrition = snapshot.values.get("nutrition_summaries", [])

            # Guard: if the plan has no meals the LLM returned a bad response
            total_meals = sum(len(d.get("meals", [])) for d in planned_days)
            if not planned_days or total_meals == 0:
                yield _sse({
                    "type": "error",
                    "message": (
                        f"The AI returned {len(planned_days)} day(s) with 0 meals — "
                        "the structured output may have failed. Please try again."
                    ),
                })
                return

            yield _sse({
                "type": "awaiting_review",
                "thread_id": thread_id,
                "days": planned_days,
                "nutrition_summaries": nutrition,
            })
        else:
            planned_days = snapshot.values.get("planned_days", [])
            if planned_days:
                _persist_plan(planned_days, db)
            yield _sse({"type": "complete", "thread_id": thread_id})


async def resume_plan(
    req: ResumePlanRequest,
    db: sqlite3.Connection,
    provider: str = "",
    api_key: str = "",
):
    from langgraph.types import Command

    try:
        norm_provider, api_key = _validate_creds(provider, api_key)
    except LLMConfigError as exc:
        yield _sse({"type": "error", "message": str(exc)})
        return

    config = {"configurable": {"thread_id": req.thread_id}}
    graph = get_graph()

    approved = req.feedback.lower().strip() in {"approve", "approved", "yes", "y", "ok", "lgtm", "looks good"}

    queue: asyncio.Queue = asyncio.Queue()
    loop = asyncio.get_event_loop()

    def _run_sync():
        token = set_request_creds(norm_provider, api_key)
        try:
            try:
                for chunk in graph.stream(
                    Command(resume=req.feedback), config, stream_mode="updates"
                ):
                    for node_name, state_update in chunk.items():
                        if node_name == "__interrupt__":
                            continue
                        msg = ""
                        if "messages" in state_update:
                            msgs = state_update["messages"]
                            if msgs:
                                msg = msgs[-1].content if hasattr(msgs[-1], "content") else str(msgs[-1])
                        loop.call_soon_threadsafe(
                            queue.put_nowait,
                            {"type": "progress", "agent": node_name, "message": msg},
                        )
            except Exception as exc:
                logger.exception("Resume stream failed for thread %s", req.thread_id)
                loop.call_soon_threadsafe(queue.put_nowait, {"type": "_stream_done", "exc": str(exc)})
                return
            loop.call_soon_threadsafe(queue.put_nowait, {"type": "_stream_done", "exc": None})
        finally:
            reset_request_creds(token)

    thread = Thread(target=_run_sync, daemon=True)
    thread.start()

    stream_error = None
    while True:
        event = await queue.get()
        if event["type"] == "_stream_done":
            stream_error = event.get("exc")
            break
        yield _sse(event)

    if stream_error:
        yield _sse({
            "type": "error",
            "message": f"Planning failed: {stream_error}",
        })
        return

    snapshot = graph.get_state(config)
    if snapshot.next:
        planned_days = snapshot.values.get("planned_days", [])
        nutrition = snapshot.values.get("nutrition_summaries", [])
        yield _sse({
            "type": "awaiting_review",
            "thread_id": req.thread_id,
            "days": planned_days,
            "nutrition_summaries": nutrition,
        })
    else:
        if approved:
            planned_days = snapshot.values.get("planned_days", [])
            if planned_days:
                _persist_plan(planned_days, db)
        yield _sse({"type": "complete", "thread_id": req.thread_id})
