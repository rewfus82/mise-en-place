from langchain_anthropic import ChatAnthropic
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from pydantic import BaseModel

from meal_planner.state import MealPlannerState

_SYSTEM = """You are a frugal, organized grocery shopper.
Given a meal plan and existing pantry inventory, generate the minimal shopping list.

Rules:
- Omit items already in sufficient quantity in the pantry
- Consolidate the same ingredient across multiple recipes into one line item
- If leftovers_ok is True, buy larger pack sizes where they offer better value
- Estimate realistic US grocery store prices
- Group items by store section (produce, protein, dairy, grains, canned, frozen, condiments, other)"""


class _Item(BaseModel):
    item: str
    quantity: str
    estimated_cost: float
    category: str


class _ShoppingList(BaseModel):
    items: list[_Item]
    total_estimated_cost: float
    items_from_pantry: list[str]


_llm = ChatAnthropic(model="claude-haiku-4-5-20251001")
_extractor = _llm.with_structured_output(_ShoppingList)


def shopping_list_node(state: MealPlannerState) -> dict:
    pantry_str = (
        "\n".join(
            f"- {p['item']}: {p.get('quantity', 'unknown')}"
            for p in state.get("pantry_inventory", [])
        )
        or "Empty pantry"
    )

    meals_str = "\n".join(
        f"- {m.get('recipe_name', 'Unknown')} | {m.get('day', '?')} {m.get('meal_type', '')} "
        f"| {m.get('servings', 1)} servings | pantry items used: {', '.join(m.get('uses_pantry_items', []))}"
        for m in state.get("planned_meals", [])
    )

    budget = state.get("weekly_budget")
    leftovers_ok = state.get("leftovers_ok", True)

    prompt = f"""Meal plan:
{meals_str}

Current pantry:
{pantry_str}

Budget: {"$" + str(budget) if budget else "flexible"}
Leftovers OK: {leftovers_ok}

Generate the complete shopping list for this week."""

    result: _ShoppingList = _extractor.invoke(
        [SystemMessage(content=_SYSTEM), HumanMessage(content=prompt)]
    )

    items = [item.model_dump() for item in result.items]
    total = result.total_estimated_cost
    budget_remaining = (budget - total) if budget else None

    over_under = ""
    if budget_remaining is not None:
        if budget_remaining >= 0:
            over_under = f" — ${budget_remaining:.2f} under budget"
        else:
            over_under = f" — ${abs(budget_remaining):.2f} over budget"

    msg = f"Shopping list ready: {len(items)} items, estimated ${total:.2f}{over_under}."

    return {
        "shopping_list": items,
        "estimated_total_cost": total,
        "budget_remaining": budget_remaining,
        "current_agent": "orchestrator",
        "messages": [AIMessage(content=msg)],
    }
