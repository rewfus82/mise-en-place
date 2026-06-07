"""Shared food quantity parsing / unit normalization / name matching.

Used by both grocery_service (deficit) and pantry_service (depletion) so the two
stay consistent. Meal ingredients store amount and unit in SEPARATE columns
(quantity='1.5', unit='cups'); the pantry stores them in ONE string ('10 lb').
"""
from __future__ import annotations

import re

# Mass/volume units reduced to a common numeric scale (grams ≈ ml — fine for a
# rough "do I have enough"). Count-style units (whole, strips, cans…) are absent
# on purpose: they can't be compared dimensionally to weights.
GRAMS: dict[str, float] = {
    "g": 1, "gram": 1,
    "kg": 1000, "kilogram": 1000,
    "oz": 28.3495, "ounce": 28.3495,
    "lb": 453.592, "pound": 453.592,
    "ml": 1, "milliliter": 1,
    "l": 1000, "liter": 1000,
    "cup": 240,
    "tbsp": 15, "tablespoon": 15,
    "tsp": 5, "teaspoon": 5,
}

_UNIT_ALIASES = {
    "grams": "g", "kgs": "kg", "kilograms": "kg",
    "ozs": "oz", "ounces": "oz",
    "lbs": "lb", "pounds": "pound",
    "milliliters": "ml", "liters": "l", "litres": "l", "litre": "l",
    "cups": "cup",
    "tablespoons": "tbsp", "tbs": "tbsp",
    "teaspoons": "tsp",
}


def parse_amount(raw: str | None) -> float | None:
    """'2', '1.5', '1/4', '1 1/2' → float. None if not numeric."""
    s = (raw or "").strip()
    if not s:
        return None
    total = 0.0
    for part in s.split():
        try:
            if "/" in part:
                num, den = part.split("/", 1)
                total += float(num) / float(den)
            else:
                total += float(part)
        except (ValueError, ZeroDivisionError):
            return None
    return total


def norm_unit(unit: str | None) -> str | None:
    """First word of a unit field, lowercased + singularized ('cups chopped' → 'cup')."""
    words = (unit or "").strip().lower().split()
    if not words:
        return None
    return _UNIT_ALIASES.get(words[0], words[0])


def norm_name(name: str) -> str:
    """Normalize an item name for matching: drop parentheticals, punctuation, plural 's'."""
    n = re.sub(r"\(.*?\)", "", name.lower())
    n = re.sub(r"[^a-z0-9 ]", " ", n)
    words = [w for w in n.split() if w]
    if words and len(words[-1]) > 3 and words[-1].endswith("s"):
        words[-1] = words[-1][:-1]
    return " ".join(words)


def to_grams(amount: float | None, unit: str | None) -> float | None:
    if amount is None or unit is None:
        return None
    factor = GRAMS.get(unit)
    return amount * factor if factor is not None else None


def parse_combined(quantity: str | None) -> tuple[float | None, str | None]:
    """Parse a single 'amount unit' string like '10 lb' or '1/2 cup' (pantry format)."""
    m = re.match(r"^\s*([\d./ ]+?)\s*([a-z]*)\s*$", (quantity or "").strip().lower())
    if not m:
        return None, None
    return parse_amount(m.group(1)), norm_unit(m.group(2))


def find_match(need_name: str, by_name: dict[str, dict]) -> dict | None:
    """Exact normalized match, else token-subset containment either direction."""
    if need_name in by_name:
        return by_name[need_name]
    need_words = set(need_name.split())
    if not need_words:
        return None
    for cand_name, cand in by_name.items():
        cand_words = set(cand_name.split())
        if cand_words and (cand_words <= need_words or need_words <= cand_words):
            return cand
    return None
