import type { MealDay } from '../../types'
import { kgToLbs } from '../../lib/units'

interface DayCellProps {
  date: string
  today: string
  day?: MealDay
  isCurrentMonth: boolean
  selected: boolean
  isOpen?: boolean
  weightKg?: number
  calorieTarget?: number | null
  proteinTarget?: number | null
  onPointerDown: (date: string) => void
  onPointerEnter: (date: string) => void
  onClick: (date: string) => void
}

export function DayCell({
  date, today, day, isCurrentMonth, selected, isOpen, weightKg,
  calorieTarget, proteinTarget,
  onPointerDown, onPointerEnter, onClick,
}: DayCellProps) {
  const dayNum = parseInt(date.split('-')[2])
  const isPast = date < today
  const isToday = date === today
  const isOutOfMonth = !isCurrentMonth

  const meals = day?.meals ?? []
  const totalCal = meals.reduce((s, m) => s + (m.calories_est ?? 0), 0)
  const totalPro = meals.reduce((s, m) => s + (m.protein_g_est ?? 0), 0)
  const mealCount = meals.length
  const hasPlan = mealCount > 0

  // On-target: within ~20% of both calorie and protein targets (matches the
  // backend nutrition check). Null when we can't judge (no plan / no targets).
  const onTarget = hasPlan && calorieTarget && proteinTarget
    ? Math.abs(totalCal - calorieTarget) / calorieTarget <= 0.2 &&
      Math.abs(totalPro - proteinTarget) / proteinTarget <= 0.2
    : null

  const proteinPct = proteinTarget && hasPlan
    ? Math.min(100, Math.round((totalPro / proteinTarget) * 100))
    : null

  // Logged progress (today + past planned days)
  const eatenCount = meals.filter(m => m.eaten).length
  const showEaten = (isPast || isToday) && hasPlan

  const isSelectable = !isPast && isCurrentMonth && !hasPlan
  const isViewable = isCurrentMonth && (hasPlan || isPast || isToday)

  if (isOutOfMonth) {
    return (
      <div className="min-h-[92px] rounded-xl bg-slate-950 opacity-20 p-2.5 select-none">
        <span className="text-xs text-slate-600">{dayNum}</span>
      </div>
    )
  }

  let cardBg = 'bg-slate-900'
  let cardBorder = 'border border-slate-800/80'
  let leftAccent = ''

  if (selected) {
    cardBg = 'bg-emerald-950/40'
    cardBorder = 'border border-emerald-500/60 ring-1 ring-emerald-500/40'
  } else if (day?.status === 'completed') {
    leftAccent = 'border-l-2 border-l-emerald-500'
    cardBorder = 'border border-slate-800/80 border-l-0'
  } else if (isPast && day?.status === 'planned') {
    leftAccent = 'border-l-2 border-l-amber-400'
    cardBorder = 'border border-slate-800/80 border-l-0'
  } else if (isToday) {
    cardBorder = 'border border-blue-500/30'
  }

  // Active-day ring — marks the cell whose panel is currently open. Layered over
  // the status accent so you can still see the day's state.
  const openRing = isOpen && !selected
    ? 'ring-2 ring-slate-100/70 ring-offset-2 ring-offset-slate-950'
    : ''

  const hoverClass = (isSelectable || isViewable)
    ? 'hover:bg-slate-800 cursor-pointer'
    : 'cursor-default'

  const dimClass = isPast && !isToday ? 'opacity-60' : ''

  return (
    <div
      className={`
        relative min-h-[92px] rounded-xl p-2.5 select-none transition-all duration-100
        ${cardBg} ${cardBorder} ${leftAccent} ${openRing} ${hoverClass} ${dimClass}
      `}
      onPointerDown={isSelectable ? () => onPointerDown(date) : undefined}
      onPointerEnter={isSelectable ? () => onPointerEnter(date) : undefined}
      onClick={() => (isSelectable || isViewable) && onClick(date)}
    >
      {/* Date number + count */}
      <div className="flex items-start justify-between mb-1.5">
        {isToday ? (
          <span className="w-6 h-6 flex items-center justify-center rounded-full bg-blue-500 text-white text-xs font-bold leading-none">
            {dayNum}
          </span>
        ) : (
          <span className={`text-sm font-medium leading-none ${isPast ? 'text-slate-500' : 'text-slate-300'}`}>
            {dayNum}
          </span>
        )}

        {mealCount > 0 && (
          <div className="flex items-center gap-1">
            {/* On-target dot */}
            {onTarget !== null && (
              <span
                title={onTarget ? 'On target' : 'Off target'}
                className={`w-1.5 h-1.5 rounded-full ${onTarget ? 'bg-emerald-400' : 'bg-amber-400'}`}
              />
            )}
            <span className={`
              text-[10px] font-semibold px-1.5 py-0.5 rounded-full leading-none
              ${day?.status === 'completed'
                ? 'bg-emerald-500/20 text-emerald-400'
                : isPast
                ? 'bg-amber-400/15 text-amber-500'
                : 'bg-slate-700 text-slate-400'}
            `}>
              {mealCount}
            </span>
          </div>
        )}
      </div>

      {/* Macro info */}
      {mealCount > 0 && totalCal > 0 && (
        <div className="mt-auto space-y-0.5">
          <div className={`text-xs font-medium ${isPast ? 'text-slate-500' : 'text-slate-300'}`}>
            {Math.round(totalCal).toLocaleString()} kcal
          </div>
          <div className={`text-[11px] font-semibold ${isPast ? 'text-emerald-700' : 'text-emerald-500'}`}>
            {Math.round(totalPro)}g P
          </div>

          {/* Protein vs target bar */}
          {proteinPct !== null && (
            <div className="h-1 rounded-full bg-slate-700/50 overflow-hidden" title={`${proteinPct}% of protein target`}>
              <div className="h-full bg-emerald-500/70 rounded-full" style={{ width: `${proteinPct}%` }} />
            </div>
          )}

          {/* Eaten progress (today / past) */}
          {showEaten && (
            <div className="flex items-center gap-1 text-[10px] text-slate-500 pt-0.5">
              <svg className="w-2.5 h-2.5 text-emerald-500/80" fill="none" viewBox="0 0 12 12">
                <path d="M2.5 6l2.5 2.5L9.5 3" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
              {eatenCount}/{mealCount}
            </div>
          )}
        </div>
      )}

      {/* Weight badge */}
      {weightKg != null && (
        <div className="absolute bottom-2 right-2 text-[10px] text-slate-500 flex items-center gap-0.5">
          <svg className="w-2.5 h-2.5 text-slate-600" fill="none" viewBox="0 0 12 12">
            <circle cx="6" cy="5" r="3" stroke="currentColor" strokeWidth="1.2" />
            <path d="M3 10c0-1.66 1.34-3 3-3s3 1.34 3 3" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" />
          </svg>
          {Math.round(kgToLbs(weightKg))}
        </div>
      )}

      {/* Selected checkmark */}
      {selected && (
        <div className="absolute top-2 right-2 w-4 h-4 rounded-full bg-emerald-500 flex items-center justify-center">
          <svg className="w-2.5 h-2.5 text-slate-950" fill="none" viewBox="0 0 10 10">
            <path d="M2 5l2.5 2.5L8 3" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        </div>
      )}
    </div>
  )
}
