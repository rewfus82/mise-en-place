# load_dotenv must run before any agent module is imported,
# because ChatAnthropic reads ANTHROPIC_API_KEY at class instantiation time.
from dotenv import load_dotenv
load_dotenv()

import uuid
from datetime import date

from langchain_core.messages import HumanMessage
from langgraph.types import Command

from meal_planner.graph import build_graph
from meal_planner.tracing import setup_tracing


def _ask(prompt: str, default: str = "") -> str:
    value = input(f"{prompt} [{default}]: ").strip()
    return value or default


def _ask_int(prompt: str, default: int) -> int:
    raw = input(f"{prompt} [{default}]: ").strip()
    try:
        return int(raw) if raw else default
    except ValueError:
        return default


def _ask_float(prompt: str, default: str = "") -> float | None:
    raw = input(f"{prompt} [{default or 'skip'}]: ").strip()
    if not raw:
        return None
    try:
        return float(raw)
    except ValueError:
        return None


def collect_preferences() -> dict:
    print("\n=== mise-en-place | AI Meal Planner ===\n")

    household_size = _ask_int("How many people are you cooking for?", 2)
    skill_level = _ask("Cooking skill level (beginner/intermediate/advanced)", "intermediate")
    max_cook_time = _ask_int("Max cook time per meal (minutes)", 45)
    weekly_budget = _ask_float("Weekly grocery budget in $ (press Enter to skip)")
    requested_meals = _ask_int("How many meals do you want planned this week?", 5)
    plan_start_date = _ask("Plan start date (YYYY-MM-DD)", str(date.today()))
    leftovers_raw = _ask("Are leftovers OK? (y/n)", "y")
    leftovers_ok = leftovers_raw.lower() in ("y", "yes")

    print("\nDescribe what's currently in your pantry (freeform — e.g. 'I have chicken")
    print("breasts, olive oil, garlic, pasta, canned tomatoes, and some frozen peas'):")
    pantry_description = input("> ").strip()

    return {
        "household_size": household_size,
        "skill_level": skill_level,
        "max_cook_time_minutes": max_cook_time,
        "weekly_budget": weekly_budget,
        "requested_meals": requested_meals,
        "plan_start_date": plan_start_date,
        "leftovers_ok": leftovers_ok,
        "pantry_description": pantry_description,
    }


def _stream_graph(graph, payload, config):
    """Stream graph events and print agent messages as they arrive."""
    for chunk in graph.stream(payload, config=config, stream_mode="updates"):
        for node_name, updates in chunk.items():
            for msg in updates.get("messages", []):
                content = getattr(msg, "content", "")
                if content:
                    print(f"\n[{node_name}] {content}")


def main():
    tracing = setup_tracing()
    if tracing["enabled"]:
        print(f"LangSmith tracing active → project: {tracing['project']}")

    prefs = collect_preferences()

    initial_state = {
        "messages": [HumanMessage(content=prefs.pop("pantry_description"))],
        "user_preferences": {},
        "household_size": prefs["household_size"],
        "skill_level": prefs["skill_level"],
        "max_cook_time_minutes": prefs["max_cook_time_minutes"],
        "weekly_budget": prefs["weekly_budget"],
        "requested_meals": prefs["requested_meals"],
        "plan_start_date": prefs["plan_start_date"],
        "meals_per_day": {},
        "leftovers_ok": prefs["leftovers_ok"],
        "pantry_inventory": [],
        "planned_meals": [],
        "shopping_list": [],
        "estimated_total_cost": None,
        "budget_remaining": None,
        "nutrition_summary": {},
        "nutrition_approved": False,
        "awaiting_human_approval": False,
        "human_feedback": None,
        "current_agent": "orchestrator",
        "error": None,
    }

    graph = build_graph()
    thread_id = str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}

    print("\nPlanning your meals...\n")
    _stream_graph(graph, initial_state, config)

    # HITL loop — resume until the graph reaches END
    while True:
        snapshot = graph.get_state(config)
        if not snapshot.next:
            break  # graph finished

        # The graph is paused at human_review — show the interrupt value
        interrupts = snapshot.tasks[0].interrupts if snapshot.tasks else []
        if interrupts:
            print(interrupts[0].value)

        user_input = input("> ").strip()
        if not user_input:
            user_input = "approve"

        _stream_graph(graph, Command(resume=user_input), config)

    print("\nDone! Your meal plan is saved. Run again to start a new session.")


if __name__ == "__main__":
    main()
