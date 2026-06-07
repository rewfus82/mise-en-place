import { useState } from 'react'
import { Modal } from '../ui/Modal'
import { Button } from '../ui/Button'
import { useCalendarMutations } from '../../hooks/useCalendar'
import { AmbiguousQtyPrompt } from './AmbiguousQtyPrompt'
import type { MealDay } from '../../types'

interface DailyConfirmModalProps {
  days: MealDay[]
  onDone: () => void
}

interface AmbiguousItem {
  item: string
  quantity: string | null
  unit: string | null
}

export function DailyConfirmModal({ days, onDone }: DailyConfirmModalProps) {
  const [idx, setIdx] = useState(0)
  const [eatenIds, setEatenIds] = useState<Set<number>>(new Set())
  const [ambiguousItems, setAmbiguousItems] = useState<AmbiguousItem[] | null>(null)
  const { endDay, skipDay } = useCalendarMutations()

  if (days.length === 0) return null

  const day = days[idx]
  const isLast = idx === days.length - 1

  const toggleMeal = (mealId: number) =>
    setEatenIds(prev => {
      const next = new Set(prev)
      next.has(mealId) ? next.delete(mealId) : next.add(mealId)
      return next
    })

  const advance = () => {
    if (isLast) onDone()
    else setIdx(i => i + 1)
    setEatenIds(new Set())
  }

  const handleEndDay = async () => {
    const result = await endDay.mutateAsync(day.date)
    const needs = (result.needs_confirmation ?? []) as AmbiguousItem[]
    if (needs.length > 0) {
      setAmbiguousItems(needs)
    } else {
      advance()
    }
  }

  const handleSkip = async () => {
    await skipDay.mutateAsync(day.date)
    advance()
  }

  const formattedDate = new Date(day.date + 'T12:00:00').toLocaleDateString('en-US', {
    weekday: 'long', month: 'short', day: 'numeric',
  })

  return (
    <>
      <Modal open blocking title={`Day ${idx + 1} of ${days.length} — ${formattedDate}`}>
        <div className="space-y-4">
          <p className="text-sm text-slate-400">Check off the meals you ate:</p>

          <div className="space-y-2">
            {day.meals.map(meal => (
              <label
                key={meal.id}
                className="flex items-start gap-3 cursor-pointer p-2.5 rounded-lg hover:bg-slate-800"
              >
                <input
                  type="checkbox"
                  checked={eatenIds.has(meal.id)}
                  onChange={() => toggleMeal(meal.id)}
                  className="mt-0.5 w-4 h-4 accent-emerald-500 shrink-0"
                />
                <div className="flex-1 min-w-0">
                  <div className="text-sm font-medium text-slate-200">
                    Meal {meal.meal_number} — {meal.recipe_name}
                  </div>
                  {meal.prep_id && (
                    <div className="text-xs text-violet-400 mt-0.5">Batch cook (using 1 serving)</div>
                  )}
                  <div className="text-xs text-slate-500 mt-0.5">
                    {meal.calories_est ? `${Math.round(meal.calories_est)} kcal` : ''}
                    {meal.protein_g_est ? ` · ${Math.round(meal.protein_g_est)}g P` : ''}
                  </div>
                </div>
              </label>
            ))}
          </div>

          <div className="flex gap-2 pt-2">
            <Button
              variant="primary"
              onClick={handleEndDay}
              loading={endDay.isPending}
              className="flex-1"
            >
              Confirm Day
            </Button>
            <Button
              variant="ghost"
              onClick={handleSkip}
              loading={skipDay.isPending}
            >
              Skip for now
            </Button>
          </div>

          {days.length > 1 && (
            <div className="flex gap-1 justify-center pt-1">
              {days.map((_, i) => (
                <div
                  key={i}
                  className={`w-1.5 h-1.5 rounded-full ${i === idx ? 'bg-emerald-500' : 'bg-slate-700'}`}
                />
              ))}
            </div>
          )}
        </div>
      </Modal>

      {ambiguousItems && (
        <AmbiguousQtyPrompt
          items={ambiguousItems}
          onClose={() => { setAmbiguousItems(null); advance() }}
        />
      )}
    </>
  )
}
