import { useState } from 'react'
import type { DayMeal } from '../../types'
import { mealLabel } from '../../lib/mealLabels'
import { Badge } from '../ui/Badge'

interface MealRowProps {
  meal: DayMeal
  date: string
  totalMeals?: number
  readOnly?: boolean
  onToggleEaten: (eaten: boolean) => void
  onToggleSkipped: (skipped: boolean) => void
  prepServingsRemaining?: number
}

export function MealRow({ meal, totalMeals, readOnly, onToggleEaten, onToggleSkipped, prepServingsRemaining }: MealRowProps) {
  const [expanded, setExpanded] = useState(false)

  const cal = Math.round(meal.calories_est ?? 0)
  const pro = Math.round(meal.protein_g_est ?? 0)
  const carb = Math.round(meal.carbs_g_est ?? 0)
  const fat = Math.round(meal.fat_g_est ?? 0)

  const isEaten = meal.eaten
  const isSkipped = meal.skipped

  // instructions arrive as string[] (review stream) or newline-joined string (DB).
  const steps = (Array.isArray(meal.instructions)
    ? meal.instructions
    : (meal.instructions ?? '').split('\n'))
    .map(s => s.trim())
    .filter(Boolean)

  return (
    <div className={`
      rounded-xl transition-all
      ${isEaten   ? 'bg-emerald-500/5 border border-emerald-800/40'
      : isSkipped ? 'bg-slate-800/30 border border-slate-700/30 opacity-50'
      :              'bg-slate-800/50 border border-slate-700/40 hover:border-slate-600/60'}
    `}>
      <div className="flex items-start gap-3 px-3 py-3">
        {/* Checkbox */}
        <button
          onClick={() => !isSkipped && !readOnly && onToggleEaten(!isEaten)}
          disabled={isSkipped || readOnly}
          className={`
            mt-0.5 w-5 h-5 rounded-md shrink-0 flex items-center justify-center border transition-all cursor-pointer
            ${isEaten
              ? 'bg-emerald-500 border-emerald-500'
              : 'border-slate-600 hover:border-emerald-500 bg-transparent'}
          `}
        >
          {isEaten && (
            <svg className="w-3 h-3 text-slate-950" fill="none" viewBox="0 0 12 12">
              <path d="M2.5 6l2.5 2.5L9.5 3.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          )}
        </button>

        {/* Content */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 min-w-0">
            <span className="text-[10px] font-semibold text-slate-600 uppercase tracking-wider shrink-0">
              {mealLabel(meal.meal_number, totalMeals ?? 0)}
            </span>
            <span className={`text-sm font-semibold truncate ${isEaten ? 'text-slate-400 line-through' : 'text-slate-100'}`}>
              {meal.recipe_name}
            </span>
            {meal.prep_id && (
              <Badge color="violet" size="sm">
                {prepServingsRemaining != null ? `×${prepServingsRemaining}` : 'Batch'}
              </Badge>
            )}
          </div>

          {meal.brief_description && !isSkipped && (
            <p className="text-xs text-slate-500 mt-0.5 line-clamp-1">{meal.brief_description}</p>
          )}

          {cal > 0 && (
            <div className="flex items-center gap-2 mt-1.5 text-[11px]">
              <span className="text-slate-300 font-medium">{cal.toLocaleString()} kcal</span>
              <span className="text-slate-700">·</span>
              <span className="text-emerald-500 font-semibold">{pro}g P</span>
              <span className="text-slate-700">·</span>
              <span className="text-amber-500">{carb}g C</span>
              <span className="text-slate-700">·</span>
              <span className="text-slate-400">{fat}g F</span>
              {meal.cook_time_minutes ? (
                <>
                  <span className="text-slate-700">·</span>
                  <span className="text-slate-500">{meal.cook_time_minutes}m</span>
                </>
              ) : null}
            </div>
          )}
        </div>

        {/* Actions */}
        <div className="flex items-center gap-1 shrink-0">
          {(meal.ingredients.length > 0 || meal.brief_description || steps.length > 0) && (
            <button
              onClick={() => setExpanded(e => !e)}
              className="w-7 h-7 flex items-center justify-center rounded-lg text-slate-500 hover:text-slate-300 hover:bg-slate-700 transition-colors cursor-pointer"
            >
              <svg className={`w-3.5 h-3.5 transition-transform ${expanded ? 'rotate-180' : ''}`} fill="none" viewBox="0 0 14 14">
                <path d="M3 5l4 4 4-4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            </button>
          )}
          {!isEaten && !readOnly && (
            <button
              onClick={() => onToggleSkipped(!isSkipped)}
              className="px-2 py-1 text-[11px] font-medium text-slate-500 hover:text-slate-300 hover:bg-slate-700 rounded-md transition-colors cursor-pointer"
            >
              {isSkipped ? 'Undo' : 'Skip'}
            </button>
          )}
        </div>
      </div>

      {/* Expanded detail — full name, full description, ingredients */}
      {expanded && (
        <div className="px-3 pb-3 border-t border-slate-700/40 mt-0 pt-2.5 space-y-3">
          {/* Full recipe name (header truncates; show it in full here) */}
          <p className="text-sm font-semibold text-slate-100">{meal.recipe_name}</p>

          {meal.brief_description && (
            <p className="text-xs text-slate-400 leading-relaxed whitespace-pre-line">
              {meal.brief_description}
            </p>
          )}

          {steps.length > 0 && (
            <div>
              <p className="text-[10px] font-semibold text-slate-600 uppercase tracking-wider mb-2">Steps</p>
              <ol className="space-y-1.5">
                {steps.map((step, i) => (
                  <li key={i} className="text-xs text-slate-300 flex gap-2">
                    <span className="text-slate-600 font-semibold shrink-0">{i + 1}.</span>
                    <span className="leading-relaxed">{step}</span>
                  </li>
                ))}
              </ol>
            </div>
          )}

          {meal.ingredients.length > 0 && (
            <div>
              <p className="text-[10px] font-semibold text-slate-600 uppercase tracking-wider mb-2">Ingredients</p>
              <ul className="grid grid-cols-2 gap-x-6 gap-y-1">
                {meal.ingredients
                  .filter(i => i.quantity_type !== 'trace')
                  .map((ing, i) => (
                    <li key={i} className="text-xs text-slate-300 flex gap-1">
                      {ing.quantity && (
                        <span className="text-slate-500 shrink-0">{ing.quantity}{ing.unit ? ` ${ing.unit}` : ''}</span>
                      )}
                      <span>{ing.item}</span>
                    </li>
                  ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
