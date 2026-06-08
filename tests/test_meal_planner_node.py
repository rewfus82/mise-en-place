"""Tests for meal_planner_node and the graph flow with a mocked LLM (no API calls).

The node builds its LLM per request via `make_llm(...).with_structured_output(...)`
(BYOK — no module-level singleton). Tests patch `mp.make_llm` to return a fake LLM
whose `with_structured_output` hands back the right fake planner for the schema.
"""
import pytest
from pydantic import ValidationError

from meal_planner.agents import meal_planner as mp


def _ingredient():
    return mp._Ingredient(item="chicken breast", quantity="2", unit="lbs", quantity_type="exact")


def _meal(n: int, name: str = "Test Meal", bulk: bool = False):
    return mp._Meal(
        meal_number=n,
        recipe_name=name,
        cook_time_minutes=20,
        estimated_cost=4.50,
        brief_description="desc",
        instructions=["Step one", "Step two"],
        ingredients=[_ingredient()],
        calories_est=700,
        protein_g_est=55,
        carbs_g_est=60,
        fat_g_est=20,
        is_bulk_prep=bulk,
        bulk_servings=3 if bulk else 1,
        bulk_prep_days=["2026-06-10"] if bulk else [],
    )


def _base_state(**over):
    state = {
        "messages": [],
        "skill_level": "intermediate",
        "max_cook_time_minutes": 45,
        "daily_budget": None,
        "dietary_restrictions": [],
        "food_allergies": "",
        "calorie_target": 2100,
        "protein_target_g": 165,
        "carbs_target_g": 200,
        "fat_target_g": 60,
        "meal_style": "simple",
        "meals_per_day": 3,
        "start_date": "2026-06-10",
        "num_days": 1,
        "special_requests": "",
        "bulk_prep_enabled": False,
        "bulk_prep_pct": 0.5,
        "bulk_repeat_all_days": False,
        "pantry_inventory": [],
        "planned_days": [],
        "nutrition_summaries": [],
        "human_feedback": None,
        "current_agent": "orchestrator",
    }
    state.update(over)
    return state


def _patch_llm(monkeypatch, *, day_planner=None, range_planner=None):
    """Make `mp.make_llm(...)` return a fake LLM that dispatches on the schema.

    `_RangePlan` -> range_planner (bulk path); `_DayPlan` -> day_planner (per-day path).
    Unset paths get an _ExplodingPlanner so a wrong code path fails loudly.
    """
    day = day_planner if day_planner is not None else _ExplodingPlanner()
    rng = range_planner if range_planner is not None else _ExplodingPlanner()

    class _LLM:
        def with_structured_output(self, schema):
            return rng if schema is mp._RangePlan else day

    monkeypatch.setattr(mp, "make_llm", lambda *a, **k: _LLM())


class TestSchemaValidation:
    def test_day_plan_rejects_empty_meals(self):
        with pytest.raises(ValidationError):
            mp._DayPlan(date="2026-06-10", meals=[])

    def test_day_plan_accepts_at_least_one_meal(self):
        day = mp._DayPlan(date="2026-06-10", meals=[_meal(1)])
        assert len(day.meals) == 1


