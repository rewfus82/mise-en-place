"""Unit tests for backend.services.tdee_service.

All expected numbers are hand-computed from the formulas so the tests are an
independent check, not a mirror of the implementation.
"""
import pytest

from backend.services.tdee_service import (
    calculate_tdee,
    recommended_macros,
    suggest_meals_per_day,
)


class TestCalculateTdee:
    def test_mifflin_male_moderately_active(self):
        # BMR = 10*80 + 6.25*180 - 5*30 + 5 = 1780; *1.55 = 2759.0
        assert calculate_tdee(80, 180, 30, "male", "moderately_active") == 2759

    def test_mifflin_female_moderately_active(self):
        # BMR = 800 + 1125 - 150 - 161 = 1614; *1.55 = 2501.7 -> 2502
        assert calculate_tdee(80, 180, 30, "female", "moderately_active") == 2502

    def test_katch_mcardle_used_when_body_fat_provided(self):
        # LBM = 80*0.8 = 64; BMR = 370 + 21.6*64 = 1752.4; *1.55 = 2716.22 -> 2716
        assert calculate_tdee(80, 180, 30, "male", "moderately_active", 20.0) == 2716

    def test_body_fat_path_ignores_height_age_sex(self):
        # Katch-McArdle depends only on weight + body fat + activity.
        a = calculate_tdee(80, 180, 30, "male", "moderately_active", 20.0)
        b = calculate_tdee(80, 150, 99, "female", "moderately_active", 20.0)
        assert a == b

    def test_activity_multipliers_scale_monotonically(self):
        sed = calculate_tdee(80, 180, 30, "male", "sedentary")
        mod = calculate_tdee(80, 180, 30, "male", "moderately_active")
        extra = calculate_tdee(80, 180, 30, "male", "extra_active")
        assert sed < mod < extra

    def test_unknown_activity_defaults_to_moderate(self):
        unknown = calculate_tdee(80, 180, 30, "male", "couch_potato")
        moderate = calculate_tdee(80, 180, 30, "male", "moderately_active")
        assert unknown == moderate

    def test_returns_int(self):
        assert isinstance(calculate_tdee(75.5, 175.2, 28, "male", "very_active"), int)


class TestRecommendedMacros:
    def test_maintain(self):
        m = recommended_macros(2500, "maintain", 80)
        # weight_lbs = 176.3696; protein = round(*0.8) = 141
        assert m["calories"] == 2500
        assert m["protein_g"] == 141
        assert m["fat_g"] == 69          # round(2500*0.25/9)
        assert m["carbs_g"] == 329       # round((1936 - 621)/4)

    def test_bulk_adds_surplus(self):
        m = recommended_macros(2500, "bulk", 80)
        assert m["calories"] == 2875     # round(2500*1.15)
        assert m["protein_g"] == 150     # round(176.3696*0.85)

    def test_cut_creates_deficit(self):
        m = recommended_macros(2500, "cut", 80)
        assert m["calories"] == 2000     # round(2500*0.80)
        assert m["protein_g"] == 212     # round(176.3696*1.2)

    def test_recomp_holds_calories(self):
        m = recommended_macros(2500, "recomp", 80)
        assert m["calories"] == 2500

    def test_calorie_ordering_across_goals(self):
        cut = recommended_macros(2500, "cut", 80)["calories"]
        maintain = recommended_macros(2500, "maintain", 80)["calories"]
        bulk = recommended_macros(2500, "bulk", 80)["calories"]
        assert cut < maintain < bulk

    def test_body_fat_uses_lean_mass_for_protein(self):
        # bulk with bf: lean_lbs = 176.3696*0.8 = 141.0957; protein = round(*1.0) = 141
        m = recommended_macros(2500, "bulk", 80, body_fat_pct=20.0)
        assert m["protein_g"] == 141

    def test_carbs_never_negative(self):
        # Very low calories with high protein could drive carbs below zero.
        m = recommended_macros(800, "cut", 120)
        assert m["carbs_g"] >= 0

    def test_unknown_goal_falls_back_to_maintain(self):
        unknown = recommended_macros(2500, "lose_weight_fast", 80)
        maintain = recommended_macros(2500, "maintain", 80)
        assert unknown == maintain


class TestSuggestMealsPerDay:
    @pytest.mark.parametrize(
        "calories,expected",
        [
            (2000, 3),
            (2499, 3),
            (2500, 4),
            (3499, 4),
            (3500, 5),
            (5000, 5),
        ],
    )
    def test_thresholds(self, calories, expected):
        assert suggest_meals_per_day(calories) == expected
