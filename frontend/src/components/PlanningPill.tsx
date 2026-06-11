/**
 * Global, persistent planning indicator — the "minimized" form of the plan panel.
 * Shows on every page while a plan job is active, except when the full panel is
 * already visible (on the calendar, panel open). Clicking jumps to the calendar
 * and re-expands the panel; a ✕ cancels an in-flight run.
 */
import { useEffect } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { usePlanning } from '../context/PlanningContext'
import { useStalled } from '../hooks/useStalled'

export function PlanningPill() {
  const { job, panelOpen, openPanel, reset, cancel } = usePlanning()
  const navigate = useNavigate()
  const location = useLocation()
  const stalled = useStalled(job.lastEventAt, job.status === 'streaming')

  const onCalendar = location.pathname.startsWith('/calendar')
  const panelVisible = onCalendar && panelOpen

  // Auto-clear the "done" state after a moment so the pill doesn't linger.
  useEffect(() => {
    if (job.status === 'done' && !panelVisible) {
      const t = setTimeout(reset, 4000)
      return () => clearTimeout(t)
    }
  }, [job.status, panelVisible, reset])

  if (job.status === 'idle' || panelVisible) return null

  const days = job.dates.length
  const isDay = job.kind === 'day'
  const cancelable = job.status === 'streaming' || job.status === 'committing'

  const open = () => {
    if (isDay) {
      // Day regen has no review panel — clicking just jumps to the calendar.
      if (!onCalendar) navigate('/calendar')
      return
    }
    openPanel()
    if (!onCalendar) navigate('/calendar')
  }

  const spinner = <span className="w-3.5 h-3.5 border-2 border-emerald-400 border-t-transparent rounded-full animate-spin" />
  const check = (
    <svg className="w-3.5 h-3.5 text-emerald-400" fill="none" viewBox="0 0 16 16">
      <path d="M3 8l3.5 3.5L13 5" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  )

  let dot: React.ReactNode = spinner
  let label: string
  let cls = 'border-slate-700 text-slate-200'

  switch (job.status) {
    case 'streaming':
      label = isDay ? 'Regenerating…' : `Planning ${days} day${days !== 1 ? 's' : ''}…`
      if (stalled) label += ' · retrying…'
      break
    case 'committing':
      label = 'Saving plan…'
      break
    case 'review':
      dot = <span className="w-2 h-2 rounded-full bg-emerald-400" />
      label = 'Plan ready · Review →'
      cls = 'border-emerald-500/40 text-emerald-300 ring-1 ring-emerald-500/20 animate-pulse'
      break
    case 'done':
      dot = check
      label = isDay ? 'Day updated' : 'Plan saved'
      cls = 'border-emerald-500/40 text-emerald-300'
      break
    case 'error':
      dot = <span className="w-2 h-2 rounded-full bg-rose-500" />
      label = isDay ? 'Regeneration failed · View' : 'Planning failed · View'
      cls = 'border-rose-500/40 text-rose-300'
      break
    default:
      return null
  }

  return (
    <div className={`fixed bottom-5 right-5 z-50 flex items-center rounded-full bg-slate-900 border shadow-xl shadow-black/40 ${cls}`}>
      <button
        onClick={open}
        className="flex items-center gap-2.5 pl-3 pr-4 py-2.5 text-sm font-medium cursor-pointer rounded-full hover:bg-white/5 transition-colors"
      >
        {dot}
        {label}
      </button>
      {cancelable && (
        <button
          onClick={cancel}
          title="Cancel"
          className="pr-3 pl-1 py-2.5 text-slate-500 hover:text-rose-400 cursor-pointer transition-colors"
        >
          <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 16 16">
            <path d="M4 4l8 8M12 4l-8 8" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
          </svg>
        </button>
      )}
    </div>
  )
}
