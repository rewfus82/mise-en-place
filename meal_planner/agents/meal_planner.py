from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date as _Date, timedelta
from typing import Annotated, Literal

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel, Field

from meal_planner.llm import get_request_creds, make_llm
from meal_planner.state import RangePlanState

_SYSTEM = """You are a professional meal planner for athletes and bodybuilders.
Plan meals for {num_days} consecutive days starting {start_date}.

User profile:
- Cooking for: 1 person
- Skill level: {skill_level}
- Max cook time per meal: {max_cook_time} minutes
- Daily budget: {budget}
- Dietary restrictions: {dietary_restrictions}
- Food allergies/avoid: {food_allergies}
- Daily calorie target: {calorie_target} kcal
- Daily protein target: {protein_target}g
- Meals per day: {meals_per_day} (labeled Meal 1, Meal 2, ... Meal {meals_per_day})

Meal style: {meal_style}
{meal_style_instructions}

Bulk prep instructions: {bulk_instructions}

Pantry on hand (prioritize using these):
{pantry_items}

IMPORTANT: Never include anything conflicting with dietary restrictions or allergies.
For each meal include a complete ingredient list with quantity_type:
- exact: numeric quantity you're confident about (e.g., "2 lbs chicken breast")
- partial: approximate or variable (e.g., "some olive oil", "half a bag of rice")
- trace: trivial amounts that don't need tracking (salt, pepper, cooking spray, spices)
- unknown: can't determine quantity

Estimate per-meal macros accurately — these drive the user's nutrition tracking.

For each meal, fill the "instructions" field with ordered, numbered-style cooking steps
(each list item is one step). Match the depth to the meal style:
- recipes: complete steps with technique, temperatures, and timing
- simple: 2–4 short practical steps
- bland: minimal steps (e.g. "Boil chicken 15 min", "Steam broccoli 6 min")
- macros_only: a single assembly line is fine (e.g. "Cook protein, carb, and veg; plate together")

{special_requests_section}"""

_MEAL_STYLE_INSTRUCTIONS = {
    "bland": "Prepare food with NO seasoning beyond salt. Boiled, steamed, baked, or grilled only. No sauces. These are performance meals — fuel only.",
    "simple": "Use basic seasoning (salt, pepper, garlic, basic spices). 3–5 ingredients per meal. Practical and quick.",
    "recipes": "Create full recipes with technique, multiple ingredients, and real flavor. The user enjoys cooking.",
    "macros_only": "Do NOT write recipes. Just list: protein source + carb source + vegetable. One line per meal. No cooking instructions.",
}

_BULK_TEMPLATE_ON = """Bulk prep is enabled. {bulk_pct}% of meals should be batch cooked.
- Mark those meals with is_bulk_prep=True
- Set bulk_servings to the number of days they cover
- Set bulk_prep_days to the list of ISO dates that meal covers
- {repeat_instruction}"""

_BULK_REPEAT_ALL = "Repeat the same bulk meals every day they're scheduled."
_BULK_MIX = "Decide which days get the bulk meal based on variety and practicality."


class _Ingredient(BaseModel):
    item: str
    quantity: str
    unit: str
    quantity_type: Literal["exact", "partial", "trace", "unknown"]


class _Meal(BaseModel):
    meal_number: int
    recipe_name: str
    cook_time_minutes: int
    estimated_cost: float
    brief_description: str
    instructions: list[str]  # ordered cooking steps (see meal-style guidance)
    ingredients: list[_Ingredient]
    calories_est: float
    protein_g_est: float
    carbs_g_est: float
    fat_g_est: float
    is_bulk_prep: bool
    bulk_servings: int
    bulk_prep_days: list[str]


class _DayPlan(BaseModel):
    date: str
    meals: Annotated[list[_Meal], Field(min_length=1)]


class _RangePlan(BaseModel):
    days: list[_DayPlan]


# Cap concurrent LLM calls so a long plan doesn't blow past API rate limits.
_MAX_PARALLEL_DAYS = 5


