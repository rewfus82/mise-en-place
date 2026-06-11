import random
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date as _Date, timedelta
from typing import Annotated, Literal

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel, Field

from meal_planner.llm import get_request_creds, make_llm
from meal_planner.rag.guidance import guideline_block, plan_rationale
from meal_planner.rag.recipes import recipe_anchor_block
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
- Daily calorie target: {calorie_target} kcal  (≈ {cal_per_meal} kcal per meal)
- Daily protein target: {protein_target}g  (≈ {protein_per_meal}g protein per meal)
- Meals per day: {meals_per_day}
{meal_structure_line}

CRITICAL — HIT THE DAILY TOTALS: the {meals_per_day} meals MUST together add up to
about {calorie_target} kcal and {protein_target}g protein for the day (within ~10%).
That is roughly {cal_per_meal} kcal and {protein_per_meal}g protein PER MEAL.
Deliberately SIZE THE PORTIONS to reach these totals — use generous serving sizes and
calorie-dense components (rice, pasta, oats, olive oil, nut butters, whole eggs,
full-fat dairy) instead of standard restaurant portions. If a normal serving falls
short, scale it up. These explicit calorie and protein targets take priority over any
general nutrition guidance below.

Meal style: {meal_style}
{meal_style_instructions}

VARIETY: Do not reuse the same recipes across days. Vary the primary protein,
cuisine, and cooking method from day to day so the plan has genuine variety.

Bulk prep instructions: {bulk_instructions}

Pantry on hand (prioritize using these):
{pantry_items}

{guidelines_section}

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

# Meal-slot labels by meals/day so a 3-meal day plans Breakfast/Lunch/Dinner rather
# than three interchangeable meals. Must stay in sync with the frontend mealLabel().
_MEAL_LABELS: dict[int, list[str]] = {
    1: ["Meal"],
    2: ["Lunch", "Dinner"],
    3: ["Breakfast", "Lunch", "Dinner"],
    4: ["Breakfast", "Lunch", "Dinner", "Snack"],
    5: ["Breakfast", "Morning Snack", "Lunch", "Afternoon Snack", "Dinner"],
    6: ["Breakfast", "Morning Snack", "Lunch", "Afternoon Snack", "Dinner", "Evening Snack"],
}


def _meal_structure_line(meals_per_day: int) -> str:
    labels = _MEAL_LABELS.get(meals_per_day)
    if not labels:
        return f"Plan them as Meal 1 … Meal {meals_per_day}."
    mapping = ", ".join(f"Meal {i + 1} = {lbl}" for i, lbl in enumerate(labels))
    return (
        f"Plan each meal for its slot: {mapping}. Make each appropriate to its time "
        f"of day (breakfast foods at breakfast, lighter fare for snacks)."
    )


# Rotation pools for per-day diversity seeding — independent parallel day-calls each
# get a distinct steer so they don't all converge on the same default meal.
_PROTEINS = ["chicken", "lean beef", "eggs & dairy", "white fish", "salmon", "turkey", "pork", "shrimp"]
_PLANT_PROTEINS = ["tofu", "tempeh", "lentils & beans", "chickpeas", "edamame", "seitan"]
_VEGETARIAN_EXTRA = ["eggs", "Greek yogurt & cottage cheese", "paneer"]
_CUISINES = ["Mediterranean", "Mexican", "East Asian", "American comfort", "Italian", "Indian-spiced", "Middle Eastern", "Thai"]
_METHODS = ["grilled", "baked", "stir-fried", "slow-cooked", "pan-seared", "sheet-pan roasted"]
_BREAKFASTS = [
    "overnight oats or oatmeal", "a Greek yogurt parfait", "a protein smoothie",
    "scrambled eggs or an omelette", "a cottage cheese bowl", "a breakfast burrito or wrap",
    "protein pancakes", "a savory breakfast hash",
]


def _allowed_proteins(restrictions: list[str], allergies: str) -> list[str]:
    r = " ".join(restrictions or []).lower()
    a = (allergies or "").lower()
    if "vegan" in r:
        pool = list(_PLANT_PROTEINS)
    elif "vegetarian" in r:
        pool = _PLANT_PROTEINS + _VEGETARIAN_EXTRA
    elif "pescatarian" in r:
        pool = ["white fish", "salmon", "shrimp", "tuna"] + _VEGETARIAN_EXTRA + _PLANT_PROTEINS
    else:
        pool = list(_PROTEINS)

    def ok(p: str) -> bool:
        pl = p.lower()
        if "shellfish" in a and any(x in pl for x in ("shrimp", "prawn", "crab", "lobster")):
            return False
        if "fish" in a and any(x in pl for x in ("fish", "salmon", "tuna", "cod")):
            return False
        if "egg" in a and "egg" in pl:
            return False
        if ("dairy" in a or "lactose" in a) and any(x in pl for x in ("dairy", "yogurt", "cottage", "paneer", "cheese")):
            return False
        if "soy" in a and any(x in pl for x in ("tofu", "tempeh", "edamame", "soy")):
            return False
        return True

    return [p for p in pool if ok(p)] or ["lean protein"]


