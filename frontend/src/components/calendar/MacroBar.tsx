interface MacroBarProps {
  calories: number
  protein: number
  carbs: number
  fat: number
  targetCalories?: number
  targetProtein?: number
  compact?: boolean
}

function pct(val: number, target: number): number {
  if (!target) return 0
  return Math.min((val / target) * 100, 120)
}

function barColor(val: number, target: number): string {
  if (!target) return 'bg-slate-600'
  const ratio = val / target
  if (ratio < 0.6 || ratio > 1.3) return 'bg-rose-500'
  if (ratio < 0.8 || ratio > 1.1) return 'bg-amber-400'
  return 'bg-emerald-500'
}

export function MacroBar({ calories, protein, carbs, fat, targetCalories, compact }: MacroBarProps) {
  if (compact) {
    return (
      <span className="text-xs text-slate-400">
        <span className={calories > 0 ? 'text-slate-200' : ''}>{Math.round(calories)} kcal</span>
        {' · '}
        <span className="text-emerald-400">{Math.round(protein)}g P</span>
      </span>
    )
  }

  return (
    <div className="space-y-1">
      <div className="flex gap-1.5 text-xs text-slate-400 mb-1">
        <span><span className="text-slate-200 font-medium">{Math.round(calories)}</span> kcal</span>
        <span>·</span>
        <span><span className="text-emerald-400 font-medium">{Math.round(protein)}g</span> P</span>
        <span>·</span>
        <span><span className="text-amber-400 font-medium">{Math.round(carbs)}g</span> C</span>
        <span>·</span>
        <span><span className="text-slate-300 font-medium">{Math.round(fat)}g</span> F</span>
      </div>
      {targetCalories && (
        <div className="flex gap-0.5 h-1.5 rounded-full overflow-hidden bg-slate-800">
          <div
            className={`h-full transition-all ${barColor(calories, targetCalories)}`}
            style={{ width: `${pct(calories, targetCalories)}%` }}
          />
        </div>
      )}
    </div>
  )
}
