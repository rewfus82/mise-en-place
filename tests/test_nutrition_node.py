"""Unit tests for meal_planner.agents.nutrition.nutrition_node (pure Python, no LLM)."""
from meal_planner.agents.nutrition import nutrition_node


def _day(date, meals):
    return {"date": date, "meals": meals}


def _meal(cal, pro, carb, fat):
    return {
        "calories_est": cal,
        "protein_g_est": pro,
        "carbs_g_est": carb,
        "fat_g_est": fat,
    }


class TestNutritionNode:
    def test_sums_macros_per_day(self):
        state = {
            "planned_days": [
                _day("2026-06-10", [_meal(500, 40, 50, 15), _meal(700, 60, 70, 20)]),
            ],
            "calorie_target": 1200,
            "protein_target_g": 100,
        }
        out = nutrition_node(state)
        summary = out["nutrition_summaries"][0]
        assert summary["total_calories"] == 1200
        assert summary["total_protein_g"] == 100
        assert summary["total_carbs_g"] == 120
        assert summary["total_fat_g"] == 35

    def test_on_target_within_20_percent(self):
        state = {
            "planned_days": [_day("2026-06-10", [_meal(1100, 95, 100, 30)])],
            "calorie_target": 1200,
            "protein_target_g": 100,
        }
        # 1100 vs 1200 = 8.3% off; 95 vs 100 = 5% off -> both within 20%
        assert nutrition_node(state)["nutrition_summaries"][0]["on_target"] is True

    def test_off_target_beyond_20_percent(self):
        state = {
            "planned_days": [_day("2026-06-10", [_meal(700, 50, 60, 20)])],
            "calorie_target": 1200,
            "protein_target_g": 100,
        }
        # 700 vs 1200 = 42% off -> not on target
        assert nutrition_node(state)["nutrition_summaries"][0]["on_target"] is False

    def test_zero_target_treated_as_on_target(self):
        state = {
            "planned_days": [_day("2026-06-10", [_meal(700, 50, 60, 20)])],
            "calorie_target": 0,
            "protein_target_g": 0,
        }
        assert nutrition_node(state)["nutrition_summaries"][0]["on_target"] is True

    def test_one_summary_per_day(self):
        state = {
            "planned_days": [
                _day("2026-06-10", [_meal(600, 50, 60, 18)]),
                _day("2026-06-11", [_meal(600, 50, 60, 18)]),
            ],
            "calorie_target": 600,
            "protein_target_g": 50,
        }
        assert len(nutrition_node(state)["nutrition_summaries"]) == 2

    def test_routes_back_to_orchestrator(self):
        state = {"planned_days": [], "calorie_target": 0, "protein_target_g": 0}
        out = nutrition_node(state)
        assert out["current_agent"] == "orchestrator"

    def test_empty_meals_day_sums_to_zero(self):
        state = {
            "planned_days": [_day("2026-06-10", [])],
            "calorie_target": 2000,
            "protein_target_g": 150,
        }
        summary = nutrition_node(state)["nutrition_summaries"][0]
        assert summary["total_calories"] == 0
        # 0 vs 2000 target is >20% off
        assert summary["on_target"] is False
