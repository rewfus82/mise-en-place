from __future__ import annotations
import sqlite3
from datetime import date

from meal_planner.mcp_servers.pantry_server import get_inventory
from backend.services.food_units import (
    GRAMS as _GRAMS,
    find_match as _find_pantry_match,
    norm_name as _norm_name,
    norm_unit as _norm_unit,
    parse_amount as _parse_amount,
    parse_combined as _parse_numeric,
    to_grams as _to_grams,
)


def compute_deficit(conn: sqlite3.Connection) -> list[dict]:
    today = date.today().isoformat()

    days = conn.execute(
        "SELECT id, date FROM meal_days WHERE date >= ? AND status = 'planned'",
        (today,),
    ).fetchall()
    if not days:
        return []

    day_ids = [d["id"] for d in days]
    date_by_day_id = {d["id"]: d["date"] for d in days}

    placeholders = ",".join("?" * len(day_ids))
    rows = conn.execute(
        f"""
        SELECT mi.item, mi.quantity, mi.unit, mi.quantity_type, dm.day_id
        FROM meal_ingredients mi
        JOIN day_meals dm ON mi.meal_id = dm.id
        WHERE dm.day_id IN ({placeholders})
          AND mi.quantity_type != 'trace'
        ORDER BY dm.day_id ASC
        """,
        day_ids,
    ).fetchall()

    # Aggregate needs per normalized ingredient name.
    needed: dict[str, dict] = {}
    for row in rows:
        key = _norm_name(row["item"])
        if not key:
            continue
        amount = _parse_amount(row["quantity"])
        unit = _norm_unit(row["unit"])
        grams = _to_grams(amount, unit)

        if key not in needed:
            needed[key] = {
                "item": row["item"],
                "display_amount": amount,
                "display_unit": unit,
                "total_g": grams,
                "needed_by_date": date_by_day_id[row["day_id"]],
                "quantity_type": row["quantity_type"],
            }
        else:
            info = needed[key]
            # Accumulate grams when both sides are mass/volume.
            if grams is not None and info["total_g"] is not None:
                info["total_g"] += grams
            # Accumulate count-style amounts when units match and aren't mass/volume.
            elif (
                grams is None and info["total_g"] is None
                and amount is not None and info["display_amount"] is not None
                and unit == info["display_unit"]
            ):
                info["display_amount"] += amount

    pantry_by_name = {_norm_name(p["item"]): p for p in get_inventory()}
    ignored = {
        _norm_name(r["item"])
        for r in conn.execute("SELECT item FROM grocery_overrides WHERE ignored = 1").fetchall()
    }

    results = []
    for key, info in needed.items():
        if key in ignored:
            continue

        pantry_item = _find_pantry_match(key, pantry_by_name)

        if pantry_item is not None:
            # Pantry stores amount + unit in one string, e.g. "10 lb".
            p_amount, p_unit = _parse_numeric(pantry_item["quantity"])
            have_g = _to_grams(p_amount, p_unit)
            # Both measurable in mass/volume → real deficit math.
            if info["total_g"] is not None and have_g is not None:
                deficit_g = info["total_g"] - have_g
                if deficit_g <= 0:
                    continue  # covered
                unit = info["display_unit"] or "g"
                factor = _GRAMS.get(unit, 1)
                results.append(_result(info, f"{deficit_g / factor:.1f}", unit, True))
            else:
                # Owned but not dimensionally comparable → assume you have enough.
                # (This is what fixes "telling me to buy things I already have".)
                continue
        else:
            # Not in pantry — list it. Prefer the accumulated mass/volume total;
            # fall back to a parsed count; else mark it for a manual check.
            if info["total_g"] is not None:
                unit = info["display_unit"] or "g"
                factor = _GRAMS.get(unit, 1)
                amount_str = f"{info['total_g'] / factor:.2f}".rstrip("0").rstrip(".")
                results.append(_result(info, amount_str, unit, True))
            elif info["display_amount"] is not None:
                amount_str = f"{info['display_amount']:.2f}".rstrip("0").rstrip(".")
                results.append(_result(info, amount_str, info["display_unit"], True))
            else:
                results.append(_result(info, "some", info["display_unit"], False))

    results.sort(key=lambda x: x["needed_by_date"])
    return results


def _result(info: dict, quantity_needed: str, unit: str | None, calculable: bool) -> dict:
    return {
        "ingredient": info["item"],
        "quantity_needed": quantity_needed,
        "unit": unit,
        "needed_by_date": info["needed_by_date"],
        "deficit_calculable": calculable,
        "quantity_type": info["quantity_type"],
    }
