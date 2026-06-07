from dotenv import load_dotenv
load_dotenv()

import uuid
from datetime import date

import pandas as pd
import streamlit as st
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.types import Command

from meal_planner.graph import build_graph
from meal_planner.mcp_servers.pantry_server import (
    add_items as _db_add,
    clear_inventory as _db_clear,
    get_inventory as _db_get,
    remove_items as _db_remove,
)
from meal_planner.agents.pantry_parser import _parser, _SYSTEM as _PARSE_SYSTEM
from meal_planner.tracing import setup_tracing

setup_tracing()

st.set_page_config(
    page_title="mise-en-place",
    page_icon="🍳",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── Constants ──────────────────────────────────────────────────────────────────
_CATEGORIES = ["produce", "protein", "dairy", "grains", "canned", "frozen", "condiments", "spices", "other"]

# (count, description, meals_per_day)
_MEAL_PRESETS = {
    "Weeknight dinners (5)":          (5,  "5 dinners, Monday–Friday",             1),
    "Full week dinners (7)":          (7,  "7 dinners, Monday–Sunday",             1),
    "Lunch + dinner, weekdays (10)":  (10, "5 lunches + 5 dinners, Monday–Friday", 2),
    "All meals, full week (21)":      (21, "breakfast, lunch, and dinner for 7 days", 3),
    "Custom":                         (None, None, None),
}

_DIETARY_OPTIONS = [
    "Vegetarian", "Vegan", "Pescatarian",
    "Gluten-free", "Dairy-free", "Nut-free",
    "Low-carb / Keto", "Low-sodium", "Halal", "Kosher",
]

_NODE_LABELS = {
    "orchestrator":  "Orchestrator",
    "pantry_parser": "Pantry Parser",
    "meal_planner":  "Meal Planner",
    "nutrition":     "Nutrition",
    "shopping_list": "Shopping List",
    "human_review":  "Review",
}

# ── Session state ──────────────────────────────────────────────────────────────
for _k, _v in {
    "phase": "setup",
    "thread_id": None,
    "graph": None,
    "initial_state": None,
    "planned_meals": [],
    "shopping_list": [],
    "nutrition": {},
    "total_cost": 0.0,
    "budget_remaining": None,
    "pending_feedback": None,
    "pantry_version": 0,   # bump to force data_editor reset
}.items():
    if _k not in st.session_state:
        st.session_state[_k] = _v


# ── Pantry helpers ─────────────────────────────────────────────────────────────
def _pantry_df() -> pd.DataFrame:
    rows = _db_get()
    if rows:
        return pd.DataFrame(rows)[["item", "quantity", "category"]]
    return pd.DataFrame(columns=["item", "quantity", "category"])


def _refresh_pantry():
    st.session_state.pantry_version += 1


def _save_pantry(df: pd.DataFrame):
    _db_clear()
    valid = df.dropna(subset=["item"])
    valid = valid[valid["item"].str.strip() != ""]
    if not valid.empty:
        _db_add(valid.fillna("unknown").to_dict("records"))
    _refresh_pantry()


# ── Plan-tab helpers ───────────────────────────────────────────────────────────
def _stream(payload, config):
    for chunk in st.session_state.graph.stream(payload, config=config, stream_mode="updates"):
        for node, updates in chunk.items():
            label = _NODE_LABELS.get(node, node)
            for msg in updates.get("messages", []):
                c = getattr(msg, "content", "")
                if c:
                    st.write(f"**{label}** — {c}")
    return st.session_state.graph.get_state(config)


def _sync(snapshot):
    v = snapshot.values
    st.session_state.planned_meals   = v.get("planned_meals", [])
    st.session_state.shopping_list   = v.get("shopping_list", [])
    st.session_state.nutrition       = v.get("nutrition_summary", {})
    st.session_state.total_cost      = v.get("estimated_total_cost") or 0.0
    st.session_state.budget_remaining = v.get("budget_remaining")


def _meal_cards(meals: list[dict]):
    cols = st.columns(3)
    for i, m in enumerate(meals):
        with cols[i % 3]:
            with st.container(border=True):
                st.markdown(f"**{m.get('recipe_name', '—')}**")
                st.caption(f"{m.get('day', '?')} · {m.get('meal_type', '').title()}")
                a, b = st.columns(2)
                a.metric("Cook time", f"{m.get('cook_time_minutes', '?')} min")
                b.metric("Est. cost", f"${m.get('estimated_cost', 0):.2f}")
                used = m.get("uses_pantry_items", [])
                if used:
                    st.caption("Pantry: " + ", ".join(used[:3]))
                if m.get("brief_description"):
                    st.caption(m["brief_description"])


def _shopping_table(shopping: list[dict]):
    if not shopping:
        return
    df = pd.DataFrame(shopping)
    keep = [c for c in ["item", "quantity", "estimated_cost", "category"] if c in df.columns]
    df = df[keep].rename(columns=lambda c: c.replace("_", " ").title())
    if "Category" in df.columns:
        df = df.sort_values("Category")
    st.dataframe(df, width='stretch', hide_index=True)


# ══════════════════════════════════════════════════════════════════════════════
# HEADER
# ══════════════════════════════════════════════════════════════════════════════
st.markdown("## 🍳 mise-en-place")
st.caption("Multi-agent AI meal planner · LangGraph + Claude + MCP")

tab_plan, tab_pantry = st.tabs(["Plan Meals", "My Pantry"])


# ══════════════════════════════════════════════════════════════════════════════
# TAB — MY PANTRY
# ══════════════════════════════════════════════════════════════════════════════
with tab_pantry:
    st.markdown("#### Inventory")
    st.caption("Edit directly in the table. Use the last empty row to add items.")

    ver = st.session_state.pantry_version
    current_df = _pantry_df()

    edited = st.data_editor(
        current_df,
        key=f"pantry_ed_{ver}",
        num_rows="dynamic",
        width='stretch',
        hide_index=True,
        column_config={
            "item":     st.column_config.TextColumn("Item", required=True, width="medium"),
            "quantity": st.column_config.TextColumn("Quantity", width="small"),
            "category": st.column_config.SelectboxColumn(
                "Category", options=_CATEGORIES, width="small"
            ),
        },
    )

    save_col, reset_col, _ = st.columns([1, 1, 4])
    with save_col:
        if st.button("Save changes", type="primary", width='stretch'):
            _save_pantry(edited)
            st.success("Saved.")
            st.rerun()
    with reset_col:
        if st.button("Reset", width='stretch'):
            _refresh_pantry()
            st.rerun()

    st.markdown("---")
    st.markdown("#### Add items in plain English")
    st.caption("Describe what you just bought or have on hand — the AI will parse it.")

    freeform = st.text_area(
        "freeform",
        placeholder="e.g. just picked up ground beef, jasmine rice, fresh ginger, coconut milk, and a bag of spinach",
        height=80,
        label_visibility="collapsed",
    )
    if st.button("Parse & add", width='content'):
        if freeform.strip():
            with st.spinner("Parsing..."):
                parsed = _parser.invoke([
                    SystemMessage(content=_PARSE_SYSTEM),
                    HumanMessage(content=freeform),
                ])
                result = _db_add([i.model_dump() for i in parsed.items])
            added, skipped = result["added"], result["skipped"]
            if added:
                st.success(f"Added: {', '.join(added)}")
            if skipped:
                st.info(f"Already on file: {', '.join(skipped)}")
            _refresh_pantry()
            st.rerun()
        else:
            st.warning("Type something first.")


# ══════════════════════════════════════════════════════════════════════════════
# TAB — PLAN MEALS
# ══════════════════════════════════════════════════════════════════════════════
with tab_plan:

    # ── SETUP ──────────────────────────────────────────────────────────────────
    if st.session_state.phase == "setup":
        col_a, col_b = st.columns(2, gap="large")

        with col_a:
            with st.container(border=True):
                st.markdown("**How you cook**")
                skill_level = st.select_slider(
                    "Skill level",
                    options=["beginner", "intermediate", "advanced"],
                    value="intermediate",
                )
                max_cook_time = st.slider(
                    "Max cook time per meal", 15, 120, 45, step=5, format="%d min"
                )
                leftovers_ok = st.toggle("Leftovers OK", value=True)

        with col_b:
            with st.container(border=True):
                st.markdown("**This week's plan**")
                preset = st.selectbox("What to plan", list(_MEAL_PRESETS.keys()), label_visibility="collapsed")
                preset_count, preset_desc, preset_mpd = _MEAL_PRESETS[preset]
                if preset == "Custom":
                    c1, c2 = st.columns(2)
                    final_count = c1.number_input("Total meals", 1, 35, 7)
                    final_mpd   = c2.number_input("Meals / day", 1, 3, 1)
                    final_desc  = st.text_input("Describe", placeholder="e.g. 7 lunches") or f"{final_count} meals"
                else:
                    final_count, final_desc, final_mpd = preset_count, preset_desc, preset_mpd

                plan_start_date = st.date_input("Week starts", value=date.today())
                weekly_budget = st.number_input(
                    "Weekly budget ($, 0 = no limit)", min_value=0, max_value=1000, value=0
                )
                if weekly_budget > 0:
                    st.caption(f"≈ ${weekly_budget/7:.0f}/day · costs are AI estimates")

        with st.expander("Nutrition goals & dietary restrictions", expanded=False):
            r1, r2 = st.columns(2)
            with r1:
                dietary = st.multiselect(
                    "Restrictions",
                    options=_DIETARY_OPTIONS,
                    placeholder="None",
                )
                allergies = st.text_input(
                    "Avoid / allergies",
                    placeholder="e.g. peanuts, shellfish",
                )
            with r2:
                calorie_target = st.number_input(
                    "Daily calorie target (0 = none)", min_value=0, max_value=5000, value=0, step=50
                )
                protein_target = st.number_input(
                    "Daily protein target in g (0 = none)", min_value=0, max_value=500, value=0, step=5
                )

        with st.expander(
            f"Pantry · {len(_db_get())} items on file" if _db_get() else "Pantry · empty",
            expanded=not bool(_db_get()),
        ):
            st.caption("Describe anything new since last time, or leave blank to use what's saved.")
            pantry_text = st.text_area(
                "Pantry update",
                placeholder="e.g. just got chicken thighs, jasmine rice, coconut milk",
                height=80,
                label_visibility="collapsed",
            )

        st.markdown("")
        if st.button("Start planning", type="primary", width='stretch'):
            pantry_msg = pantry_text.strip() if pantry_text.strip() else "Use the existing pantry inventory on file."
            st.session_state.thread_id = str(uuid.uuid4())
            st.session_state.graph     = build_graph()
            st.session_state.initial_state = {
                "messages":                   [HumanMessage(content=pantry_msg)],
                "skill_level":                skill_level,
                "max_cook_time_minutes":      int(max_cook_time),
                "weekly_budget":              float(weekly_budget) if weekly_budget > 0 else None,
                "dietary_restrictions":       dietary,
                "food_allergies":             allergies.strip(),
                "calorie_target":             int(calorie_target) if calorie_target > 0 else None,
                "protein_target_g":           int(protein_target) if protein_target > 0 else None,
                "requested_meals":            int(final_count),
                "meal_structure_description": final_desc,
                "meals_per_day_count":        int(final_mpd),
                "plan_start_date":            str(plan_start_date),
                "meals_per_day":              {},
                "leftovers_ok":               leftovers_ok,
                "pantry_inventory":           [],
                "planned_meals":              [],
                "shopping_list":              [],
                "estimated_total_cost":       None,
                "budget_remaining":           None,
                "nutrition_summary":          {},
                "nutrition_approved":         False,
                "awaiting_human_approval":    False,
                "human_feedback":             None,
                "current_agent":              "orchestrator",
                "error":                      None,
            }
            st.session_state.phase = "planning"
            st.rerun()

    # ── PLANNING / REVISING ────────────────────────────────────────────────────
    elif st.session_state.phase in ("planning", "revising"):
        config  = {"configurable": {"thread_id": st.session_state.thread_id}}
        label   = "Planning your meals..." if st.session_state.phase == "planning" else "Revising..."
        payload = (
            st.session_state.initial_state
            if st.session_state.phase == "planning"
            else Command(resume=st.session_state.pending_feedback)
        )
        with st.status(label, expanded=True) as status:
            snapshot = _stream(payload, config)
            _sync(snapshot)
            if snapshot.next:
                status.update(label="Ready for review!", state="complete")
                st.session_state.phase = "review"
            else:
                status.update(label="Done!", state="complete")
                st.session_state.phase = "done"
        st.rerun()

    # ── REVIEW ─────────────────────────────────────────────────────────────────
    elif st.session_state.phase == "review":
        config = {"configurable": {"thread_id": st.session_state.thread_id}}

        # Nutrition strip
        n = st.session_state.nutrition
        if n:
            mpd = n.get("meals_per_day_count", 1)
            structure = n.get("meal_structure", "")

            st.markdown("#### Nutrition estimates")

            if mpd >= 3:
                # Full day planned — show daily totals directly
                st.caption(f"Daily totals · {structure}")
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("Calories",  f"{n.get('est_daily_calories', 0):.0f} kcal")
                c2.metric("Protein",   f"{n.get('est_daily_protein_g', 0):.0f} g")
                c3.metric("Carbs",     f"{n.get('avg_carbs_g_per_meal', 0) * mpd:.0f} g")
                c4.metric("Fiber",     f"{n.get('est_daily_fiber_g', 0):.0f} g")
            else:
                # Partial day — show per-meal, then scaled daily estimate
                st.caption(f"Per meal · {structure}")
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("Calories / meal",  f"{n.get('avg_calories_per_meal', 0):.0f} kcal")
                c2.metric("Protein / meal",   f"{n.get('avg_protein_g_per_meal', 0):.0f} g")
                c3.metric("Carbs / meal",     f"{n.get('avg_carbs_g_per_meal', 0):.0f} g")
                c4.metric("Fiber / meal",     f"{n.get('avg_fiber_g_per_meal', 0):.0f} g")

                if mpd == 2:
                    st.caption(
                        f"Est. daily totals ({mpd} meals/day planned): "
                        f"~{n.get('est_daily_calories', 0):.0f} kcal · "
                        f"~{n.get('est_daily_protein_g', 0):.0f}g protein · "
                        f"does not include meals not in this plan"
                    )
                else:
                    st.caption(
                        f"These are {structure} only — daily totals will be higher "
                        f"once you add other meals."
                    )

            st.caption("All figures are AI estimates from recipe knowledge.")
            st.markdown("---")

        # Meal cards
        meals = st.session_state.planned_meals
        st.markdown(f"#### Meal plan — {len(meals)} meals")
        _meal_cards(meals)
        st.markdown("---")

        # Shopping list
        shopping = st.session_state.shopping_list
        br = st.session_state.budget_remaining
        left, right = st.columns([3, 1])
        with left:
            st.markdown(f"#### Shopping list — {len(shopping)} items")
            st.caption("Prices are AI estimates.")
        with right:
            delta = f"${br:+.2f} vs budget" if br is not None else None
            st.metric("Estimated total", f"${st.session_state.total_cost:.2f}", delta=delta)
        _shopping_table(shopping)
        st.markdown("---")

        # Approve / revise
        approve, revise = st.columns([1, 2], gap="large")
        with approve:
            if st.button("Approve this plan", type="primary", width='stretch'):
                with st.spinner(""):
                    st.session_state.graph.invoke(Command(resume="approve"), config=config)
                st.session_state.phase = "done"
                st.rerun()
        with revise:
            with st.form("revise", border=False):
                feedback = st.text_input(
                    "Request changes",
                    placeholder="e.g. more Asian-inspired meals, keep each dinner under $12...",
                )
                if st.form_submit_button("Revise"):
                    if feedback.strip():
                        st.session_state.pending_feedback = feedback.strip()
                        st.session_state.phase = "revising"
                        st.rerun()

    # ── DONE ───────────────────────────────────────────────────────────────────
    elif st.session_state.phase == "done":
        st.success("Plan locked in. Enjoy the week!")
        st.markdown("---")
        meals = st.session_state.planned_meals
        if meals:
            st.markdown("#### Final meal plan")
            _meal_cards(meals)
        shopping = st.session_state.shopping_list
        if shopping:
            st.markdown("---")
            st.markdown("#### Shopping list")
            _shopping_table(shopping)
        st.markdown("---")
        if st.button("Plan another week"):
            for k in list(st.session_state.keys()):
                del st.session_state[k]
            st.rerun()
