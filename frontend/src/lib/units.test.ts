import { describe, it, expect } from 'vitest'
import { kgToLbs, lbsToKg, cmToFtIn, ftInToCm, deriveCarbsFat } from './units'

describe('kgToLbs / lbsToKg', () => {
  it('converts kg to lbs', () => {
    expect(kgToLbs(80)).toBeCloseTo(176.3696, 3)
  })

  it('converts lbs to kg', () => {
    expect(lbsToKg(176.3696)).toBeCloseTo(80, 2)
  })

  it('round-trips within tolerance', () => {
    // The lb/kg constants aren't exact inverses, so allow ~0.001 drift.
    expect(lbsToKg(kgToLbs(72.5))).toBeCloseTo(72.5, 2)
  })
})

describe('cmToFtIn / ftInToCm', () => {
  it('converts 180cm to ~5ft 11in', () => {
    expect(cmToFtIn(180)).toEqual({ ft: 5, inches: 11 })
  })

  it('converts 152.4cm to exactly 5ft 0in', () => {
    expect(cmToFtIn(152.4)).toEqual({ ft: 5, inches: 0 })
  })

  it('ftInToCm matches the foot definition', () => {
    expect(ftInToCm(5, 0)).toBeCloseTo(152.4, 5)
    expect(ftInToCm(6, 0)).toBeCloseTo(182.88, 5)
  })

  it('treats NaN inches as zero', () => {
    expect(ftInToCm(5, NaN)).toBeCloseTo(152.4, 5)
  })

  it('round-trips a whole-inch height', () => {
    const { ft, inches } = cmToFtIn(ftInToCm(5, 10))
    expect({ ft, inches }).toEqual({ ft: 5, inches: 10 })
  })
})

describe('deriveCarbsFat', () => {
  it('matches the backend macro formula', () => {
    // calories=2500, protein=141 -> fat=69, carbs=329 (same as tdee_service)
    expect(deriveCarbsFat(2500, 141)).toEqual({ fat: 69, carbs: 329 })
  })

  it('fat is 25% of calories / 9', () => {
    expect(deriveCarbsFat(3600, 180).fat).toBe(100) // 3600*0.25/9 = 100
  })

  it('clamps carbs at zero when protein exceeds the budget', () => {
    // Tiny calories, huge protein -> negative carbs would result, clamped to 0.
    expect(deriveCarbsFat(500, 300).carbs).toBe(0)
  })
})
