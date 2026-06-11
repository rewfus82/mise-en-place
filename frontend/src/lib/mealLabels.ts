// Meal-slot labels by number of meals in the day — mirrors the backend
// _MEAL_LABELS so a 3-meal day reads Breakfast / Lunch / Dinner instead of M1/M2/M3.

const MEAL_LABELS: Record<number, string[]> = {
  1: ['Meal'],
  2: ['Lunch', 'Dinner'],
  3: ['Breakfast', 'Lunch', 'Dinner'],
  4: ['Breakfast', 'Lunch', 'Dinner', 'Snack'],
  5: ['Breakfast', 'Morning Snack', 'Lunch', 'Afternoon Snack', 'Dinner'],
  6: ['Breakfast', 'Morning Snack', 'Lunch', 'Afternoon Snack', 'Dinner', 'Evening Snack'],
}

/** Full label for a meal slot, e.g. (1, 3) -> "Breakfast". Falls back to "Meal N". */
export function mealLabel(mealNumber: number, totalMeals: number): string {
  const labels = MEAL_LABELS[totalMeals]
  if (labels && mealNumber >= 1 && mealNumber <= labels.length) return labels[mealNumber - 1]
  return `Meal ${mealNumber}`
}
