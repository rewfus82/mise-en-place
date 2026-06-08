import { useState, useEffect, useRef, useCallback } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { profileApi } from '../../api/profile'
import type { UserProfile } from '../../types'
import { kgToLbs, lbsToKg, cmToFtIn, ftInToCm } from '../../lib/units'

const ACTIVITY_OPTIONS = [
  { value: 'sedentary',         label: 'Sedentary',          desc: 'Desk job, little movement' },
  { value: 'lightly_active',    label: 'Lightly Active',     desc: '1–3 days/week light exercise' },
  { value: 'moderately_active', label: 'Moderately Active',  desc: '3–5 days/week moderate exercise' },
  { value: 'very_active',       label: 'Very Active',        desc: '6–7 days/week hard training' },
  { value: 'extra_active',      label: 'Extra Active',       desc: 'Twice/day or physical job + training' },
]

const MEAL_STYLE_OPTIONS = [
  { value: 'bland',       label: 'Bland',         desc: 'Boiled/steamed, no seasoning' },
  { value: 'simple',      label: 'Simple',        desc: '3–5 ingredients, basic seasoning' },
  { value: 'recipes',     label: 'Full Recipes',  desc: 'Complete technique + flavor' },
  { value: 'macros_only', label: 'Macros Only',   desc: 'Just list protein + carb + veg' },
]

const GOAL_OPTIONS = [
  { value: 'bulk',     label: 'Build Muscle' },
  { value: 'cut',      label: 'Lose Fat' },
  { value: 'maintain', label: 'Maintain' },
  { value: 'recomp',   label: 'Recomp' },
]

type SaveStatus = 'idle' | 'saving' | 'saved'

