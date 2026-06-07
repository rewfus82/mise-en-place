"""
LangChain tool wrappers around the pantry MCP server.
Agents call these — they never touch the SQLite DB directly.
"""
import subprocess
import sys
from pathlib import Path

from langchain_core.tools import tool

from meal_planner.mcp_servers.pantry_server import (
    add_items,
    check_item,
    clear_inventory,
    get_inventory,
    remove_items,
)


@tool
def tool_get_inventory() -> list[dict]:
    """Return all items currently in the pantry."""
    return get_inventory()


@tool
def tool_add_items(items: list[dict]) -> dict:
    """
    Add parsed food items to the pantry.
    Each item must have: item (str), quantity (str), category (str).
    """
    return add_items(items)


@tool
def tool_remove_items(item_names: list[str]) -> dict:
    """Remove items from the pantry by name."""
    return remove_items(item_names)


@tool
def tool_check_item(item_name: str) -> bool:
    """Check whether a specific item exists in the pantry."""
    return check_item(item_name)


@tool
def tool_clear_inventory() -> dict:
    """Clear all pantry items. Call at the start of a new planning session."""
    return clear_inventory()


PANTRY_TOOLS = [
    tool_get_inventory,
    tool_add_items,
    tool_remove_items,
    tool_check_item,
    tool_clear_inventory,
]