class TestMealPlannerNode:
    """Non-bulk path generates one day per LLM call via the day planner (parallel)."""

    def test_parses_structured_output(self, monkeypatch):
        day = mp._DayPlan(date="2026-06-10", meals=[_meal(1, "Eggs"), _meal(2, "Chicken")])
        _patch_llm(monkeypatch, day_planner=_FakeDayPlanner(day))

        out = mp.meal_planner_node(_base_state())

        assert len(out["planned_days"]) == 1
        meals = out["planned_days"][0]["meals"]
        assert [m["recipe_name"] for m in meals] == ["Eggs", "Chicken"]
        assert out["current_agent"] == "orchestrator"
        assert out["human_feedback"] is None
        assert "1 days" in out["messages"][0].content

    def test_forces_requested_date(self, monkeypatch):
        # Even if the model echoes a wrong date, the node overrides it.
        day = mp._DayPlan(date="1999-01-01", meals=[_meal(1)])
        _patch_llm(monkeypatch, day_planner=_FakeDayPlanner(day))

        out = mp.meal_planner_node(_base_state(start_date="2026-06-10", num_days=1))
        assert out["planned_days"][0]["date"] == "2026-06-10"

    def test_parallel_generates_each_day(self, monkeypatch):
        # 3 days -> 3 calls -> 3 dated days in order.
        _patch_llm(monkeypatch, day_planner=_FakeDayPlanner(None))

        out = mp.meal_planner_node(_base_state(start_date="2026-06-10", num_days=3))
        dates = [d["date"] for d in out["planned_days"]]
        assert dates == ["2026-06-10", "2026-06-11", "2026-06-12"]

    def test_dumps_to_plain_dicts(self, monkeypatch):
        day = mp._DayPlan(date="2026-06-10", meals=[_meal(1)])
        _patch_llm(monkeypatch, day_planner=_FakeDayPlanner(day))

        out = mp.meal_planner_node(_base_state())
        assert isinstance(out["planned_days"][0], dict)
        assert isinstance(out["planned_days"][0]["meals"][0], dict)

    def test_passes_special_requests_into_prompt(self, monkeypatch):
        captured = {}

        class CapturingPlanner:
            def invoke(self, messages):
                captured["system"] = messages[0].content
                return mp._DayPlan(date="2026-06-10", meals=[_meal(1)])

        _patch_llm(monkeypatch, day_planner=CapturingPlanner())
        mp.meal_planner_node(_base_state(special_requests="no dairy, extra spicy"))

        assert "no dairy, extra spicy" in captured["system"]

    def test_revision_feedback_in_human_message(self, monkeypatch):
        captured = {}

        class CapturingPlanner:
            def invoke(self, messages):
                captured["human"] = messages[1].content
                return mp._DayPlan(date="2026-06-10", meals=[_meal(1)])

        _patch_llm(monkeypatch, day_planner=CapturingPlanner())
        mp.meal_planner_node(_base_state(human_feedback="make it vegetarian"))

        assert "make it vegetarian" in captured["human"]

    def test_bulk_path_uses_range_planner(self, monkeypatch):
        # Bulk prep must plan all days in one coordinated call via the range planner.
        fake = mp._RangePlan(days=[
            mp._DayPlan(date="2026-06-10", meals=[_meal(1, bulk=True)]),
            mp._DayPlan(date="2026-06-11", meals=[_meal(1, bulk=True)]),
        ])
        # The day planner is left as _ExplodingPlanner: if the bulk path wrongly used
        # it, the test would fail loudly (no network).
        _patch_llm(monkeypatch, range_planner=_FakePlanner(fake))

        out = mp.meal_planner_node(_base_state(num_days=2, bulk_prep_enabled=True))
        assert len(out["planned_days"]) == 2

    def test_missing_key_raises(self, monkeypatch):
        # No mock: with no provider/key the real make_llm must reject the request so
        # BYOK is enforced rather than silently falling back to an env key.
        from meal_planner.llm import LLMConfigError

        with pytest.raises(LLMConfigError):
            mp.meal_planner_node(_base_state())


class TestGraphFlowMocked:
    def test_full_flow_pauses_at_review(self, monkeypatch):
        """orchestrator -> meal_planner -> nutrition -> human_review (interrupt)."""
        day = mp._DayPlan(date="2026-06-10", meals=[_meal(1), _meal(2), _meal(3)])
        _patch_llm(monkeypatch, day_planner=_FakeDayPlanner(day))

        from langgraph.checkpoint.memory import MemorySaver
        from langgraph.graph import END, StateGraph
        from meal_planner.graph import human_review_node, _route_after_human_review, _route_from_orchestrator
        from meal_planner.agents.nutrition import nutrition_node
        from meal_planner.agents.orchestrator import orchestrator_node
        from meal_planner.state import RangePlanState

        # Rebuild the graph with an in-memory checkpointer (no disk side effects).
        g = StateGraph(RangePlanState)
        g.add_node("orchestrator", orchestrator_node)
        g.add_node("meal_planner", mp.meal_planner_node)
        g.add_node("nutrition", nutrition_node)
        g.add_node("human_review", human_review_node)
        g.set_entry_point("orchestrator")
        g.add_conditional_edges("orchestrator", _route_from_orchestrator, {
            "meal_planner": "meal_planner", "nutrition": "nutrition", "human_review": "human_review",
        })
        g.add_edge("meal_planner", "orchestrator")
        g.add_edge("nutrition", "orchestrator")
        g.add_conditional_edges("human_review", _route_after_human_review, {END: END, "meal_planner": "meal_planner"})
        app = g.compile(checkpointer=MemorySaver())

        cfg = {"configurable": {"thread_id": "mock-flow"}}
        visited = []
        for chunk in app.stream(_base_state(), cfg, stream_mode="updates"):
            visited.extend(chunk.keys())

        snap = app.get_state(cfg)
        assert snap.next == ("human_review",)            # paused at interrupt
        assert len(snap.values["planned_days"]) == 1
        assert len(snap.values["nutrition_summaries"]) == 1
        assert "meal_planner" in visited and "nutrition" in visited


