from langchain_core.messages import AIMessage

from meal_planner.state import RangePlanState


def orchestrator_node(state: RangePlanState) -> dict:
    if not state.get("planned_days"):
        return {"current_agent": "meal_planner", "messages": [AIMessage(content="Creating your meal plan...")]}
    if not state.get("nutrition_summaries"):
        return {"current_agent": "nutrition", "messages": [AIMessage(content="Running nutrition check...")]}
    return {"current_agent": "human_review", "messages": [AIMessage(content="Ready for your review.")]}
