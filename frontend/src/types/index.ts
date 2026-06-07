export interface Ingredient {
  id: number
  meal_id: number
  item: string
  quantity: string | null
  unit: string | null
  quantity_type: 'exact' | 'partial' | 'trace' | 'unknown' | null
}

export interface DayMeal {
  id: number
  day_id: number
  meal_number: number
  recipe_name: string
  cook_time_minutes: number | null
  estimated_cost: number | null
  brief_description: string | null
  // Newline-joined steps from the calendar/DB, or a string[] straight from the
  // plan-review stream. MealRow normalizes both.
  instructions: string | string[] | null
  calories_est: number | null
  protein_g_est: number | null
  carbs_g_est: number | null
  fat_g_est: number | null
  eaten: boolean
  skipped: boolean
  prep_id: number | null
  ingredients: Ingredient[]
}

export interface MealDay {
  id: number
  date: string
  status: 'planned' | 'completed' | 'skipped'
  confirmed_at: string | null
  skipped_at: string | null
  meals: DayMeal[]
}

export interface MealPrep {
  id: number
  recipe_name: string
  brief_description: string | null
  total_servings: number
  servings_remaining: number
  prep_date: string
  calories_per_serving: number | null
  protein_g_per_serving: number | null
  carbs_g_per_serving: number | null
  fat_g_per_serving: number | null
}

export interface PantryItem {
  id: number
  item: string
  quantity: string
  category: string
}

export interface GroceryItem {
  ingredient: string
  quantity_needed: string
  unit: string | null
  needed_by_date: string
  deficit_calculable: boolean
  quantity_type: string | null
}

export interface UserProfile {
  id: number
  skill_level: string
  max_cook_time_minutes: number
  weekly_budget: number | null
  dietary_restrictions: string[]
  food_allergies: string
  meal_style: string
  meals_per_day: number
  height_cm: number | null
  weight_kg: number | null
  age: number | null
  sex: string | null
  activity_level: string
  body_fat_pct: number | null
  goal: string
  tdee_calculated: number | null
  calorie_target: number | null
  protein_target_g: number | null
  carbs_target_g: number | null
  fat_target_g: number | null
  theme: string
}

export interface TdeeResponse {
  tdee: number
  recommended_calories: number
  recommended_protein_g: number
  recommended_carbs_g: number
  recommended_fat_g: number
  suggested_meals_per_day: number
}

export interface NutritionSummary {
  date: string
  total_calories: number
  total_protein_g: number
  total_carbs_g: number
  total_fat_g: number
  on_target: boolean
}

export interface PlanReviewDay {
  date: string
  meals: Array<{
    meal_number: number
    recipe_name: string
    brief_description: string
    calories_est: number
    protein_g_est: number
    carbs_g_est: number
    fat_g_est: number
    is_bulk_prep: boolean
    bulk_servings: number
    ingredients: Ingredient[]
  }>
}

export interface SSEProgressEvent {
  type: 'progress'
  agent: string
  message: string
}

export interface SSEReviewEvent {
  type: 'awaiting_review'
  thread_id: string
  days: PlanReviewDay[]
  nutrition_summaries: NutritionSummary[]
}

export interface SSECompleteEvent {
  type: 'complete'
  thread_id: string
}

export type SSEEvent = SSEProgressEvent | SSEReviewEvent | SSECompleteEvent

export interface WeightEntry {
  id: number
  date: string
  weight_kg: number
  notes: string | null
}

export interface MeasuredTdee {
  measured_tdee: number
  window_days: number
  tracked_days: number
  start_date: string
  end_date: string
  start_weight_kg: number
  end_weight_kg: number
  avg_daily_calories: number
}
