import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { profileApi } from '../../api/profile'
import { weightLogApi } from '../../api/weightLog'

export function TdeeWidget() {
  const qc = useQueryClient()
  const { data: profile } = useQuery({ queryKey: ['profile'], queryFn: profileApi.get })
  const { data: tdee, isLoading } = useQuery({ queryKey: ['tdee'], queryFn: profileApi.getTdee })
  const { data: measured } = useQuery({
    queryKey: ['measured-tdee'],
    queryFn: weightLogApi.getMeasuredTdee,
  })

  const [overrideMode, setOverrideMode] = useState(false)
  const [overrideVal, setOverrideVal] = useState('')
  const [saved, setSaved] = useState(false)
  const [showMeasuredDetail, setShowMeasuredDetail] = useState(false)

  const update = useMutation({
    mutationFn: (tdeeOverride: number) =>
      profileApi.update({ tdee_override: tdeeOverride } as never),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['profile'] })
      qc.invalidateQueries({ queryKey: ['tdee'] })
      setOverrideMode(false)
      setOverrideVal('')
      setSaved(true)
      setTimeout(() => setSaved(false), 2000)
    },
  })

  if (isLoading) return <div className="text-slate-500 text-sm animate-pulse">Calculating...</div>
  if (!tdee || !profile) return null

  const activeCal  = profile.calorie_target  ?? tdee.recommended_calories
  const activePro  = profile.protein_target_g ?? tdee.recommended_protein_g
  const activeCarb = profile.carbs_target_g   ?? tdee.recommended_carbs_g
  const activeFat  = profile.fat_target_g     ?? tdee.recommended_fat_g

  const deficit = tdee.tdee - activeCal
  const usingBF = profile.body_fat_pct != null

  // If measured TDEE is available, use it as the displayed maintenance
  const maintenanceTdee = measured ? measured.measured_tdee : tdee.tdee
  const maintenanceLabel = measured ? 'Measured Maintenance' : 'Estimated Maintenance'
  const methodLabel = measured
    ? `${measured.tracked_days}d tracked`
    : usingBF ? 'Katch-McArdle' : 'Mifflin-St Jeor'

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden">
      {/* Calorie target — hero */}
      <div className="px-5 py-4 border-b border-slate-800/60 flex items-center justify-between">
        <div>
          <div className="text-xs text-slate-500 uppercase tracking-wider font-medium mb-1">Daily Calorie Target</div>
          <div className="flex items-baseline gap-2">
            <span className="text-4xl font-bold tabular-nums text-slate-100">{activeCal.toLocaleString()}</span>
            <span className="text-slate-500 text-sm">kcal</span>
          </div>
        </div>

        <div className="text-right space-y-1">
          {!overrideMode ? (
            <div>
              <div className="text-xs text-slate-600 mb-0.5 flex items-center justify-end gap-1">
                {maintenanceLabel}
                {measured && (
                  <button
                    onClick={() => setShowMeasuredDetail(d => !d)}
                    className="text-emerald-700 hover:text-emerald-500 cursor-pointer transition-colors"
                    title="How this was calculated"
                  >
                    <svg className="w-3 h-3" fill="none" viewBox="0 0 12 12">
                      <circle cx="6" cy="6" r="5" stroke="currentColor" strokeWidth="1.2" />
                      <path d="M6 5.5v3M6 4h.01" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" />
                    </svg>
                  </button>
                )}
              </div>
              <div className="flex items-baseline gap-1.5 justify-end">
                <span className={`text-lg font-semibold tabular-nums ${measured ? 'text-emerald-400' : 'text-slate-400'}`}>
                  {maintenanceTdee.toLocaleString()}
                </span>
                <span className="text-[10px] text-slate-600">{methodLabel}</span>
                <button
                  onClick={() => { setOverrideMode(true); setOverrideVal(String(maintenanceTdee)) }}
                  className="text-[10px] text-slate-600 hover:text-slate-400 cursor-pointer transition-colors"
                >
                  Override
                </button>
              </div>
              {deficit !== 0 && (
                <div className={`text-xs font-medium ${deficit > 0 ? 'text-rose-400' : 'text-emerald-400'}`}>
                  {deficit > 0 ? `−${deficit.toLocaleString()}` : `+${Math.abs(deficit).toLocaleString()}`} kcal {deficit > 0 ? 'deficit' : 'surplus'}
                </div>
              )}
            </div>
          ) : (
            <div className="flex flex-col items-end gap-1.5">
              <div className="text-xs text-slate-400">Your actual maintenance:</div>
              <div className="flex items-center gap-2">
                <input
                  type="number"
                  value={overrideVal}
                  onChange={e => setOverrideVal(e.target.value)}
                  className="w-24 bg-slate-800 border border-slate-600 rounded-lg px-2 py-1 text-sm text-slate-100 text-right tabular-nums focus:outline-none focus:border-emerald-500"
                  autoFocus
                />
                <span className="text-xs text-slate-500">kcal</span>
              </div>
              <div className="flex gap-2">
                <button
                  onClick={() => update.mutate(Number(overrideVal))}
                  disabled={!overrideVal || update.isPending}
                  className="text-xs text-emerald-400 hover:text-emerald-300 cursor-pointer disabled:opacity-40"
                >
                  Save
                </button>
                <button
                  onClick={() => setOverrideMode(false)}
                  className="text-xs text-slate-600 hover:text-slate-400 cursor-pointer"
                >
                  Cancel
                </button>
              </div>
            </div>
          )}
          {saved && <div className="text-xs text-emerald-400">Updated!</div>}
        </div>
      </div>

      {/* Measured TDEE detail */}
      {measured && showMeasuredDetail && (
        <div className="px-5 py-3 border-b border-slate-800/40 bg-emerald-500/5 text-xs text-slate-400 space-y-1">
          <div className="font-medium text-emerald-400 text-[11px] uppercase tracking-wider">How this was measured</div>
          <div className="grid grid-cols-2 gap-x-4 gap-y-0.5 text-slate-500">
            <span>Window</span>
            <span className="text-slate-300">{measured.start_date} → {measured.end_date} ({measured.window_days}d)</span>
            <span>Tracked days</span>
            <span className="text-slate-300">{measured.tracked_days} days with logged meals</span>
            <span>Avg calories eaten</span>
            <span className="text-slate-300">{measured.avg_daily_calories.toLocaleString()} kcal/day</span>
            <span>Weight change</span>
            <span className={`font-medium ${measured.end_weight_kg < measured.start_weight_kg ? 'text-emerald-400' : 'text-amber-400'}`}>
              {(measured.end_weight_kg - measured.start_weight_kg > 0 ? '+' : '')}
              {((measured.end_weight_kg - measured.start_weight_kg) * 2.20462).toFixed(1)} lbs
            </span>
          </div>
          <div className="text-[10px] text-slate-600 pt-1">
            Formula: avg calories − (weight change × 7,700 kcal/kg ÷ days)
          </div>
        </div>
      )}

      {/* Macro targets */}
      <div className="grid grid-cols-3 divide-x divide-slate-800/60">
        {[
          { label: 'Protein', value: activePro,  unit: 'g', color: 'text-sky-400',    custom: profile.protein_target_g != null && profile.protein_target_g !== tdee.recommended_protein_g },
          { label: 'Carbs',   value: activeCarb,  unit: 'g', color: 'text-amber-400',  custom: profile.carbs_target_g != null },
          { label: 'Fat',     value: activeFat,   unit: 'g', color: 'text-orange-400', custom: profile.fat_target_g != null },
        ].map(({ label, value, unit, color, custom }) => (
          <div key={label} className="px-4 py-3 text-center">
            <div className={`text-xl font-bold tabular-nums ${color}`}>
              {value}<span className="text-xs text-slate-500 font-normal ml-0.5">{unit}</span>
            </div>
            <div className="text-[10px] text-slate-600 mt-0.5 uppercase tracking-wider">{label}</div>
            {custom && <div className="text-[9px] text-amber-600 mt-0.5">custom</div>}
          </div>
        ))}
      </div>

      {/* Context */}
      <div className="px-5 py-2.5 border-t border-slate-800/60 flex items-center justify-between">
        <span className="text-[11px] text-slate-600 capitalize">
          {profile.goal?.replace('_', ' ')} · {profile.activity_level?.replace(/_/g, ' ')} · {profile.age}yo {profile.sex}
          {usingBF && ` · ${profile.body_fat_pct}% BF`}
        </span>
        {!usingBF && !measured && (
          <span className="text-[10px] text-slate-600">Add body fat % for a better estimate</span>
        )}
        {measured && (
          <span className="text-[10px] text-emerald-700">Based on {measured.tracked_days} days of data</span>
        )}
      </div>
    </div>
  )
}
