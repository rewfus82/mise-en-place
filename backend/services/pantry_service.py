from __future__ import annotations
import sqlite3

from meal_planner.mcp_servers.pantry_server import get_inventory, remove_items, update_quantity
from backend.services.food_units import (
    GRAMS,
    find_match,
    norm_name,
    norm_unit,
    parse_amount,
    parse_combined,
    to_grams,
)


def compute_depletion(day_id: int, conn: sqlite3.Connection) -> dict:
    """
    For all eaten meals on day_id, split ingredients into:
    - auto_deducted: exact quantity_type with a parseable qty matched to a pantry
      item → deducted from the pantry
    - needs_confirmation: partial/unknown, or anything we can't deduct cleanly
    trace items are silently skipped.
    """
    rows = conn.execute(
        """
        SELECT mi.item, mi.quantity, mi.unit, mi.quantity_type
        FROM meal_ingredients mi
        JOIN day_meals dm ON mi.meal_id = dm.id
        WHERE dm.day_id = ? AND dm.eaten = 1 AND mi.quantity_type != 'trace'
        """,
        (day_id,),
    ).fetchall()

    auto_deducted: list[dict] = []
    needs_confirmation: list[dict] = []
    pantry_by_name = {norm_name(p["item"]): p for p in get_inventory()}

    for row in rows:
        item, qty_str, unit, qty_type = row["item"], row["quantity"], row["unit"], row["quantity_type"]

        if qty_type in ("partial", "unknown"):
            needs_confirmation.append({"item": item, "quantity": qty_str, "unit": unit})
            continue

        # exact — amount from the quantity column, unit from the unit column.
        amount = parse_amount(qty_str)
        used_unit = norm_unit(unit)
        pantry_item = find_match(norm_name(item), pantry_by_name)

        if amount is None or pantry_item is None:
            needs_confirmation.append({"item": item, "quantity": qty_str, "unit": unit})
            continue

        # Pantry stores amount + unit together, e.g. "10 lb".
        pantry_amount, pantry_unit = parse_combined(pantry_item["quantity"])
        if pantry_amount is None:
            needs_confirmation.append({"item": item, "quantity": qty_str, "unit": unit})
            continue

        used_g = to_grams(amount, used_unit)
        have_g = to_grams(pantry_amount, pantry_unit)

        if used_g is not None and have_g is not None:
            # Both mass/volume — real deduction.
            remaining_g = have_g - used_g
            if remaining_g <= 0:
                remove_items([pantry_item["item"]])
            else:
                out_unit = pantry_unit or "g"
                factor = GRAMS.get(out_unit, 1)
                update_quantity(pantry_item["item"], f"{remaining_g / factor:.1f} {out_unit}")
            auto_deducted.append({"item": item, "deducted": f"{amount} {used_unit or ''}".strip()})

        elif used_unit is None and pantry_unit is None:
            # Both count-based — deduct directly.
            remaining = pantry_amount - amount
            if remaining <= 0:
                remove_items([pantry_item["item"]])
            else:
                update_quantity(pantry_item["item"], f"{remaining:g}")
            auto_deducted.append({"item": item, "deducted": f"{amount:g}"})

        else:
            # Mismatched dimensions (e.g. need cups, have count) — ask the user.
            needs_confirmation.append({"item": item, "quantity": qty_str, "unit": unit})

    conn.commit()
    return {"auto_deducted": auto_deducted, "needs_confirmation": needs_confirmation}
