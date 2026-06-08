from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel

from meal_planner.llm import get_request_creds, make_llm
from meal_planner.tools.pantry_tools import tool_add_items, tool_get_inventory

_CATEGORIES = "produce, protein, dairy, grains, canned, frozen, condiments, spices, other"

_SYSTEM = f"""Extract every food item from the user's pantry description.
For each item provide:
- item: food name (lowercase singular — "chicken breast" not "Chicken Breasts")
- quantity: amount they have ("2 lbs", "half a bag", "unknown" if not stated)
- category: one of [{_CATEGORIES}]

Be thorough — capture every food item mentioned, even if described vaguely."""


class _Item(BaseModel):
    item: str
    quantity: str
    category: str


class _ParsedPantry(BaseModel):
    items: list[_Item]


def make_parser(provider: str, api_key: str):
    """Build a structured pantry parser bound to the caller's provider + key (BYOK)."""
    return make_llm(provider, api_key, role="light").with_structured_output(_ParsedPantry)


def pantry_parser_node(state: dict, config: RunnableConfig | None = None) -> dict:
    user_input = state["messages"][-1].content

    parser = make_parser(*get_request_creds())
    parsed: _ParsedPantry = parser.invoke(
        [SystemMessage(content=_SYSTEM), HumanMessage(content=user_input)]
    )

    items = [item.model_dump() for item in parsed.items]
    result = tool_add_items.invoke({"items": items})
    inventory = tool_get_inventory.invoke({})

    msg = (
        f"Pantry scanned: added {len(result['added'])} items "
        f"({len(result['skipped'])} already on file). "
        f"Total inventory: {len(inventory)} items."
    )

    return {
        "pantry_inventory": inventory,
        "current_agent": "orchestrator",
        "messages": [AIMessage(content=msg)],
    }
