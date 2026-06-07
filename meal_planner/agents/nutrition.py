from langchain_core.messages import AIMessage

from meal_planner.state import RangePlanState


def nutrition_node(state: RangePlanState) -> dict:
    """Pure Python aggregation — sums meal macros per day, checks against targets."""
    planned_days = state.get("planned_days", [])
    calorie_target = state.get("calorie_target", 0)
    protein_target = state.get("protein_target_g", 0)

    summaries = []
    messages = []

    for day_plan in planned_days:
        meals = day_plan.get("meals", [])
        total_cal = sum(m.get("calories_est", 0) for m in meals)
        total_pro = sum(m.get("protein_g_est", 0) for m in meals)
        total_carb = sum(m.get("carbs_g_est", 0) for m in meals)
        total_fat = sum(m.get("fat_g_est", 0) for m in meals)

        cal_ok = calorie_target == 0 or abs(total_cal - calorie_target) / max(calorie_target, 1) <= 0.20
        pro_ok = protein_target == 0 or abs(total_pro - protein_target) / max(protein_target, 1) <= 0.20

        summaries.append({
            "date": day_plan["date"],
            "total_calories": round(total_cal),
            "total_protein_g": round(total_pro),
            "total_carbs_g": round(total_carb),
            "total_fat_g": round(total_fat),
            "on_target": cal_ok and pro_ok,
        })

    days_off = [s["date"] for s in summaries if not s["on_target"]]
    if days_off:
        msg = f"Nutrition check: {len(days_off)} day(s) are >20% off targets ({', '.join(days_off)})."
    else:
        msg = f"Nutrition check: all {len(summaries)} day(s) are within 20% of targets."

    return {
        "nutrition_summaries": summaries,
        "current_agent": "orchestrator",
        "messages": [AIMessage(content=msg)],
    }
