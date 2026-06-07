import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { profileApi } from '../../api/profile'
import { Button } from '../ui/Button'
import type { UserProfile } from '../../types'

interface OnboardingWizardProps {
  onComplete: () => void
}

type Goal = 'bulk' | 'cut' | 'maintain' | 'recomp'
type ActivityLevel = 'sedentary' | 'lightly_active' | 'moderately_active' | 'very_active' | 'extra_active'
type Sex = 'male' | 'female' | 'other'

const GOALS: { value: Goal; label: string; description: string }[] = [
  { value: 'bulk', label: 'Build Muscle', description: 'Caloric surplus + high protein to maximize muscle gain' },
  { value: 'cut', label: 'Lose Fat', description: 'Caloric deficit, preserve muscle while dropping body fat' },
  { value: 'maintain', label: 'Maintain', description: 'Stay at current weight and body composition' },
  { value: 'recomp', label: 'Recomposition', description: 'Build muscle and lose fat simultaneously at maintenance' },
]

const ACTIVITY_LEVELS: { value: ActivityLevel; label: string; description: string }[] = [
  { value: 'sedentary', label: 'Sedentary', description: 'Desk job, little to no exercise' },
  { value: 'lightly_active', label: 'Lightly Active', description: '1–3 days/week of light exercise' },
  { value: 'moderately_active', label: 'Moderately Active', description: '3–5 days/week of moderate exercise' },
  { value: 'very_active', label: 'Very Active', description: '6–7 days/week hard training' },
  { value: 'extra_active', label: 'Extra Active', description: 'Twice/day training or physical job + hard training' },
]

function stepTitle(step: number) {
  return ['Your Goal', 'Body Metrics', 'Activity Level', 'Macro Targets', 'You\'re Set'][step]
}

