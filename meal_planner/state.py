from typing import Annotated, TypedDict
from langgraph.graph.message import add_messages


class RangePlanState(TypedDict):
    messages: Annotated[list, add_messages]

    # User profile — all resolved before graph call, no NULLs for targets
    skill_level: str
    max_cook_time_minutes: int | None
    daily_budget: float | None
    dietary_restrictions: list[str]
    food_allergies: str
    calorie_target: int
    protein_target_g: int
    carbs_target_g: int | None
    fat_target_g: int | None
    meal_style: str          # "bland" | "simple" | "recipes" | "macros_only"
    meals_per_day: int
    goal: str                # "cut" | "bulk" | "maintain" — steers evidence grounding

    # Planning scope
    start_date: str          # ISO date of first day being planned
    num_days: int
    special_requests: str    # free-text extra instructions from the user

    # Bulk prep configuration
    bulk_prep_enabled: bool
    bulk_prep_pct: float     # 0.0–1.0, fraction of meals to bulk prep
    bulk_repeat_all_days: bool

    # Pantry
    pantry_inventory: list[dict]

    # Output
    planned_days: list[dict]        # [{date, meals: [{meal_number, ...}]}]
    nutrition_summaries: list[dict] # per-day nutrition totals
    applied_guidelines: list[dict]  # evidence sources the plan was grounded in
    guideline_summary: str          # grounded "why this plan" rationale

    # Human-in-the-loop
    awaiting_human_approval: bool
    human_feedback: str | None

    # Routing
    current_agent: str
    error: str | None
