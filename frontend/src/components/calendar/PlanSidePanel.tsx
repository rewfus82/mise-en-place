import { useState, useEffect, useRef } from 'react'
import { usePlanning } from '../../context/PlanningContext'
import { useStalled } from '../../hooks/useStalled'
import { mealLabel } from '../../lib/mealLabels'
import type { SSEReviewEvent } from '../../types'
import { Button } from '../ui/Button'

interface PlanSidePanelProps {
  selectedDates: string[]
  onClose: () => void
  profile?: { meals_per_day?: number; calorie_target?: number | null }
}

export function PlanSidePanel({ selectedDates, onClose, profile }: PlanSidePanelProps) {
  const { job, startRangePlan, approve, revise, cancel } = usePlanning()

  // Config is panel-local: it only matters before a job exists.
  const [bulkEnabled, setBulkEnabled] = useState(false)
  const [bulkPct, setBulkPct] = useState(50)
  const [bulkRepeatAll, setBulkRepeatAll] = useState(false)
  const [specialRequests, setSpecialRequests] = useState('')
  const [feedback, setFeedback] = useState('')
  const logEndRef = useRef<HTMLDivElement>(null)

  const step = job.status === 'idle' ? 'config' : job.status
  const reviewData: SSEReviewEvent | null = job.review
  const error = job.error
  const stalled = useStalled(job.lastEventAt, step === 'streaming')

  // Auto-scroll the activity log whenever a new message arrives
  useEffect(() => {
    logEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [job.progress])

  const sortedSelected = [...selectedDates].sort()
  const startDate = step === 'config' ? sortedSelected[0] : job.dates[0]
  const numDays = step === 'config' ? sortedSelected.length : job.dates.length

  const handleGenerate = () =>
    startRangePlan(sortedSelected, { bulkEnabled, bulkPct, bulkRepeatAll, specialRequests })

  const handleApprove = () => approve()

  const handleRevise = () => {
    if (!feedback.trim()) return
    const fb = feedback
    setFeedback('')
    revise(fb)
  }

  // Derived review stats
  const reviewStats = reviewData ? {
    totalMeals: reviewData.days.reduce((s, d) => s + d.meals.length, 0),
    avgCal: reviewData.nutrition_summaries?.length
      ? Math.round(reviewData.nutrition_summaries.reduce((s, n) => s + n.total_calories, 0) / reviewData.nutrition_summaries.length)
      : null,
    avgPro: reviewData.nutrition_summaries?.length
      ? Math.round(reviewData.nutrition_summaries.reduce((s, n) => s + n.total_protein_g, 0) / reviewData.nutrition_summaries.length)
      : null,
    offTarget: reviewData.nutrition_summaries?.filter(n => !n.on_target).length ?? 0,
  } : null

  return (
    <div className="h-full flex flex-col bg-slate-900 border-l border-slate-800">
      {/* Header */}
      <div className="flex items-center justify-between px-5 py-4 border-b border-slate-800">
        <div>
          <h2 className="text-lg font-semibold text-slate-100">
            Plan {numDays} Day{numDays > 1 ? 's' : ''}
          </h2>
          <p className="text-xs text-slate-500">
            {startDate}{numDays > 1 ? ` + ${numDays - 1} more` : ''}
          </p>
        </div>
        <button
          onClick={onClose}
          title={step === 'streaming' || step === 'committing' ? 'Minimize — keeps running' : 'Close'}
          className="w-8 h-8 flex items-center justify-center rounded-lg text-slate-500 hover:text-slate-200 hover:bg-slate-800 transition-colors cursor-pointer"
        >
          <svg className="w-4 h-4" fill="none" viewBox="0 0 16 16">
            <path d="M4 4l8 8M12 4l-8 8" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
          </svg>
        </button>
      </div>

      <div className="flex-1 overflow-y-auto px-5 py-4">

        {/* Config step */}
        {step === 'config' && (
          <div className="space-y-5">
            <p className="text-sm text-slate-400">
              {numDays} day{numDays > 1 ? 's' : ''} · {profile?.meals_per_day ?? 3} meals/day
              {profile?.calorie_target ? ` · ${profile.calorie_target.toLocaleString()} kcal target` : ''}
            </p>

            {error && (
              <div className="text-xs text-rose-400 bg-rose-500/10 border border-rose-500/20 rounded-lg px-3 py-2">
                {error}
              </div>
            )}

            <div className="space-y-3">
              <label className="flex items-center gap-3 cursor-pointer">
                <input
                  type="checkbox"
                  checked={bulkEnabled}
                  onChange={e => setBulkEnabled(e.target.checked)}
                  className="w-4 h-4 accent-emerald-500"
                />
                <span className="text-sm font-medium text-slate-200">Enable bulk meal prep</span>
              </label>

              {bulkEnabled && (
                <div className="ml-7 space-y-3 p-3 bg-slate-800 rounded-lg">
                  <div>
                    <label className="text-xs text-slate-400 block mb-1">
                      % of meals to batch cook: <span className="text-emerald-400 font-semibold">{bulkPct}%</span>
                    </label>
                    <input
                      type="range" min={10} max={100} step={10}
                      value={bulkPct}
                      onChange={e => setBulkPct(Number(e.target.value))}
                      className="w-full accent-emerald-500"
                    />
                  </div>
                  <label className="flex items-center gap-2 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={bulkRepeatAll}
                      onChange={e => setBulkRepeatAll(e.target.checked)}
                      className="w-4 h-4 accent-emerald-500"
                    />
                    <span className="text-xs text-slate-300">Repeat bulk meals every day</span>
                  </label>
                </div>
              )}
            </div>

            <div>
              <label className="text-xs text-slate-400 block mb-1">Special requests (optional)</label>
              <textarea
                value={specialRequests}
                onChange={e => setSpecialRequests(e.target.value)}
                placeholder="e.g. high carb days, avoid red meat this week..."
                rows={3}
                className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm text-slate-100 placeholder-slate-500 resize-none focus:outline-none focus:border-emerald-500"
              />
            </div>

            <Button variant="primary" size="lg" onClick={handleGenerate} className="w-full">
              Generate Plan
            </Button>
          </div>
        )}

        {/* Streaming step */}
        {step === 'streaming' && (
          <div className="space-y-3">
            {/* Status header */}
            <div className="flex items-center gap-2.5 text-emerald-400">
              <span className="w-4 h-4 border-2 border-emerald-400 border-t-transparent rounded-full animate-spin shrink-0" />
              <span className="text-sm font-medium">Generating your plan…</span>
            </div>

            {/* Activity log window */}
            <div className="bg-slate-950 border border-slate-800 rounded-xl overflow-hidden">
              <div className="flex items-center gap-1.5 px-3 py-2 border-b border-slate-800/60">
                <span className="w-2 h-2 rounded-full bg-rose-500/60" />
                <span className="w-2 h-2 rounded-full bg-amber-500/60" />
                <span className="w-2 h-2 rounded-full bg-emerald-500/60" />
                <span className="text-[10px] text-slate-600 ml-1 font-mono">activity</span>
              </div>
              <div className="h-48 overflow-y-auto px-3 py-2.5 space-y-1.5 font-mono text-xs">
                {job.progress.length === 0 ? (
                  <div className="flex items-center gap-2 text-slate-600">
                    <span className="animate-pulse">▋</span>
                    <span>Starting up…</span>
                  </div>
                ) : (
                  job.progress.map((msg, i) => {
                    const isLatest = i === job.progress.length - 1
                    return (
                      <div key={i} className={`flex gap-2 ${isLatest ? 'text-slate-300' : 'text-slate-600'}`}>
                        <span className="text-slate-700 shrink-0 select-none">›</span>
                        <span className="break-words">{msg}</span>
                      </div>
                    )
                  })
                )}
                {/* Blinking cursor on latest line */}
                {job.progress.length > 0 && (
                  <div className="flex gap-2 text-slate-600">
                    <span className="text-slate-700 select-none">›</span>
                    <span className="animate-pulse">▋</span>
                  </div>
                )}
                <div ref={logEndRef} />
              </div>
            </div>

            {stalled && (
              <div className="flex items-center gap-2 text-xs text-amber-400/90 bg-amber-500/10 border border-amber-500/20 rounded-lg px-3 py-2">
                <span className="w-3 h-3 border-2 border-amber-400 border-t-transparent rounded-full animate-spin shrink-0" />
                Still working — your AI provider may be rate-limiting; retrying…
              </div>
            )}

            <p className="text-xs text-slate-600 text-center">
              This may take 15–30 seconds for multi-day plans — you can switch pages, it keeps running.
            </p>

            <button
              onClick={cancel}
              className="w-full text-xs text-slate-500 hover:text-rose-400 py-1.5 transition-colors cursor-pointer"
            >
              Cancel
            </button>
          </div>
        )}

        {/* Review step */}
        {step === 'review' && reviewData && reviewStats && (
          <div className="space-y-4">
            {/* "Ready" banner */}
            <div className="flex items-start gap-3 bg-emerald-500/10 border border-emerald-500/25 rounded-xl px-4 py-3">
              <div className="w-5 h-5 rounded-full bg-emerald-500 flex items-center justify-center shrink-0 mt-0.5">
                <svg className="w-3 h-3 text-slate-950" fill="none" viewBox="0 0 12 12">
                  <path d="M2.5 6l2.5 2.5L9.5 3.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
                </svg>
              </div>
              <div>
                <div className="text-sm font-semibold text-emerald-400">Plan ready — review before saving</div>
                <div className="text-xs text-slate-400 mt-0.5">
                  {numDays} days · {reviewStats.totalMeals} meals
                  {reviewStats.avgCal && ` · avg ${reviewStats.avgCal.toLocaleString()} kcal/day`}
                  {reviewStats.avgPro && ` · ${reviewStats.avgPro}g P`}
                  {reviewStats.offTarget > 0 && (
                    <span className="text-amber-400 ml-1">· {reviewStats.offTarget} day{reviewStats.offTarget > 1 ? 's' : ''} off target</span>
                  )}
                </div>
              </div>
            </div>

            {/* Evidence grounding — shows the plan is backed by sourced literature */}
            {((reviewData.applied_guidelines && reviewData.applied_guidelines.length > 0) ||
              reviewData.guideline_summary) && (
              <div className="bg-slate-800/40 border border-slate-700/60 rounded-lg px-3 py-2.5">
                <div className="flex items-center gap-1.5 text-[11px] text-slate-500 uppercase tracking-wider font-medium mb-1.5">
                  <svg className="w-3.5 h-3.5 text-emerald-400" fill="none" viewBox="0 0 16 16">
                    <path d="M3 2h7l3 3v9H3V2z" stroke="currentColor" strokeWidth="1.3" strokeLinejoin="round" />
                    <path d="M5.5 7h5M5.5 9.5h3" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" />
                  </svg>
                  Grounded in
                </div>
                {reviewData.guideline_summary && (
                  <p className="text-xs text-slate-300 leading-relaxed mb-2">
                    {reviewData.guideline_summary}
                  </p>
                )}
                <ul className="space-y-1">
                  {reviewData.applied_guidelines?.map((g, i) => (
                    <li key={i} className="text-xs text-slate-400">
                      {g.url ? (
                        <a
                          href={g.url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-slate-300 hover:text-emerald-400 hover:underline"
                        >
                          {g.citation}
                        </a>
                      ) : (
                        <span className="text-slate-300">{g.citation}</span>
                      )}
                      {g.title && <span className="text-slate-600"> — {g.title}</span>}
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {error && (
              <div className="text-xs text-rose-400 bg-rose-500/10 border border-rose-500/20 rounded-lg px-3 py-2">
                {error}
              </div>
            )}

            {/* Day cards */}
            {reviewData.days.map((day, di) => {
              const nutrition = reviewData.nutrition_summaries?.[di]
              const dateLabel = new Date(day.date + 'T12:00:00').toLocaleDateString('en-US', {
                weekday: 'short', month: 'short', day: 'numeric',
              })
              return (
                <div key={day.date} className="border border-slate-700/60 rounded-xl overflow-hidden">
                  <div className="px-3 py-2.5 bg-slate-800/60 flex items-center justify-between">
                    <span className="text-sm font-semibold text-slate-200">{dateLabel}</span>
                    {nutrition && (
                      <div className="flex items-center gap-2 text-xs">
                        <span className="text-slate-400">
                          {Math.round(nutrition.total_calories).toLocaleString()} kcal
                        </span>
                        <span className="text-emerald-500 font-medium">
                          {Math.round(nutrition.total_protein_g)}g P
                        </span>
                        {!nutrition.on_target && (
                          <span className="text-amber-400">⚠</span>
                        )}
                      </div>
                    )}
                  </div>
                  <div className="divide-y divide-slate-800/60">
                    {day.meals.map(m => (
                      <div key={m.meal_number} className="px-3 py-2.5">
                        <div className="flex items-center gap-2">
                          <span className="text-[10px] font-semibold text-slate-600 uppercase tracking-wider shrink-0">
                            {mealLabel(m.meal_number, day.meals.length)}
                          </span>
                          <span className="text-sm text-slate-200 truncate">{m.recipe_name}</span>
                          {m.is_bulk_prep && (
                            <span className="text-[10px] text-violet-400 bg-violet-400/10 px-1.5 py-0.5 rounded-full shrink-0">
                              ×{m.bulk_servings}
                            </span>
                          )}
                        </div>
                        {m.brief_description && (
                          <p className="text-xs text-slate-500 mt-0.5 ml-6 line-clamp-1">{m.brief_description}</p>
                        )}
                        <div className="text-xs text-slate-500 mt-0.5 ml-6">
                          {Math.round(m.calories_est).toLocaleString()} kcal · {Math.round(m.protein_g_est)}g P
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )
            })}

            {/* Actions */}
            <div className="space-y-2 pt-1 pb-2">
              <Button variant="primary" size="lg" onClick={handleApprove} className="w-full">
                Save to Calendar
              </Button>
              <div className="flex gap-2">
                <input
                  type="text"
                  value={feedback}
                  onChange={e => setFeedback(e.target.value)}
                  placeholder="Ask for changes…"
                  className="flex-1 bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm text-slate-100 placeholder-slate-500 focus:outline-none focus:border-emerald-500"
                  onKeyDown={e => e.key === 'Enter' && handleRevise()}
                />
                <Button variant="secondary" onClick={handleRevise} disabled={!feedback.trim()}>
                  Revise
                </Button>
              </div>
            </div>
          </div>
        )}

        {/* Committing step */}
        {step === 'committing' && (
          <div className="flex flex-col items-center justify-center h-48 gap-3">
            <span className="w-6 h-6 border-2 border-emerald-400 border-t-transparent rounded-full animate-spin" />
            <span className="text-sm text-slate-400">Saving to calendar…</span>
          </div>
        )}

        {/* Error step (outside review) */}
        {step === 'error' && (
          <div className="flex flex-col items-center justify-center h-64 gap-4">
            <div className="w-12 h-12 rounded-full bg-rose-500/15 border border-rose-500/40 flex items-center justify-center">
              <svg className="w-6 h-6 text-rose-400" fill="none" viewBox="0 0 24 24">
                <path d="M12 8v5M12 16h.01" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
                <circle cx="12" cy="12" r="9" stroke="currentColor" strokeWidth="1.6" />
              </svg>
            </div>
            <div className="text-center">
              <p className="text-base font-semibold text-slate-100">Planning failed</p>
              <p className="text-xs text-slate-500 mt-1 max-w-xs">{error}</p>
            </div>
            <Button variant="secondary" onClick={onClose}>Close</Button>
          </div>
        )}

        {/* Done step */}
        {step === 'done' && (
          <div className="flex flex-col items-center justify-center h-64 gap-4">
            <div className="w-12 h-12 rounded-full bg-emerald-500/20 border border-emerald-500/40 flex items-center justify-center">
              <svg className="w-6 h-6 text-emerald-400" fill="none" viewBox="0 0 24 24">
                <path d="M5 13l4 4L19 7" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            </div>
            <div className="text-center">
              <p className="text-lg font-semibold text-slate-100">Plan saved</p>
              <p className="text-sm text-slate-500 mt-1">{numDays} day{numDays > 1 ? 's' : ''} added to your calendar</p>
            </div>
            <Button variant="primary" onClick={onClose}>View Calendar</Button>
          </div>
        )}
      </div>
    </div>
  )
}
