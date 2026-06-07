import sqlite3
from pathlib import Path

from langchain_core.messages import AIMessage
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, StateGraph
from langgraph.types import interrupt

from meal_planner.agents.meal_planner import meal_planner_node
from meal_planner.agents.nutrition import nutrition_node
from meal_planner.agents.orchestrator import orchestrator_node
from meal_planner.state import RangePlanState

_DB_PATH = Path(__file__).parent.parent / "data" / "checkpoints.db"


def human_review_node(state: RangePlanState) -> dict:
    planned_days = state.get("planned_days", [])
    nutrition = state.get("nutrition_summaries", [])

    day_lines = []
    for day in planned_days:
        meal_names = ", ".join(m.get("recipe_name", "") for m in day.get("meals", []))
        day_lines.append(f"  {day['date']}: {meal_names}")

    review_prompt = (
        f"\n{'=' * 50}\n"
        f"YOUR PLAN — {len(planned_days)} day(s)\n"
        + "\n".join(day_lines)
        + "\n\nNUTRITION SUMMARY\n"
        + "\n".join(
            f"  {s['date']}: {s.get('total_calories', 0):.0f} kcal · "
            f"{s.get('total_protein_g', 0):.0f}g protein"
            for s in nutrition
        )
        + f"\n{'=' * 50}\n"
        + "Type 'approve' to confirm, or describe changes you'd like:"
    )

    feedback: str = interrupt(review_prompt)

    approved = feedback.lower().strip() in {
        "approve", "approved", "yes", "y", "looks good", "ok", "lgtm",
    }

    return {
        "human_feedback": None if approved else feedback,
        "awaiting_human_approval": False,
        "messages": [
            AIMessage(
                content=(
                    "Plan approved!"
                    if approved
                    else f"Got it — revising: {feedback}"
                )
            )
        ],
    }


def _route_from_orchestrator(state: RangePlanState) -> str:
    return state.get("current_agent", "orchestrator")


def _route_after_human_review(state: RangePlanState) -> str:
    return END if state.get("human_feedback") is None else "meal_planner"


def build_range_graph():
    graph = StateGraph(RangePlanState)

    graph.add_node("orchestrator", orchestrator_node)
    graph.add_node("meal_planner", meal_planner_node)
    graph.add_node("nutrition", nutrition_node)
    graph.add_node("human_review", human_review_node)

    graph.set_entry_point("orchestrator")

    graph.add_conditional_edges(
        "orchestrator",
        _route_from_orchestrator,
        {
            "meal_planner": "meal_planner",
            "nutrition": "nutrition",
            "human_review": "human_review",
        },
    )

    graph.add_edge("meal_planner", "orchestrator")
    graph.add_edge("nutrition", "orchestrator")

    graph.add_conditional_edges(
        "human_review",
        _route_after_human_review,
        {END: END, "meal_planner": "meal_planner"},
    )

    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(_DB_PATH), check_same_thread=False)
    checkpointer = SqliteSaver(conn)

    return graph.compile(checkpointer=checkpointer)