def _diversity_choice(idx: int, restrictions: list[str], allergies: str) -> tuple[str, str, str, str]:
    """(protein, cuisine, method, breakfast) for a given day index — drives both the
    prompt steer and the recipe-anchor query so they stay aligned."""
    proteins = _allowed_proteins(restrictions, allergies)
    return (
        proteins[idx % len(proteins)],
        _CUISINES[(idx * 3) % len(_CUISINES)],   # stride 3 (coprime to 8) spreads choices
        _METHODS[idx % len(_METHODS)],
        _BREAKFASTS[idx % len(_BREAKFASTS)],
    )


def _diversity_directive(idx: int, restrictions: list[str], allergies: str) -> str:
    protein, cuisine, method, breakfast = _diversity_choice(idx, restrictions, allergies)
    return (
        f"Variety steer for this day: lean toward {protein} as a primary protein, a "
        f"{cuisine} flavor profile, and {method} preparation where it fits the targets "
        f"and restrictions. If this day includes a breakfast, make it {breakfast} — do "
        f"NOT default every breakfast to eggs. Make this day clearly distinct from the "
        f"other days."
    )


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

    # Retrieve evidence once per plan (not per day) and reuse the block across the
    # parallel per-day calls. `guideline_sources` is surfaced to the user so the
    # grounding is visible, not silent.
    guidelines_section, guideline_sources = guideline_block(
        state.get("goal", "maintain"), state["protein_target_g"]
    )

    # Random base so the per-day variety steer differs run-to-run — multi-day plans
    # still get distinct days (base+idx), and a single-day regen varies each time.
    div_base = random.randint(0, 720)
    restrictions = state.get("dietary_restrictions", [])
    allergies = state.get("food_allergies", "")
    # Minimal styles (macros_only/bland) don't benefit from recipe inspiration.
    use_anchors = meal_style not in ("macros_only", "bland")

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
                cal_per_meal=round(state["calorie_target"] / max(state["meals_per_day"], 1)),
                protein_per_meal=round(state["protein_target_g"] / max(state["meals_per_day"], 1)),
                meals_per_day=state["meals_per_day"],
                meal_structure_line=_meal_structure_line(state["meals_per_day"]),
                meal_style=meal_style,
                meal_style_instructions=style_instructions,
                bulk_instructions=bulk_instructions,
                pantry_items=pantry_items,
                guidelines_section=guidelines_section,
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
        bulk_anchors = (
            recipe_anchor_block(" ".join(_allowed_proteins(restrictions, allergies)[:4]), k=6, restrictions=restrictions)
            if use_anchors else ""
        )
        human = HumanMessage(
            content=(
                "Create my meal plan. Make every day distinct — vary the proteins, "
                f"cuisines, and cooking methods across the days. {bulk_anchors}{feedback_addendum}"
            )
        )
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
            seed = div_base + idx
            protein, cuisine, method, _b = _diversity_choice(seed, restrictions, allergies)
            anchors = (
                recipe_anchor_block(f"{protein} {cuisine} {method}", restrictions=restrictions)
                if use_anchors else ""
            )
            human = HumanMessage(
                content=(
                    f"Create meals for {target_date} (day {idx + 1} of {num_days}). "
                    f"{_diversity_directive(seed, restrictions, allergies)} {anchors}"
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
    if guideline_sources:
        cites = ", ".join(s["citation"] for s in guideline_sources)
        msg += f" Applied evidence-based guidance from {cites}."

    # A short, grounded "why this plan" written from the same retrieved evidence.
    # Feed the rationale model the plan's shape so it explains a concrete plan.
    days_n = len(planned_days)
    avg_protein = (
        round(sum(m.get("protein_g_est", 0) for day in planned_days
                  for m in day.get("meals", [])) / days_n)
        if days_n else 0
    )
    plan_summary = (
        f"{days_n} day(s), {state.get('meals_per_day', 0)} meals/day, "
        f"averaging ~{avg_protein} g protein/day"
    )
    guideline_summary = plan_rationale(
        state.get("goal", "maintain"),
        state["protein_target_g"],
        state.get("calorie_target", 0),
        guidelines_section,
        provider,
        api_key,
        plan_summary,
    )

    return {
        "planned_days": planned_days,
        "nutrition_summaries": [],
        "applied_guidelines": guideline_sources,
        "guideline_summary": guideline_summary,
        "human_feedback": None,
        "current_agent": "orchestrator",
        "messages": [AIMessage(content=msg)],
    }