export function ProfileForm() {
  const qc = useQueryClient()
  const { data: profile } = useQuery({ queryKey: ['profile'], queryFn: profileApi.get })

  const [weight, setWeight]           = useState('')
  const [heightFt, setHeightFt]       = useState('')
  const [heightIn, setHeightIn]       = useState('')
  const [age, setAge]                 = useState('')
  const [sex, setSex]                 = useState('male')
  const [activityLevel, setActivity]  = useState('moderately_active')
  const [goal, setGoal]               = useState('maintain')
  const [bodyFat, setBodyFat]         = useState('')
  const [mealStyle, setMealStyle]     = useState('simple')
  const [mealsPerDay, setMealsPerDay] = useState('3')
  const [skillLevel, setSkill]        = useState('intermediate')
  const [maxCookTime, setMaxCook]     = useState('60')
  const [budget, setBudget]           = useState('')
  const [restrictions, setRestrictions] = useState('')
  const [allergies, setAllergies]     = useState('')
  const [status, setStatus]           = useState<SaveStatus>('idle')

  const pendingRef = useRef<Partial<UserProfile>>({})
  const timerRef   = useRef<ReturnType<typeof setTimeout>>(undefined)

  const update = useMutation({
    mutationFn: (data: Partial<UserProfile>) => profileApi.update(data),
    onMutate:  () => setStatus('saving'),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['profile'] })
      qc.invalidateQueries({ queryKey: ['tdee'] })
      setStatus('saved')
      setTimeout(() => setStatus('idle'), 1500)
    },
  })

  // Initialize once when profile loads
  useEffect(() => {
    if (!profile) return
    if (profile.weight_kg)  setWeight(String(Math.round(kgToLbs(profile.weight_kg))))
    if (profile.height_cm) {
      const { ft, inches } = cmToFtIn(profile.height_cm)
      setHeightFt(String(ft))
      setHeightIn(String(inches))
    }
    if (profile.age)        setAge(String(profile.age))
    if (profile.sex)        setSex(profile.sex)
    setActivity(profile.activity_level)
    setGoal(profile.goal)
    if (profile.body_fat_pct) setBodyFat(String(profile.body_fat_pct))
    setMealStyle(profile.meal_style)
    setMealsPerDay(String(profile.meals_per_day))
    setSkill(profile.skill_level)
    setMaxCook(String(profile.max_cook_time_minutes))
    if (profile.weekly_budget) setBudget(String(profile.weekly_budget))
    setRestrictions(profile.dietary_restrictions.join(', '))
    setAllergies(profile.food_allergies)
  }, [
    profile?.weight_kg, profile?.height_cm, profile?.age, profile?.sex,
    profile?.activity_level, profile?.goal, profile?.body_fat_pct,
    profile?.meal_style, profile?.meals_per_day, profile?.skill_level,
    profile?.max_cook_time_minutes, profile?.weekly_budget, profile?.food_allergies,
  ])

  const save = useCallback((partial: Partial<UserProfile>, delay = 600) => {
    pendingRef.current = { ...pendingRef.current, ...partial }
    clearTimeout(timerRef.current)
    timerRef.current = setTimeout(() => {
      const payload = pendingRef.current
      pendingRef.current = {}
      update.mutate(payload)
    }, delay)
  }, [update])

  // Instant save (selects, toggles)
  const saveNow = useCallback((partial: Partial<UserProfile>) => save(partial, 50), [save])

  const inputClass = `
    w-full bg-slate-800 border border-slate-700/80 rounded-lg px-3 py-2
    text-sm text-slate-100 placeholder-slate-600
    focus:outline-none focus:border-emerald-500/60
    transition-colors
  `

  const section = "bg-slate-900 border border-slate-800 rounded-xl p-5 space-y-4"
  const label = "text-xs font-medium text-slate-500 uppercase tracking-wider block mb-1.5"

  return (
    <div className="space-y-5">
      {/* Status indicator */}
      <div className="h-5 flex items-center justify-end">
        {status === 'saving' && (
          <div className="flex items-center gap-1.5 text-xs text-slate-500">
            <span className="w-3 h-3 border border-slate-500 border-t-transparent rounded-full animate-spin" />
            Saving...
          </div>
        )}
        {status === 'saved' && (
          <div className="flex items-center gap-1.5 text-xs text-emerald-500">
            <svg className="w-3 h-3" fill="none" viewBox="0 0 12 12">
              <path d="M2 6l2.5 2.5L10 3" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
            Saved
          </div>
        )}
      </div>

      {/* Body metrics */}
      <section className={section}>
        <h3 className="font-semibold text-slate-100">Body Metrics</h3>
        <div className="grid grid-cols-2 gap-4">

          <div>
            <label className={label}>Weight</label>
            <div className="flex gap-2 items-center">
              <input
                type="number" value={weight} placeholder="200"
                onChange={e => { setWeight(e.target.value); save({ weight_kg: lbsToKg(Number(e.target.value)) }) }}
                className="w-24 bg-slate-800 border border-slate-700/80 rounded-lg px-3 py-2 text-sm text-slate-100 focus:outline-none focus:border-emerald-500/60"
              />
              <span className="text-xs text-slate-500">lbs</span>
            </div>
          </div>

          <div>
            <label className={label}>Height</label>
            <div className="flex gap-2 items-center">
              <input
                type="number" value={heightFt} placeholder="5"
                onChange={e => {
                  setHeightFt(e.target.value)
                  save({ height_cm: ftInToCm(Number(e.target.value), Number(heightIn)) })
                }}
                className="w-14 bg-slate-800 border border-slate-700/80 rounded-lg px-2 py-2 text-sm text-slate-100 text-center focus:outline-none focus:border-emerald-500/60"
              />
              <span className="text-xs text-slate-500">ft</span>
              <input
                type="number" value={heightIn} placeholder="6"
                onChange={e => {
                  setHeightIn(e.target.value)
                  save({ height_cm: ftInToCm(Number(heightFt), Number(e.target.value)) })
                }}
                className="w-14 bg-slate-800 border border-slate-700/80 rounded-lg px-2 py-2 text-sm text-slate-100 text-center focus:outline-none focus:border-emerald-500/60"
              />
              <span className="text-xs text-slate-500">in</span>
            </div>
          </div>

          <div>
            <label className={label}>Age</label>
            <div className="flex gap-2 items-center">
              <input
                type="number" value={age} placeholder="30"
                onChange={e => { setAge(e.target.value); save({ age: Number(e.target.value) }) }}
                className="w-20 bg-slate-800 border border-slate-700/80 rounded-lg px-3 py-2 text-sm text-slate-100 focus:outline-none focus:border-emerald-500/60"
              />
              <span className="text-xs text-slate-500">yrs</span>
            </div>
          </div>

          <div>
            <label className={label}>Body Fat %</label>
            <div className="flex gap-2 items-center">
              <input
                type="number" value={bodyFat} placeholder="15"
                onChange={e => { setBodyFat(e.target.value); save({ body_fat_pct: Number(e.target.value) || null }) }}
                className="w-20 bg-slate-800 border border-slate-700/80 rounded-lg px-3 py-2 text-sm text-slate-100 focus:outline-none focus:border-emerald-500/60"
              />
              <span className="text-xs text-slate-500">%</span>
            </div>
          </div>
        </div>

        {/* Sex */}
        <div>
          <label className={label}>Sex</label>
          <div className="flex gap-2">
            {['male', 'female', 'other'].map(s => (
              <button
                key={s} onClick={() => { setSex(s); saveNow({ sex: s }) }}
                className={`px-4 py-1.5 text-sm rounded-lg border transition-colors cursor-pointer capitalize
                  ${sex === s ? 'border-emerald-500/60 bg-emerald-500/10 text-emerald-300' : 'border-slate-700 text-slate-400 hover:border-slate-500'}`}
              >
                {s}
              </button>
            ))}
          </div>
        </div>

        {/* Goal */}
        <div>
          <label className={label}>Goal</label>
          <div className="grid grid-cols-4 gap-2">
            {GOAL_OPTIONS.map(g => (
              <button
                key={g.value} onClick={() => { setGoal(g.value); saveNow({ goal: g.value }) }}
                className={`py-2 text-sm rounded-lg border transition-colors cursor-pointer
                  ${goal === g.value ? 'border-emerald-500/60 bg-emerald-500/10 text-emerald-300 font-medium' : 'border-slate-700 text-slate-400 hover:border-slate-500'}`}
              >
                {g.label}
              </button>
            ))}
          </div>
        </div>

        {/* Activity */}
        <div>
          <label className={label}>Activity Level</label>
          <div className="space-y-1.5">
            {ACTIVITY_OPTIONS.map(a => (
              <button
                key={a.value} onClick={() => { setActivity(a.value); saveNow({ activity_level: a.value }) }}
                className={`w-full flex items-center justify-between px-3 py-2.5 rounded-lg border transition-colors cursor-pointer text-left
                  ${activityLevel === a.value ? 'border-emerald-500/60 bg-emerald-500/10' : 'border-slate-700/60 hover:border-slate-600'}`}
              >
                <span className={`text-sm font-medium ${activityLevel === a.value ? 'text-emerald-300' : 'text-slate-300'}`}>{a.label}</span>
                <span className="text-xs text-slate-500">{a.desc}</span>
              </button>
            ))}
          </div>
        </div>
      </section>

      {/* Meal preferences */}
      <section className={section}>
        <h3 className="font-semibold text-slate-100">Meal Preferences</h3>

        {/* Meal style */}
        <div>
          <label className={label}>Meal Style</label>
          <div className="grid grid-cols-2 gap-2">
            {MEAL_STYLE_OPTIONS.map(opt => (
              <button
                key={opt.value} onClick={() => { setMealStyle(opt.value); saveNow({ meal_style: opt.value }) }}
                className={`text-left p-3 rounded-lg border transition-colors cursor-pointer
                  ${mealStyle === opt.value ? 'border-emerald-500/60 bg-emerald-500/10' : 'border-slate-700/60 hover:border-slate-600'}`}
              >
                <div className={`text-sm font-medium ${mealStyle === opt.value ? 'text-emerald-300' : 'text-slate-200'}`}>{opt.label}</div>
                <div className="text-xs text-slate-500 mt-0.5">{opt.desc}</div>
              </button>
            ))}
          </div>
        </div>

        <div className="grid grid-cols-3 gap-4">
          <div>
            <label className={label}>Meals/day</label>
            <input
              type="number" min="2" max="8" value={mealsPerDay}
              onChange={e => { setMealsPerDay(e.target.value); save({ meals_per_day: Number(e.target.value) }, 300) }}
              className={inputClass}
            />
          </div>
          <div>
            <label className={label}>Skill level</label>
            <select
              value={skillLevel}
              onChange={e => { setSkill(e.target.value); saveNow({ skill_level: e.target.value }) }}
              className={inputClass}
            >
              <option value="beginner">Beginner</option>
              <option value="intermediate">Intermediate</option>
              <option value="advanced">Advanced</option>
            </select>
          </div>
          <div>
            <label className={label}>Max cook time</label>
            <div className="flex gap-2 items-center">
              <input
                type="number" value={maxCookTime}
                onChange={e => { setMaxCook(e.target.value); save({ max_cook_time_minutes: Number(e.target.value) }) }}
                className="w-20 bg-slate-800 border border-slate-700/80 rounded-lg px-3 py-2 text-sm text-slate-100 focus:outline-none focus:border-emerald-500/60"
              />
              <span className="text-xs text-slate-500">min</span>
            </div>
          </div>
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className={label}>Weekly budget</label>
            <div className="flex gap-2 items-center">
              <span className="text-slate-500 text-sm">$</span>
              <input
                type="number" value={budget} placeholder="—"
                onChange={e => { setBudget(e.target.value); save({ weekly_budget: Number(e.target.value) || null }) }}
                className="flex-1 bg-slate-800 border border-slate-700/80 rounded-lg px-3 py-2 text-sm text-slate-100 focus:outline-none focus:border-emerald-500/60"
              />
            </div>
          </div>
        </div>

        <div>
          <label className={label}>Dietary restrictions <span className="normal-case text-slate-600">(comma-separated)</span></label>
          <input
            type="text" value={restrictions} placeholder="vegetarian, gluten-free"
            onChange={e => {
              setRestrictions(e.target.value)
              save({ dietary_restrictions: e.target.value.split(',').map(s => s.trim()).filter(Boolean) })
            }}
            className={inputClass}
          />
        </div>

        <div>
          <label className={label}>Allergies</label>
          <input
            type="text" value={allergies} placeholder="peanuts, shellfish"
            onChange={e => { setAllergies(e.target.value); save({ food_allergies: e.target.value }) }}
            className={inputClass}
          />
        </div>
      </section>
    </div>
  )
}
