import { useState, useEffect, useRef, useCallback } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { profileApi } from '../../api/profile'
import type { UserProfile } from '../../types'
import { deriveCarbsFat } from '../../lib/units'

type SaveStatus = 'idle' | 'saving' | 'saved'

export function MacroTargets() {
  const qc = useQueryClient()
  const { data: profile } = useQuery({ queryKey: ['profile'], queryFn: profileApi.get })
  const { data: tdee } = useQuery({ queryKey: ['tdee'], queryFn: profileApi.getTdee })

  const [calories, setCalories] = useState('')
  const [protein, setProtein]   = useState('')
  const [carbs, setCarbs]       = useState('')
  const [fat, setFat]           = useState('')
  const [carbsLocked, setCarbsLocked] = useState(false)
  const [fatLocked, setFatLocked]     = useState(false)
  const [status, setStatus]     = useState<SaveStatus>('idle')

  const initialized = useRef(false)
  const timerRef = useRef<ReturnType<typeof setTimeout>>()

  // Initialize from saved profile (only once per profile load)
  useEffect(() => {
    if (!profile) return
    initialized.current = false
    const cal = profile.calorie_target
    const pro = profile.protein_target_g
    if (cal != null) setCalories(String(cal))
    if (pro != null) setProtein(String(pro))

    if (cal != null && pro != null) {
      const { fat: autoFat, carbs: autoCarbs } = deriveCarbsFat(cal, pro)
      const savedCarbs = profile.carbs_target_g
      const savedFat   = profile.fat_target_g
      if (savedCarbs != null && savedCarbs !== autoCarbs) {
        setCarbs(String(savedCarbs)); setCarbsLocked(true)
      } else {
        setCarbs(String(autoCarbs))
      }
      if (savedFat != null && savedFat !== autoFat) {
        setFat(String(savedFat)); setFatLocked(true)
      } else {
        setFat(String(autoFat))
      }
    }
    // Delay marking initialized so the above state writes don't trigger a save
    setTimeout(() => { initialized.current = true }, 100)
  }, [profile?.calorie_target, profile?.protein_target_g, profile?.carbs_target_g, profile?.fat_target_g])

  // Auto-recalculate carbs & fat when calories or protein change
  useEffect(() => {
    const cal = Number(calories)
    const pro = Number(protein)
    if (!cal || !pro) return
    const { fat: autoFat, carbs: autoCarbs } = deriveCarbsFat(cal, pro)
    if (!carbsLocked) setCarbs(String(autoCarbs))
    if (!fatLocked)   setFat(String(autoFat))
  }, [calories, protein, carbsLocked, fatLocked])

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

  // Auto-save whenever any macro value changes (debounced)
  useEffect(() => {
    if (!initialized.current) return
    clearTimeout(timerRef.current)
    timerRef.current = setTimeout(() => {
      update.mutate({
        calorie_target:   calories ? Number(calories) : undefined,
        protein_target_g: protein  ? Number(protein)  : undefined,
        carbs_target_g:   carbs    ? Number(carbs)     : undefined,
        fat_target_g:     fat      ? Number(fat)       : undefined,
      })
    }, 700)
  }, [calories, protein, carbs, fat])

  if (!profile) return null

  const recCal = tdee?.recommended_calories
  const recPro = tdee?.recommended_protein_g

  const inputClass = `
    w-24 bg-slate-800 border border-slate-700 rounded-lg px-3 py-2
    text-sm text-slate-100 focus:outline-none focus:border-emerald-500
    text-right tabular-nums transition-colors
  `

  const rows = [
    {
      label: 'Calories', unit: 'kcal',
      value: calories, setValue: setCalories,
      rec: recCal, derived: false,
    },
    {
      label: 'Protein', unit: 'g',
      value: protein, setValue: setProtein,
      rec: recPro, derived: false,
    },
    {
      label: 'Carbs', unit: 'g',
      value: carbs,
      setValue: (v: string) => { setCarbsLocked(true); setCarbs(v) },
      derived: true, locked: carbsLocked,
      onUnlock: () => {
        setCarbsLocked(false)
        const { carbs: auto } = deriveCarbsFat(Number(calories), Number(protein))
        setCarbs(String(auto))
      },
    },
    {
      label: 'Fat', unit: 'g',
      value: fat,
      setValue: (v: string) => { setFatLocked(true); setFat(v) },
      derived: true, locked: fatLocked,
      onUnlock: () => {
        setFatLocked(false)
        const { fat: auto } = deriveCarbsFat(Number(calories), Number(protein))
        setFat(String(auto))
      },
    },
  ]

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="font-semibold text-slate-100">Daily Targets</h3>
        <div className="flex items-center gap-3">
          <span className="text-[11px] text-slate-600">Carbs & fat auto-calc from calories</span>
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
      </div>

      <div className="space-y-3">
        {rows.map(({ label, unit, value, setValue, rec, derived, locked, onUnlock }) => (
          <div key={label} className="flex items-center justify-between gap-4">
            <div className="min-w-0">
              <div className="flex items-center gap-2">
                <span className="text-sm text-slate-300">{label}</span>
                {derived && !locked && (
                  <span className="text-[10px] text-slate-600 bg-slate-800 px-1.5 py-0.5 rounded-full">auto</span>
                )}
                {derived && locked && (
                  <span className="text-[10px] text-amber-500 bg-amber-500/10 px-1.5 py-0.5 rounded-full">custom</span>
                )}
              </div>
              {rec != null && !derived && Number(value) !== rec && (
                <button
                  onClick={() => setValue(String(rec))}
                  className="text-[11px] text-slate-600 hover:text-emerald-400 transition-colors cursor-pointer mt-0.5"
                >
                  Recommended: {rec} {unit}
                </button>
              )}
              {derived && (
                <button
                  onClick={locked ? onUnlock : undefined}
                  className={`text-[11px] transition-colors cursor-pointer mt-0.5 ${locked ? 'text-slate-600 hover:text-slate-400' : 'text-slate-700'}`}
                >
                  {locked ? '↩ Reset to auto' : ''}
                </button>
              )}
            </div>

            <div className="flex items-center gap-2 shrink-0">
              <input
                type="number"
                value={value}
                onChange={e => setValue(e.target.value)}
                readOnly={derived && !locked}
                className={`${inputClass} ${derived && !locked ? 'text-slate-500 cursor-default' : ''}`}
              />
              <span className="text-xs text-slate-500 w-8">{unit}</span>
            </div>
          </div>
        ))}
      </div>

      {/* Calorie sanity check */}
      {calories && protein && carbs && fat && (() => {
        const total = Number(protein) * 4 + Number(carbs) * 4 + Number(fat) * 9
        const diff = Math.abs(total - Number(calories))
        return diff > 50 ? (
          <div className="text-xs text-amber-500 bg-amber-500/10 rounded-lg px-3 py-2">
            Macro calories ({Math.round(total)} kcal) differ from calorie target by {Math.round(diff)} kcal
          </div>
        ) : null
      })()}
    </div>
  )
}
