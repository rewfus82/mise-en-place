from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException

from backend.schemas.pantry import (
    AddPantryRequest,
    ParseImageRequest,
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


def _run_parse(content, provider: str, key: str) -> ParsePantryResponse:
    """Parse + add, mapping provider errors to clean HTTP responses.

    A bad/missing key becomes a 400 whose message trips the frontend's key-modal
    heuristic; other provider/vision failures become a 502 rather than a raw 500.
    """
    from meal_planner.agents.pantry_parser import parse_and_add
    from meal_planner.llm import LLMConfigError

    try:
        result = parse_and_add(content, provider, key)
    except LLMConfigError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:  # noqa: BLE001 — surface provider errors cleanly
        msg = str(exc).lower()
        if any(k in msg for k in ("api key", "authentication", "401", "invalid x-api-key", "unauthorized")):
            raise HTTPException(status_code=400, detail="Invalid or missing API key for the selected provider.")
        raise HTTPException(status_code=502, detail=f"Could not read the input: {exc}")
    return ParsePantryResponse(**result)


@router.post("/parse", response_model=ParsePantryResponse)
def parse_pantry(
    body: ParsePantryRequest,
    x_llm_provider: str = Header(default=""),
    x_llm_key: str = Header(default=""),
):
    return _run_parse(body.text, x_llm_provider, x_llm_key)


@router.post("/parse-image", response_model=ParsePantryResponse)
def parse_pantry_image(
    body: ParseImageRequest,
    x_llm_provider: str = Header(default=""),
    x_llm_key: str = Header(default=""),
):
    """Extract pantry items from a photo (groceries / fridge / receipt) via vision."""
    content = [
        {
            "type": "text",
            "text": (
                "This is a photo of the user's groceries, pantry, fridge, or a "
                "receipt. Identify every food item you can see and extract it. "
                "Include quantities when visible (count items, read labels)."
            ),
        },
        {
            "type": "image_url",
            "image_url": {"url": f"data:{body.mime_type};base64,{body.data}"},
        },
    ]
    return _run_parse(content, x_llm_provider, x_llm_key)


@router.post("/deplete", response_model=dict)
def deplete_pantry(body: dict):
    """Manually remove items the user confirmed they finished (ambiguous qty prompt)."""
    items = body.get("items", [])
    return remove_items(items)
