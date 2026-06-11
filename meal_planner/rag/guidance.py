"""Evidence retrieval for grounding meal generation.

The Nutrition Coach answers a user's question; this module instead pulls the
guidelines relevant to *the plan being generated* (driven by the user's goal and
protein target) and packs them into a compact block for the meal-planner system
prompt. Retrieved once per plan and reused across the per-day calls, so grounding
adds a single retrieval, not one per day.

Grounding degrades gracefully: any retrieval failure (e.g. a missing knowledge.db
in a stripped deploy) returns an empty block so meal generation still runs.
"""
from __future__ import annotations

from langchain_core.messages import HumanMessage, SystemMessage

from meal_planner.llm import coerce_text, make_llm
from meal_planner.rag.retriever import retrieve

# Goal -> the phrase that steers retrieval toward the right evidence.
_GOAL_PHRASES = {
    "cut": "fat loss in a caloric deficit while preserving lean muscle mass",
    "lose": "fat loss in a caloric deficit while preserving lean muscle mass",
    "lose_fat": "fat loss in a caloric deficit while preserving lean muscle mass",
    "bulk": "muscle gain in a caloric surplus",
    "gain": "muscle gain and building lean mass in a caloric surplus",
    "gain_muscle": "muscle gain and building lean mass in a caloric surplus",
    "maintain": "maintaining muscle and body composition",
}


def _query(goal: str, protein_target_g: int) -> str:
    phrase = _GOAL_PHRASES.get((goal or "").lower(), _GOAL_PHRASES["maintain"])
    return (
        f"protein intake and meal planning for {phrase}; "
        f"daily protein around {protein_target_g} grams; "
        f"distributing protein across meals"
    )


def guideline_block(
    goal: str, protein_target_g: int, *, k: int = 3
) -> tuple[str, list[dict]]:
    """Return (system-prompt block, distinct sources) for a plan.

    Sources are dicts ({citation, title, url}), deduped by citation, so the review
    UI can show and link the evidence the plan was grounded in. Empty block + empty
    list when nothing relevant is retrievable.
    """
    try:
        chunks = retrieve(_query(goal, protein_target_g), k=k)
    except Exception:  # noqa: BLE001 — grounding is best-effort, never fatal
        return "", []
    if not chunks:
        return "", []

    lines = [f"- {c.text.strip()} [{c.citation()}]" for c in chunks]
    block = (
        "Evidence-based guidelines from peer-reviewed sports-nutrition position "
        "stands. Follow them where relevant while hitting the macro targets:\n"
        + "\n".join(lines)
    )

    sources: list[dict] = []
    seen: set[str] = set()
    for c in chunks:
        cite = c.citation()
        if cite in seen:
            continue
        seen.add(cite)
        sources.append({"citation": cite, "title": c.title, "url": c.url})
    return block, sources


_RATIONALE_SYSTEM = (
    "You are a sports-nutrition coach. A meal plan has ALREADY been generated for the "
    "user (its shape is given below). In ONE or TWO sentences, explain how that plan's "
    "design reflects the evidence-based guidance — reference concrete numbers (like "
    "protein per kilogram or per day) where relevant. Write it as a direct statement to "
    "the user, starting with \"This plan\". Do NOT ask the user for anything, do NOT "
    "request their meals, and do NOT use citation brackets or list sources. Never "
    "exceed two sentences."
)


def plan_rationale(
    goal: str,
    protein_target_g: int,
    calorie_target: int,
    guidelines_block: str,
    provider: str,
    api_key: str,
    plan_summary: str = "",
) -> str:
    """A short, grounded 'why this plan' summary from the retrieved evidence.

    `plan_summary` is a compact description of the already-generated plan (day count,
    meals/day, average protein) so the model explains a concrete plan rather than
    asking the user for one.

    Best-effort and non-fatal: returns "" when there's no evidence, no BYOK creds,
    or the model call fails — meal generation never depends on it.
    """
    if not guidelines_block or not provider or not api_key:
        return ""
    try:
        llm = make_llm(provider, api_key, role="light")
        human = HumanMessage(
            content=(
                f"Goal: {goal}. Daily targets: {calorie_target} kcal, "
                f"{protein_target_g} g protein.\n"
                f"Generated plan: {plan_summary or 'a multi-day plan meeting these targets'}.\n\n"
                f"{guidelines_block}"
            )
        )
        resp = llm.invoke([SystemMessage(content=_RATIONALE_SYSTEM), human])
        return coerce_text(getattr(resp, "content", "")).strip()
    except Exception:  # noqa: BLE001 — rationale is a nicety, never fatal
        return ""
