/**
 * App-level planning state. The SSE generation loops live here (not in a route
 * component), so a plan keeps running and its progress/review survive when the
 * user navigates to another page. The PlanSidePanel and the floating pill are both
 * just views of this state.
 */
import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { streamSSE } from '../api/client'
import { calendarApi } from '../api/calendar'
import { track } from '../lib/analytics'
import { useToast } from '../components/ui/Toast'
import type { SSEEvent, SSEReviewEvent } from '../types'

export type PlanStatus = 'idle' | 'streaming' | 'review' | 'committing' | 'done' | 'error'
export type PlanKind = 'range' | 'day'

export interface PlanJob {
  kind: PlanKind
  status: PlanStatus
  dates: string[]
  threadId: string | null
  progress: string[]
  review: SSEReviewEvent | null
  error: string | null
  lastEventAt: number   // ms timestamp of the last event — drives the stall hint
}

const ACTIVE_STATUSES: PlanStatus[] = ['streaming', 'review', 'committing']

export interface RangePlanOptions {
  bulkEnabled: boolean
  bulkPct: number
  bulkRepeatAll: boolean
  specialRequests: string
}

interface PlanningContextValue {
  job: PlanJob
  panelOpen: boolean
  openPanel: () => void
  closePanel: () => void
  reset: () => void
  cancel: () => void
  startRangePlan: (dates: string[], opts: RangePlanOptions) => Promise<void>
  startDayRegen: (date: string) => Promise<void>
  approve: () => Promise<void>
  revise: (feedback: string) => Promise<void>
}

const IDLE_JOB: PlanJob = {
  kind: 'range',
  status: 'idle',
  dates: [],
  threadId: null,
  progress: [],
  review: null,
  error: null,
  lastEventAt: 0,
}

const PlanningContext = createContext<PlanningContextValue | null>(null)

// eslint-disable-next-line react-refresh/only-export-components
export function usePlanning(): PlanningContextValue {
  const ctx = useContext(PlanningContext)
  if (!ctx) throw new Error('usePlanning must be used within a PlanningProvider')
  return ctx
}

