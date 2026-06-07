/**
 * Unit conversions and macro math.
 *
 * These were previously duplicated inline across several components (with subtle
 * variants). They are pure functions — formatting (rounding / toFixed) is left to
 * the call site so each component controls its own display precision.
 */

/** Kilograms → pounds (exact; round/format at the call site). */
export function kgToLbs(kg: number): number {
  return kg * 2.20462
}

/** Pounds → kilograms. */
export function lbsToKg(lbs: number): number {
  return lbs * 0.453592
}

/** Centimeters → feet + inches (inches rounded to nearest whole). */
export function cmToFtIn(cm: number): { ft: number; inches: number } {
  const totalIn = cm / 2.54
  return { ft: Math.floor(totalIn / 12), inches: Math.round(totalIn % 12) }
}

/** Feet + inches → centimeters. */
export function ftInToCm(ft: number, inches: number): number {
  return (ft * 12 + (inches || 0)) * 2.54
}

/**
 * Derive fat and carb grams from a calorie + protein target.
 * Fat is fixed at 25% of calories; carbs fill the remainder. Carbs never go
 * negative (clamped at 0 when protein alone exceeds the calorie budget).
 */
export function deriveCarbsFat(
  calories: number,
  protein: number,
): { fat: number; carbs: number } {
  const fat = Math.round((calories * 0.25) / 9)
  const carbs = Math.max(Math.round((calories - protein * 4 - fat * 9) / 4), 0)
  return { fat, carbs }
}
