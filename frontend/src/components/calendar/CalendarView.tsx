import { useState, useCallback } from 'react'
import type { MealDay, UserProfile } from '../../types'
import { DayCell } from './DayCell'
import { DayPanel } from './DayPanel'
import { PlanSidePanel } from './PlanSidePanel'
import { SelectionToolbar } from './SelectionToolbar'

const DOW = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat']

interface CalendarViewProps {
  year: number
  month: number
  days: MealDay[]
  profile?: UserProfile
  weightByDate?: Map<string, number>
  onMonthChange: (year: number, month: number) => void
}

interface GridCell {
  date: string
  isCurrentMonth: boolean
}

function buildDateGrid(year: number, month: number, weeks: number): GridCell[][] {
  const first = new Date(year, month - 1, 1)
  const offset = first.getDay()
  const grid: GridCell[][] = []
  const current = new Date(first)
  current.setDate(current.getDate() - offset)

  for (let w = 0; w < weeks; w++) {
    const week: GridCell[] = []
    for (let d = 0; d < 7; d++) {
      week.push({
        date: current.toISOString().split('T')[0],
        isCurrentMonth: current.getMonth() === month - 1,
      })
      current.setDate(current.getDate() + 1)
    }
    grid.push(week)
  }
  return grid
}

export function CalendarView({ year, month, days, profile, weightByDate, onMonthChange }: CalendarViewProps) {
  const [weeksToShow, setWeeksToShow] = useState(4)
  const [selectedDates, setSelectedDates] = useState<Set<string>>(new Set())
  const [isDragging, setIsDragging] = useState(false)
  const [dragStart, setDragStart] = useState<string | null>(null)
  const [openDay, setOpenDay] = useState<string | null>(null)
  const [showPlanPanel, setShowPlanPanel] = useState(false)

  const dayMap = new Map(days.map(d => [d.date, d]))
  const today = new Date().toISOString().split('T')[0]
  const grid = buildDateGrid(year, month, weeksToShow)
  const allCells = grid.flat()

  const monthName = new Date(year, month - 1, 1).toLocaleString('default', { month: 'long' })
  const isCurrentMonth = year === new Date().getFullYear() && month === new Date().getMonth() + 1

  const prevMonth = () => month === 1 ? onMonthChange(year - 1, 12) : onMonthChange(year, month - 1)
  const nextMonth = () => month === 12 ? onMonthChange(year + 1, 1) : onMonthChange(year, month + 1)
  const goToToday = () => {
    const now = new Date()
    onMonthChange(now.getFullYear(), now.getMonth() + 1)
  }

  const hasPlan = (date: string) => (dayMap.get(date)?.meals.length ?? 0) > 0
  // Past dates (or today) are "viewable" — can open history panel
  const isViewable = (date: string) => date <= today

  const handlePointerDown = useCallback((date: string) => {
    setIsDragging(true)
    setDragStart(date)
    setSelectedDates(prev => {
      const next = new Set(prev)
      next.has(date) ? next.delete(date) : next.add(date)
      return next
    })
  }, [])

  const handlePointerEnter = useCallback((date: string) => {
    if (!isDragging || !dragStart) return
    const selectableCells = allCells.filter(c => c.date >= today && c.isCurrentMonth && !hasPlan(c.date))
    const startIdx = selectableCells.findIndex(c => c.date === dragStart)
    const endIdx = selectableCells.findIndex(c => c.date === date)
    if (startIdx === -1 || endIdx === -1) return
    const [lo, hi] = startIdx <= endIdx ? [startIdx, endIdx] : [endIdx, startIdx]
    setSelectedDates(new Set(selectableCells.slice(lo, hi + 1).map(c => c.date)))
  }, [isDragging, dragStart, allCells, today])

  const handlePointerUp = useCallback(() => {
    setIsDragging(false)
    setDragStart(null)
  }, [])

  const handleCellClick = useCallback((date: string) => {
    if (selectedDates.size > 0) return  // toolbar handles it
    const hasMeals = dayMap.has(date)
    // Open panel for any past/today date (for history + weight log) or any planned date
    if (hasMeals || isViewable(date)) {
      setOpenDay(date)
      setShowPlanPanel(false)
    }
  }, [selectedDates.size, dayMap, today])

  const openDayData = openDay ? dayMap.get(openDay) : undefined
  const hasSidePanel = openDay !== null || showPlanPanel

  return (
    <div
      className="flex h-full bg-slate-950"
      onPointerUp={handlePointerUp}
      onPointerLeave={handlePointerUp}
    >
      {/* Main calendar */}
      <div className={`flex-1 flex flex-col min-w-0 transition-all duration-300 ${hasSidePanel ? 'mr-[400px]' : ''}`}>

        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-800/60">
          <div className="flex items-center gap-2">
            <button
              onClick={prevMonth}
              className="w-8 h-8 flex items-center justify-center rounded-lg text-slate-400 hover:text-slate-100 hover:bg-slate-800 transition-colors cursor-pointer"
            >
              <svg className="w-4 h-4" fill="none" viewBox="0 0 16 16">
                <path d="M10 3L5 8l5 5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            </button>
            <h1 className="text-xl font-semibold text-slate-100 w-44 text-center">
              {monthName} {year}
            </h1>
            <button
              onClick={nextMonth}
              className="w-8 h-8 flex items-center justify-center rounded-lg text-slate-400 hover:text-slate-100 hover:bg-slate-800 transition-colors cursor-pointer"
            >
              <svg className="w-4 h-4" fill="none" viewBox="0 0 16 16">
                <path d="M6 3l5 5-5 5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            </button>
            {!isCurrentMonth && (
              <button
                onClick={goToToday}
                className="ml-1 px-3 py-1 text-xs text-slate-400 hover:text-slate-200 border border-slate-700 hover:border-slate-500 rounded-lg transition-colors cursor-pointer"
              >
                Today
              </button>
            )}
          </div>

          {/* Week selector */}
          <div className="flex items-center gap-3">
            <span className="text-xs text-slate-500">View</span>
            <div className="flex items-center bg-slate-900 border border-slate-800 rounded-lg p-0.5">
              {[1, 2, 3, 4].map(w => (
                <button
                  key={w}
                  onClick={() => setWeeksToShow(w)}
                  className={`
                    w-9 py-1.5 text-xs font-medium rounded transition-colors cursor-pointer
                    ${weeksToShow === w
                      ? 'bg-slate-700 text-slate-100'
                      : 'text-slate-500 hover:text-slate-300'}
                  `}
                >
                  {w}W
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* Day-of-week labels */}
        <div className="grid grid-cols-7 px-6 pt-4 pb-2">
          {DOW.map(d => (
            <div key={d} className="text-[11px] font-semibold text-slate-600 uppercase tracking-wider text-center">
              {d}
            </div>
          ))}
        </div>

        {/* Grid */}
        <div className="flex-1 px-6 pb-6 overflow-y-auto">
          <div className="space-y-2">
            {grid.map((week, wi) => (
              <div key={wi} className="grid grid-cols-7 gap-2">
                {week.map(({ date, isCurrentMonth: inMonth }) => (
                  <DayCell
                    key={date}
                    date={date}
                    today={today}
                    day={dayMap.get(date)}
                    isCurrentMonth={inMonth}
                    selected={selectedDates.has(date)}
                    weightKg={weightByDate?.get(date)}
                    onPointerDown={handlePointerDown}
                    onPointerEnter={handlePointerEnter}
                    onClick={handleCellClick}
                  />
                ))}
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Day panel — history or future */}
      {openDay !== null && !showPlanPanel && (
        <div className="fixed right-0 top-0 h-full w-[400px] z-30 border-l border-slate-800 bg-slate-900 shadow-2xl">
          <DayPanel
            date={openDay}
            day={openDayData}
            profile={profile}
            onClose={() => setOpenDay(null)}
          />
        </div>
      )}

      {/* Plan panel */}
      {showPlanPanel && (
        <div className="fixed right-0 top-0 h-full w-[420px] z-30 border-l border-slate-800 bg-slate-900 shadow-2xl">
          <PlanSidePanel
            selectedDates={Array.from(selectedDates).sort()}
            profile={profile}
            onClose={() => { setShowPlanPanel(false); setSelectedDates(new Set()) }}
          />
        </div>
      )}

      {/* Selection toolbar */}
      <SelectionToolbar
        selectedCount={selectedDates.size}
        onPlan={() => { setOpenDay(null); setShowPlanPanel(true) }}
        onClear={() => setSelectedDates(new Set())}
      />
    </div>
  )
}