export function PlanningProvider({ children }: { children: React.ReactNode }) {
  const qc = useQueryClient()
  const { toast } = useToast()
  const [job, setJob] = useState<PlanJob>(IDLE_JOB)
  const [panelOpen, setPanelOpen] = useState(false)

  // The async loops capture state at call time; a ref gives them the live job
  // (e.g. the thread id needed by approve/revise) without stale closures.
  const jobRef = useRef(job)
  useEffect(() => {
    jobRef.current = job
  }, [job])

  // Aborts the in-flight fetch/stream for the current job.
  const abortRef = useRef<AbortController | null>(null)

  const openPanel = useCallback(() => setPanelOpen(true), [])
  const closePanel = useCallback(() => setPanelOpen(false), [])
  const reset = useCallback(() => {
    setJob(IDLE_JOB)
    setPanelOpen(false)
  }, [])

  const cancel = useCallback(() => {
    abortRef.current?.abort()
    abortRef.current = null
    setJob(IDLE_JOB)
    setPanelOpen(false)
    toast('Cancelled', 'info')
  }, [toast])

  const invalidateCalendar = useCallback(() => {
    qc.invalidateQueries({ queryKey: ['calendar'] })
    qc.invalidateQueries({ queryKey: ['grocery'] })
  }, [qc])

  // Shared SSE consumer for the three plan flows (generate / approve / revise).
  // The caller sets the initial job state; this drives the stream events through to
  // review/done/error and is abort-aware (a user cancel resets without an error).
  const consumePlanStream = useCallback(
    async (path: string, body: unknown, opts: { failToast: string; completeToast?: string }) => {
      const controller = new AbortController()
      abortRef.current = controller
      try {
        for await (const event of streamSSE(path, body, controller.signal)) {
          const e = event as unknown as SSEEvent
          if (e.type === 'progress' && e.message) {
            setJob(j => ({ ...j, progress: [...j.progress, e.message], lastEventAt: Date.now() }))
          } else if (e.type === 'error') {
            setJob(j => ({ ...j, status: 'error', error: e.message ?? 'An error occurred' }))
            toast(opts.failToast, 'error')
            return
          } else if (e.type === 'awaiting_review') {
            setJob(j => ({ ...j, status: 'review', review: e as SSEReviewEvent, lastEventAt: Date.now() }))
            track('plan_awaiting_review')
            toast('Plan ready to review', 'info')
          } else if (e.type === 'complete') {
            setJob(j => ({ ...j, status: 'done' }))
            invalidateCalendar()
            if (opts.completeToast) toast(opts.completeToast, 'success')
          }
        }
      } catch (err) {
        if (controller.signal.aborted) return  // user cancelled — already reset
        setJob(j => ({ ...j, status: 'error', error: String(err) }))
        toast(opts.failToast, 'error')
      }
    },
    [toast, invalidateCalendar],
  )

  const startRangePlan = useCallback(
    async (dates: string[], opts: RangePlanOptions) => {
      if (ACTIVE_STATUSES.includes(jobRef.current.status)) return
      const sorted = [...dates].sort()
      if (sorted.length === 0) return
      const threadId = `range-${sorted[0]}-${sorted.length}-${Date.now()}`
      setJob({
        kind: 'range', status: 'streaming', dates: sorted, threadId,
        progress: [], review: null, error: null, lastEventAt: Date.now(),
      })
      setPanelOpen(true)
      track('plan_started', { num_days: sorted.length, bulk_prep: opts.bulkEnabled })
      await consumePlanStream(
        '/plan/range',
        {
          start_date: sorted[0],
          num_days: sorted.length,
          bulk_prep_enabled: opts.bulkEnabled,
          bulk_prep_pct: opts.bulkPct / 100,
          bulk_repeat_all_days: opts.bulkRepeatAll,
          special_requests: opts.specialRequests,
          thread_id: threadId,
        },
        { failToast: 'Planning failed' },
      )
    },
    [consumePlanStream],
  )

  const startDayRegen = useCallback(
    async (date: string) => {
      if (ACTIVE_STATUSES.includes(jobRef.current.status)) return
      const controller = new AbortController()
      abortRef.current = controller
      setJob({
        kind: 'day', status: 'streaming', dates: [date], threadId: null,
        progress: [`Regenerating ${date}…`], review: null, error: null, lastEventAt: Date.now(),
      })
      track('plan_day_regenerated')
      try {
        await calendarApi.regenerateDay(date, '', controller.signal)
        setJob(j => ({ ...j, status: 'done' }))
        invalidateCalendar()
        toast('Day updated', 'success')
      } catch (err) {
        if (controller.signal.aborted) return
        setJob(j => ({ ...j, status: 'error', error: String(err) }))
        toast('Regeneration failed', 'error')
      }
    },
    [toast, invalidateCalendar],
  )

  const approve = useCallback(async () => {
    const threadId = jobRef.current.threadId
    if (!threadId) return
    setJob(j => ({ ...j, status: 'committing', lastEventAt: Date.now() }))
    track('plan_approved')
    await consumePlanStream(
      '/plan/range/resume',
      { thread_id: threadId, feedback: 'approve' },
      { failToast: 'Save failed', completeToast: 'Plan saved to calendar' },
    )
  }, [consumePlanStream])

  const revise = useCallback(
    async (feedback: string) => {
      const threadId = jobRef.current.threadId
      if (!threadId || !feedback.trim()) return
      setJob(j => ({ ...j, status: 'streaming', progress: [`Revising — ${feedback}`], review: null, lastEventAt: Date.now() }))
      track('plan_revised')
      await consumePlanStream('/plan/range/resume', { thread_id: threadId, feedback }, { failToast: 'Revision failed' })
    },
    [consumePlanStream],
  )

  const value = useMemo<PlanningContextValue>(
    () => ({ job, panelOpen, openPanel, closePanel, reset, cancel, startRangePlan, startDayRegen, approve, revise }),
    [job, panelOpen, openPanel, closePanel, reset, cancel, startRangePlan, startDayRegen, approve, revise],
  )

  return <PlanningContext.Provider value={value}>{children}</PlanningContext.Provider>
}