export function OnboardingWizard({ onComplete }: OnboardingWizardProps) {
  const qc = useQueryClient()
  const [step, setStep] = useState(0)

  // Step 0: goal
  const [goal, setGoal] = useState<Goal>('maintain')

  // Step 1: body metrics
  const [weightLbs, setWeightLbs] = useState('')
  const [heightFt, setHeightFt] = useState('')
  const [heightIn, setHeightIn] = useState('')
  const [age, setAge] = useState('')
  const [sex, setSex] = useState<Sex>('male')

  // Step 2: activity
  const [activityLevel, setActivityLevel] = useState<ActivityLevel>('moderately_active')

  // Step 3: optional overrides (shown after TDEE preview)
  const [calorieOverride, setCalorieOverride] = useState('')
  const [proteinOverride, setProteinOverride] = useState('')

  const updateProfile = useMutation({
    mutationFn: (data: Partial<UserProfile>) => profileApi.update(data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['profile'] })
    },
  })

  const kgFromLbs = (lbs: number) => lbs * 0.453592
  const cmFromFtIn = (ft: number, inches: number) => (ft * 12 + inches) * 2.54

  const computeTdee = () => {
    const wKg = kgFromLbs(Number(weightLbs))
    const hCm = cmFromFtIn(Number(heightFt), Number(heightIn))
    const a = Number(age)
    let bmr = 10 * wKg + 6.25 * hCm - 5 * a + (sex === 'male' ? 5 : -161)
    const multipliers: Record<ActivityLevel, number> = {
      sedentary: 1.2, lightly_active: 1.375, moderately_active: 1.55, very_active: 1.725, extra_active: 1.9,
    }
    return Math.round(bmr * multipliers[activityLevel])
  }

  const computeCalories = (tdee: number) => {
    if (goal === 'bulk') return Math.round(tdee * 1.15)
    if (goal === 'cut') return Math.round(tdee * 0.80)
    return tdee
  }

  const computeProtein = () => {
    const wLbs = Number(weightLbs)
    if (goal === 'bulk') return Math.round(wLbs * 0.85)
    if (goal === 'cut') return Math.round(wLbs * 1.2)
    if (goal === 'recomp') return Math.round(wLbs * 1.0)
    return Math.round(wLbs * 0.8)
  }

  const isMetricsValid = weightLbs && heightFt && age && Number(weightLbs) > 0

  const handleFinish = async () => {
    const tdee = computeTdee()
    const autoCal = computeCalories(tdee)
    const autoPro = computeProtein()

    await updateProfile.mutateAsync({
      goal,
      weight_kg: kgFromLbs(Number(weightLbs)),
      height_cm: cmFromFtIn(Number(heightFt), Number(heightIn)),
      age: Number(age),
      sex,
      activity_level: activityLevel,
      tdee_calculated: tdee,
      calorie_target: calorieOverride ? Number(calorieOverride) : autoCal,
      protein_target_g: proteinOverride ? Number(proteinOverride) : autoPro,
    })
    onComplete()
  }

  const tdee = isMetricsValid ? computeTdee() : null
  const autoCal = tdee ? computeCalories(tdee) : null
  const autoPro = isMetricsValid ? computeProtein() : null

  return (
    <div className="min-h-screen bg-slate-950 flex items-center justify-center p-4">
      <div className="w-full max-w-xl">
        {/* Progress */}
        <div className="flex gap-1 mb-8">
          {[0, 1, 2, 3, 4].map(i => (
            <div key={i} className={`h-1 flex-1 rounded-full transition-colors ${i <= step ? 'bg-emerald-500' : 'bg-slate-800'}`} />
          ))}
        </div>

        <div className="bg-slate-900 border border-slate-800 rounded-2xl p-8">
          <h2 className="text-2xl font-bold text-slate-100 mb-1">{stepTitle(step)}</h2>
          <p className="text-sm text-slate-500 mb-6">Step {step + 1} of 5</p>

          {/* Step 0: Goal */}
          {step === 0 && (
            <div className="space-y-3">
              {GOALS.map(g => (
                <button
                  key={g.value}
                  onClick={() => setGoal(g.value)}
                  className={`w-full text-left p-4 rounded-xl border transition-colors cursor-pointer
                    ${goal === g.value ? 'border-emerald-500 bg-emerald-950/30' : 'border-slate-700 hover:border-slate-600'}`}
                >
                  <div className="font-semibold text-slate-100">{g.label}</div>
                  <div className="text-sm text-slate-400 mt-0.5">{g.description}</div>
                </button>
              ))}
            </div>
          )}

          {/* Step 1: Body Metrics */}
          {step === 1 && (
            <div className="space-y-4">
              <div>
                <label className="text-xs text-slate-400 block mb-1.5">Weight</label>
                <div className="flex gap-2 items-center">
                  <input
                    type="number"
                    value={weightLbs}
                    onChange={e => setWeightLbs(e.target.value)}
                    placeholder="185"
                    className="w-24 bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm text-slate-100 focus:outline-none focus:border-emerald-500"
                  />
                  <span className="text-sm text-slate-400">lbs</span>
                </div>
              </div>
              <div>
                <label className="text-xs text-slate-400 block mb-1.5">Height</label>
                <div className="flex gap-2 items-center">
                  <input
                    type="number"
                    value={heightFt}
                    onChange={e => setHeightFt(e.target.value)}
                    placeholder="5"
                    className="w-16 bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm text-slate-100 focus:outline-none focus:border-emerald-500"
                  />
                  <span className="text-sm text-slate-400">ft</span>
                  <input
                    type="number"
                    value={heightIn}
                    onChange={e => setHeightIn(e.target.value)}
                    placeholder="10"
                    className="w-16 bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm text-slate-100 focus:outline-none focus:border-emerald-500"
                  />
                  <span className="text-sm text-slate-400">in</span>
                </div>
              </div>
              <div>
                <label className="text-xs text-slate-400 block mb-1.5">Age</label>
                <div className="flex gap-2 items-center">
                  <input
                    type="number"
                    value={age}
                    onChange={e => setAge(e.target.value)}
                    placeholder="28"
                    className="w-20 bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm text-slate-100 focus:outline-none focus:border-emerald-500"
                  />
                  <span className="text-sm text-slate-400">years</span>
                </div>
              </div>
              <div>
                <label className="text-xs text-slate-400 block mb-1.5">Sex (for calorie calculation)</label>
                <div className="flex gap-2">
                  {(['male', 'female', 'other'] as Sex[]).map(s => (
                    <button
                      key={s}
                      onClick={() => setSex(s)}
                      className={`px-4 py-1.5 text-sm rounded-lg border transition-colors cursor-pointer capitalize
                        ${sex === s ? 'border-emerald-500 bg-emerald-950/30 text-emerald-300' : 'border-slate-700 text-slate-400 hover:border-slate-600'}`}
                    >
                      {s}
                    </button>
                  ))}
                </div>
              </div>
            </div>
          )}

          {/* Step 2: Activity Level */}
          {step === 2 && (
            <div className="space-y-2.5">
              {ACTIVITY_LEVELS.map(a => (
                <button
                  key={a.value}
                  onClick={() => setActivityLevel(a.value)}
                  className={`w-full text-left p-3.5 rounded-xl border transition-colors cursor-pointer
                    ${activityLevel === a.value ? 'border-emerald-500 bg-emerald-950/30' : 'border-slate-700 hover:border-slate-600'}`}
                >
                  <div className="font-medium text-slate-100">{a.label}</div>
                  <div className="text-xs text-slate-400 mt-0.5">{a.description}</div>
                </button>
              ))}
            </div>
          )}

          {/* Step 3: Macro Targets */}
          {step === 3 && tdee && autoCal && autoPro && (
            <div className="space-y-5">
              <div className="bg-slate-800 rounded-xl p-4 space-y-2">
                <div className="text-xs text-slate-500 uppercase tracking-wide">Your TDEE</div>
                <div className="text-3xl font-bold text-slate-100">{tdee} <span className="text-lg text-slate-400">kcal/day</span></div>
                <div className="text-sm text-slate-400">
                  Goal-adjusted target: <span className="text-emerald-400 font-semibold">{autoCal} kcal · {autoPro}g protein</span>
                </div>
              </div>

              <div className="space-y-3">
                <p className="text-xs text-slate-400">Override daily targets (leave blank to use recommended):</p>
                <div className="flex gap-3">
                  <div className="flex-1">
                    <label className="text-xs text-slate-500 block mb-1">Calories</label>
                    <input
                      type="number"
                      value={calorieOverride}
                      onChange={e => setCalorieOverride(e.target.value)}
                      placeholder={String(autoCal)}
                      className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm text-slate-100 focus:outline-none focus:border-emerald-500"
                    />
                  </div>
                  <div className="flex-1">
                    <label className="text-xs text-slate-500 block mb-1">Protein (g)</label>
                    <input
                      type="number"
                      value={proteinOverride}
                      onChange={e => setProteinOverride(e.target.value)}
                      placeholder={String(autoPro)}
                      className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm text-slate-100 focus:outline-none focus:border-emerald-500"
                    />
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Step 4: Summary */}
          {step === 4 && (
            <div className="space-y-4">
              <div className="bg-slate-800 rounded-xl p-4 space-y-2 text-sm">
                <div className="flex justify-between"><span className="text-slate-400">Goal</span><span className="text-slate-100 capitalize">{goal}</span></div>
                {tdee && <div className="flex justify-between"><span className="text-slate-400">TDEE</span><span className="text-slate-100">{tdee} kcal</span></div>}
                {autoCal && <div className="flex justify-between"><span className="text-slate-400">Daily calories</span><span className="text-emerald-400 font-semibold">{calorieOverride || autoCal} kcal</span></div>}
                {autoPro && <div className="flex justify-between"><span className="text-slate-400">Daily protein</span><span className="text-emerald-400 font-semibold">{proteinOverride || autoPro}g</span></div>}
                <div className="flex justify-between"><span className="text-slate-400">Meal style</span><span className="text-slate-100">Simple</span></div>
                <div className="flex justify-between"><span className="text-slate-400">Skill level</span><span className="text-slate-100">Intermediate</span></div>
              </div>
              <p className="text-xs text-slate-500">You can update any of this in Profile settings.</p>
            </div>
          )}

          {/* Navigation */}
          <div className="flex justify-between mt-8">
            {step > 0 ? (
              <Button variant="ghost" onClick={() => setStep(s => s - 1)}>Back</Button>
            ) : <div />}

            {step < 4 ? (
              <Button
                variant="primary"
                onClick={() => setStep(s => s + 1)}
                disabled={step === 1 && !isMetricsValid}
              >
                Continue
              </Button>
            ) : (
              <Button
                variant="primary"
                onClick={handleFinish}
                loading={updateProfile.isPending}
              >
                Start Planning
              </Button>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