def meal_planner_node(state: RangePlanState, config: RunnableConfig | None = None) -> dict:
    # BYOK creds come from the request-scoped ContextVar, never from the graph
    # config (which the checkpointer would persist to disk). `config` is accepted
    # for LangGraph node-signature compatibility but intentionally unused here.
    provider, api_key = get_request_creds()
    llm = make_llm(provider, api_key, role="planner")
    planner = llm.with_structured_output(_RangePlan)      # all days in one call (bulk prep)
    planner_day = llm.with_structured_output(_DayPlan)    # a single day (parallel path)

    pantry_items = (
        ", ".join(p["item"] for p in state.get("pantry_inventory", []))
        or "none"
    )

    meal_style = state.get("meal_style", "simple")
    style_instructions = _MEAL_STYLE_INSTRUCTIONS.get(meal_style, _MEAL_STYLE_INSTRUCTIONS["simple"])

    feedback = state.get("human_feedback", "")
    feedback_addendum = f"\n\nRevision requested: {feedback}" if feedback else ""

    special_requests = state.get("special_requests", "").strip()
    special_requests_section = (
        f"Additional user requests: {special_requests}"
        if special_requests
        else ""
    )

    def _system(num_days: int, start_date: str, bulk_instructions: str) -> SystemMessage:
        return SystemMessage(
            content=_SYSTEM.format(
                num_days=num_days,
                start_date=start_date,
                skill_level=state["skill_level"],
                max_cook_time=state.get("max_cook_time_minutes", 60),
                budget=f"${state['daily_budget']}/day" if state.get("daily_budget") else "flexible",
                dietary_restrictions=", ".join(state.get("dietary_restrictions", [])) or "none",
                food_allergies=state.get("food_allergies", "") or "none",
                calorie_target=state["calorie_target"],
                protein_target=state["protein_target_g"],
                meals_per_day=state["meals_per_day"],
                meal_style=meal_style,
                meal_style_instructions=style_instructions,
                bulk_instructions=bulk_instructions,
                pantry_items=pantry_items,
                special_requests_section=special_requests_section,
            )
        )

    num_days = state["num_days"]
    bulk_enabled = state.get("bulk_prep_enabled", False)

    if bulk_enabled:
        # Bulk prep batches span multiple days, so they must be planned together
        # in a single coordinated call.
        pct = round(state.get("bulk_prep_pct", 0.5) * 100)
        repeat_instr = _BULK_REPEAT_ALL if state.get("bulk_repeat_all_days") else _BULK_MIX
        bulk_instructions = _BULK_TEMPLATE_ON.format(bulk_pct=pct, repeat_instruction=repeat_instr)
        system = _system(num_days, state["start_date"], bulk_instructions)
        human = HumanMessage(content=f"Create my meal plan.{feedback_addendum}")
        plan: _RangePlan = planner.invoke([system, human])
        planned_days = [d.model_dump() for d in plan.days]
    else:
        # Days are independent (each hits the same per-day macro target), so we
        # generate them concurrently — turning one long serial call into N short
        # parallel ones.
        start = _Date.fromisoformat(state["start_date"])
        dates = [(start + timedelta(days=i)).isoformat() for i in range(num_days)]
        no_bulk = "No bulk prep — generate meals for this single day."

        def _plan_one(idx: int, target_date: str) -> dict:
            system = _system(1, target_date, no_bulk)
            human = HumanMessage(
                content=(
                    f"Create meals for {target_date} (day {idx + 1} of {num_days}). "
                    f"Make this day's meals distinct so the week has variety."
                    f"{feedback_addendum}"
                )
            )
            day: _DayPlan = planner_day.invoke([system, human])
            day_dict = day.model_dump()
            day_dict["date"] = target_date  # trust our date, not the model's
            return day_dict

        planned_days: list[dict] = [None] * num_days  # type: ignore[list-item]
        with ThreadPoolExecutor(max_workers=min(num_days, _MAX_PARALLEL_DAYS)) as pool:
            futures = {pool.submit(_plan_one, i, d): i for i, d in enumerate(dates)}
            for fut in as_completed(futures):
                planned_days[futures[fut]] = fut.result()

    names = [m["recipe_name"] for day in planned_days for m in day.get("meals", [])]
    msg = f"Planned {len(planned_days)} days, {len(names)} total meals."

    return {
        "planned_days": planned_days,
        "nutrition_summaries": [],
        "human_feedback": None,
        "current_agent": "orchestrator",
        "messages": [AIMessage(content=msg)],
    }