class TestByokKeySafety:
    def test_key_not_persisted_in_checkpoints(self, monkeypatch, tmp_path):
        """The BYOK key rides in config.configurable; it must never reach the
        SqliteSaver checkpoint rows (state blobs or metadata)."""
        import sqlite3

        from langgraph.checkpoint.sqlite import SqliteSaver
        from langgraph.graph import END, StateGraph
        from meal_planner.graph import (
            human_review_node,
            _route_after_human_review,
            _route_from_orchestrator,
        )
        from meal_planner.agents.nutrition import nutrition_node
        from meal_planner.agents.orchestrator import orchestrator_node
        from meal_planner.state import RangePlanState

        day = mp._DayPlan(date="2026-06-10", meals=[_meal(1)])
        _patch_llm(monkeypatch, day_planner=_FakeDayPlanner(day))

        g = StateGraph(RangePlanState)
        g.add_node("orchestrator", orchestrator_node)
        g.add_node("meal_planner", mp.meal_planner_node)
        g.add_node("nutrition", nutrition_node)
        g.add_node("human_review", human_review_node)
        g.set_entry_point("orchestrator")
        g.add_conditional_edges("orchestrator", _route_from_orchestrator, {
            "meal_planner": "meal_planner", "nutrition": "nutrition", "human_review": "human_review",
        })
        g.add_edge("meal_planner", "orchestrator")
        g.add_edge("nutrition", "orchestrator")
        g.add_conditional_edges("human_review", _route_after_human_review, {END: END, "meal_planner": "meal_planner"})

        db_file = tmp_path / "checkpoints.db"
        conn = sqlite3.connect(str(db_file), check_same_thread=False)
        app = g.compile(checkpointer=SqliteSaver(conn))

        from meal_planner.llm import reset_request_creds, set_request_creds

        secret = "sk-ant-SUPERSECRETKEY-DO-NOT-PERSIST"
        cfg = {"configurable": {"thread_id": "sec"}}
        # Creds ride the ContextVar (request-scoped), never the persisted config.
        token = set_request_creds("anthropic", secret)
        try:
            for _ in app.stream(_base_state(), cfg, stream_mode="updates"):
                pass
        finally:
            reset_request_creds(token)

        # Scan every cell of every table for the secret, as text and as bytes.
        tables = [r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()]
        assert tables, "checkpointer wrote no tables"
        secret_b = secret.encode()
        for tbl in tables:
            for row in conn.execute(f"SELECT * FROM {tbl}").fetchall():
                for cell in row:
                    if isinstance(cell, (bytes, bytearray)):
                        assert secret_b not in bytes(cell)
                    elif cell is not None:
                        assert secret not in str(cell)
        conn.close()


class _FakePlanner:
    """Stands in for the range planner (returns a full _RangePlan)."""
    def __init__(self, plan):
        self._plan = plan

    def invoke(self, _messages):
        return self._plan


class _FakeDayPlanner:
    """Stands in for the day planner (returns one _DayPlan per call).

    If constructed with None, fabricates a single-meal day each call so parallel
    multi-day generation can be exercised without pinning a specific date.
    """
    def __init__(self, day):
        self._day = day

    def invoke(self, _messages):
        if self._day is not None:
            return self._day
        return mp._DayPlan(date="2026-01-01", meals=[_meal(1)])


class _ExplodingPlanner:
    def invoke(self, _messages):
        raise AssertionError("wrong planner used")
