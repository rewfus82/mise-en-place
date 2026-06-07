from __future__ import annotations
import sqlite3

from fastapi import APIRouter, Depends

from backend.database import get_db
from backend.schemas.planning import GroceryItemOut, MarkBoughtRequest
from backend.services.grocery_service import compute_deficit
from meal_planner.mcp_servers.pantry_server import add_items

router = APIRouter(tags=["grocery"])


@router.get("", response_model=list[GroceryItemOut])
def get_grocery_list(conn: sqlite3.Connection = Depends(get_db)):
    return compute_deficit(conn)


@router.patch("/{item_name}/ignore", response_model=dict)
def ignore_item(item_name: str, conn: sqlite3.Connection = Depends(get_db)):
    conn.execute(
        "INSERT OR REPLACE INTO grocery_overrides (item, ignored) VALUES (?, 1)",
        (item_name.lower(),),
    )
    conn.commit()
    return {"ignored": item_name}


@router.post("/mark-bought", response_model=dict)
def mark_bought(body: MarkBoughtRequest):
    result = add_items([{"item": body.item, "quantity": body.quantity, "category": body.category}])
    return result
