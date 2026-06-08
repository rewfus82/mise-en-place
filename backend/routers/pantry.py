from __future__ import annotations
import sqlite3

from fastapi import APIRouter, Depends, Header, HTTPException
from langchain_core.messages import HumanMessage, SystemMessage

from backend.database import get_db
from backend.schemas.pantry import (
    AddPantryRequest,
    ParsePantryRequest,
    ParsePantryResponse,
    PantryItemOut,
)
from meal_planner.mcp_servers.pantry_server import (
    add_items,
    clear_inventory,
    get_inventory,
    remove_items,
)

router = APIRouter(tags=["pantry"])


def _get_all() -> list[PantryItemOut]:
    return [PantryItemOut(**item) for item in get_inventory()]


@router.get("", response_model=list[PantryItemOut])
def list_pantry():
    return _get_all()


@router.post("", response_model=dict)
def add_pantry_items(body: AddPantryRequest):
    return add_items(body.items)


@router.delete("/{item_name}", response_model=dict)
def delete_pantry_item(item_name: str):
    result = remove_items([item_name])
    if not result.get("removed"):
        raise HTTPException(status_code=404, detail="Item not found")
    return result


@router.delete("", response_model=dict)
def clear_pantry():
    return clear_inventory()


@router.post("/parse", response_model=ParsePantryResponse)
def parse_pantry(
    body: ParsePantryRequest,
    x_llm_provider: str = Header(default=""),
    x_llm_key: str = Header(default=""),
):
    from meal_planner.agents.pantry_parser import make_parser, _SYSTEM
    from meal_planner.llm import LLMConfigError
    from meal_planner.tools.pantry_tools import tool_add_items

    try:
        parser = make_parser(x_llm_provider, x_llm_key)
    except LLMConfigError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    parsed = parser.invoke([
        SystemMessage(content=_SYSTEM),
        HumanMessage(content=body.text),
    ])
    items = [item.model_dump() for item in parsed.items]
    result = tool_add_items.invoke({"items": items})
    return ParsePantryResponse(
        added=result.get("added", []),
        skipped=result.get("skipped", []),
    )


@router.post("/deplete", response_model=dict)
def deplete_pantry(body: dict):
    """Manually remove items the user confirmed they finished (ambiguous qty prompt)."""
    items = body.get("items", [])
    return remove_items(items)
