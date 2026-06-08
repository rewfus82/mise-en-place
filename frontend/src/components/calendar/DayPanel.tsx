import { useState, useEffect, useRef } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import type { MealDay, UserProfile } from '../../types'
import { useCalendarMutations } from '../../hooks/useCalendar'
import { calendarApi } from '../../api/calendar'
import { weightLogApi } from '../../api/weightLog'
import { kgToLbs, lbsToKg } from '../../lib/units'
import { AmbiguousQtyPrompt } from '../confirmation/AmbiguousQtyPrompt'
import { Button } from '../ui/Button'
import { MacroBar } from './MacroBar'
import { MealRow } from './MealRow'

interface DayPanelProps {
  date: string
  day?: MealDay
  profile?: UserProfile
  onClose: () => void
}

const STATUS_CONFIG = {
  completed: { label: 'Completed', dot: 'bg-emerald-500', text: 'text-emerald-400' },
  planned:   { label: 'Planned',   dot: 'bg-blue-500',    text: 'text-blue-400'    },
  skipped:   { label: 'Skipped',   dot: 'bg-slate-500',   text: 'text-slate-400'   },
}


export function DayPanel({ date, day, profile, onClose }: DayPanelProps) {
  const qc = useQueryClient()
  const { toggleEaten, toggleSkipped, endDay, deleteDay } = useCalendarMutations()
  const [ambiguousItems, setAmbiguousItems] = useState<Array<{ item: string; quantity: string | null; unit: string | null }>>([])

  const today = new Date().toISOString().split('T')[0]
  const isPast = date < today
  const isToday = date === today
  const showWeightLog = isPast || isToday

  // Weight log state
  const { data: weightEntries = [] } = useQuery({
    queryKey: ['weight-log'],
    queryFn: weightLogApi.list,
  })
  const currentEntry = weightEntries.find(e => e.date === date)

  const [weightInput, setWeightInput] = useState('')
  const [weightStatus, setWeightStatus] = useState<'idle' | 'saving' | 'saved'>('idle')
  const weightTimerRef = useRef<ReturnType<typeof setTimeout>>(undefined)

  useEffect(() => {
    if (currentEntry) {
      setWeightInput(kgToLbs(currentEntry.weight_kg).toFixed(1))
    } else {
      setWeightInput('')
    }
  }, [currentEntry?.weight_kg, date])

  const weightMutation = useMutation({
    mutationFn: ({ kg }: { kg: number }) => weightLogApi.upsert(date, kg),
    onMutate: () => setWeightStatus('saving'),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['weight-log'] })
      setWeightStatus('saved')
      setTimeout(() => setWeightStatus('idle'), 1500)
    },
  })

  const removeWeight = useMutation({
    mutationFn: () => weightLogApi.remove(date),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['weight-log'] })
      setWeightInput('')
    },
  })

  const handleWeightChange = (val: string) => {
    setWeightInput(val)
    clearTimeout(weightTimerRef.current)
    if (!val || isNaN(Number(val))) return
    weightTimerRef.current = setTimeout(() => {
      weightMutation.mutate({ kg: lbsToKg(Number(val)) })
    }, 700)
  }

  // Day data
  const meals = day?.meals ?? []
  const totalCal  = meals.reduce((s, m) => s + (m.calories_est ?? 0), 0)
  const totalPro  = meals.reduce((s, m) => s + (m.protein_g_est ?? 0), 0)
  const totalCarb = meals.reduce((s, m) => s + (m.carbs_g_est ?? 0), 0)
  const totalFat  = meals.reduce((s, m) => s + (m.fat_g_est ?? 0), 0)

  const allAddressed = meals.length > 0 && meals.every(m => m.eaten || m.skipped)
  const status = day ? STATUS_CONFIG[day.status] : null

  const dateLabel = new Date(date + 'T12:00:00').toLocaleDateString('en-US', {
    weekday: 'long', month: 'long', day: 'numeric',
  })

  const handleEndDay = async () => {
    const result = await endDay.mutateAsync(date)
    if ((result.needs_confirmation as unknown[])?.length) {
      setAmbiguousItems(result.needs_confirmation as Array<{ item: string; quantity: string | null; unit: string | null }>)
    }
  }

  const handleDelete = async () => {
    if (!confirm(`Delete all meals for ${date}?`)) return
    await deleteDay.mutateAsync(date)
    onClose()
  }

  const regenerate = useMutation({
    mutationFn: () => calendarApi.regenerateDay(date),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['calendar'] })
      qc.invalidateQueries({ queryKey: ['grocery'] })
    },
  })

  return (
    <>
      <div className="h-full flex flex-col bg-slate-900">
        {/* Header */}
        <div className="px-5 py-5 border-b border-slate-800/60">
          <div className="flex items-start justify-between">
            <div>
              <h2 className="text-lg font-semibold text-slate-100">{dateLabel}</h2>
              <div className="flex items-center gap-2 mt-1.5">
                {status && (
                  <>
                    <span className={`w-1.5 h-1.5 rounded-full ${status.dot}`} />
                    <span className={`text-xs font-medium ${status.text}`}>{status.label}</span>
                    <span className="text-slate-700">·</span>
                  </>
                )}
                {isPast && !day && (
                  <>
                    <span className="w-1.5 h-1.5 rounded-full bg-slate-600" />
                    <span className="text-xs font-medium text-slate-500">No meals logged</span>
                    <span className="text-slate-700">·</span>
                  </>
                )}
                <span className="text-xs text-slate-500">{meals.length} meal{meals.length !== 1 ? 's' : ''}</span>
              </div>
            </div>
            <button
              onClick={onClose}
              className="w-8 h-8 flex items-center justify-center rounded-lg text-slate-500 hover:text-slate-200 hover:bg-slate-800 transition-colors cursor-pointer"
            >
              <svg className="w-4 h-4" fill="none" viewBox="0 0 16 16">
                <path d="M4 4l8 8M12 4l-8 8" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
              </svg>
            </button>
          </div>

          {/* Macro bar */}
          {totalCal > 0 && (
            <div className="mt-4">
              <MacroBar
                calories={totalCal}
                protein={totalPro}
                carbs={totalCarb}
                fat={totalFat}
                targetCalories={profile?.calorie_target ?? undefined}
                targetProtein={profile?.protein_target_g ?? undefined}
              />
            </div>
          )}
        </div>

        {/* Weight log section — past dates & today */}
        {showWeightLog && (
          <div className="px-5 py-3.5 border-b border-slate-800/40 flex items-center gap-3">
            <div className="flex items-center gap-1.5 text-slate-500">
              <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 14 14">
                <circle cx="7" cy="5.5" r="3.5" stroke="currentColor" strokeWidth="1.2" />
                <path d="M3 12.5c0-2.21 1.79-4 4-4s4 1.79 4 4" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" />
              </svg>
              <span className="text-xs font-medium text-slate-400">Weight</span>
            </div>
            <div className="flex items-center gap-2 flex-1">
              <input
                type="number"
                value={weightInput}
                onChange={e => handleWeightChange(e.target.value)}
                placeholder="—"
                className="w-20 bg-slate-800 border border-slate-700/80 rounded-lg px-3 py-1.5 text-sm text-slate-100 tabular-nums text-right focus:outline-none focus:border-emerald-500/60"
              />
              <span className="text-xs text-slate-500">lbs</span>
              {weightStatus === 'saving' && (
                <span className="w-3 h-3 border border-slate-500 border-t-transparent rounded-full animate-spin" />
              )}
              {weightStatus === 'saved' && (
                <svg className="w-3 h-3 text-emerald-500" fill="none" viewBox="0 0 12 12">
                  <path d="M2 6l2.5 2.5L10 3" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
                </svg>
              )}
              {currentEntry && weightStatus === 'idle' && (
                <button
                  onClick={() => removeWeight.mutate()}
                  className="text-[11px] text-slate-700 hover:text-rose-400 transition-colors cursor-pointer"
                >
                  remove
                </button>
              )}
            </div>
          </div>
        )}

        {/* Meals */}
        <div className="flex-1 overflow-y-auto py-3">
          {meals.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-full gap-2 text-slate-600">
              <svg className="w-8 h-8 opacity-30" fill="none" viewBox="0 0 32 32">
                <circle cx="16" cy="16" r="13" stroke="currentColor" strokeWidth="1.5" />
                <path d="M10 16h12M16 10v12" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
              </svg>
              <p className="text-sm">{isPast ? 'No meals were logged' : 'No meals planned'}</p>
            </div>
          ) : (
            <div className="space-y-1 px-3">
              {meals.map(meal => (
                <MealRow
                  key={meal.id}
                  meal={meal}
                  date={date}
                  readOnly={day?.status === 'completed' || day?.status === 'skipped'}
                  onToggleEaten={(eaten) => toggleEaten.mutate({ date, mealId: meal.id, eaten })}
                  onToggleSkipped={(skipped) => toggleSkipped.mutate({ date, mealId: meal.id, skipped })}
                />
              ))}
            </div>
          )}
        </div>

        {/* Footer — only show actions for planned/actionable days */}
        {day && day.status === 'planned' && (
          <div className="px-5 py-4 border-t border-slate-800/60 space-y-2">
            {!allAddressed && meals.length > 0 && (
              <p className="text-xs text-slate-500 text-center pb-1">
                Check off or skip all meals to end the day
              </p>
            )}
            <Button
              variant="primary"
              onClick={handleEndDay}
              disabled={!allAddressed}
              loading={endDay.isPending}
              className="w-full"
            >
              End Day
            </Button>
            {!isPast && (
              <Button
                variant="secondary"
                size="sm"
                onClick={() => regenerate.mutate()}
                loading={regenerate.isPending}
                className="w-full"
              >
                {regenerate.isPending ? 'Regenerating…' : 'Regenerate this day'}
              </Button>
            )}
            {regenerate.isError && (
              <p className="text-xs text-rose-400 text-center">Regeneration failed — try again.</p>
            )}
            <Button
              variant="ghost"
              size="sm"
              onClick={handleDelete}
              loading={deleteDay.isPending}
              className="w-full text-rose-500 hover:text-rose-400 hover:bg-rose-500/10"
            >
              Delete plan for this day
            </Button>
          </div>
        )}
        {day && (day.status === 'completed' || day.status === 'skipped') && (
          <div className="px-5 py-3 border-t border-slate-800/60">
            <Button
              variant="ghost"
              size="sm"
              onClick={handleDelete}
              loading={deleteDay.isPending}
              className="w-full text-rose-500/60 hover:text-rose-400 hover:bg-rose-500/10"
            >
              Remove from history
            </Button>
          </div>
        )}
      </div>

      <AmbiguousQtyPrompt
        items={ambiguousItems}
        onClose={() => setAmbiguousItems([])}
      />
    </>
  )
}
