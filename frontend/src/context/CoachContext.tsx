/**
 * App-level Nutrition Coach state. The answer stream lives here (not in CoachPage),
 * so an in-flight or completed answer survives navigating away and back.
 */
import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react'
import { streamSSE } from '../api/client'
import { track } from '../lib/analytics'
import type { CoachSSEEvent, CoachSource } from '../types'

export type CoachStatus = 'idle' | 'streaming' | 'done' | 'error'

interface CoachState {
  asked: string
  answer: string
  sources: CoachSource[]
  status: CoachStatus
  error: string | null
}

interface CoachContextValue extends CoachState {
  ask: (question: string) => Promise<void>
  stop: () => void
}

const IDLE: CoachState = { asked: '', answer: '', sources: [], status: 'idle', error: null }

const CoachContext = createContext<CoachContextValue | null>(null)

// eslint-disable-next-line react-refresh/only-export-components
export function useCoach(): CoachContextValue {
  const ctx = useContext(CoachContext)
  if (!ctx) throw new Error('useCoach must be used within a CoachProvider')
  return ctx
}

export function CoachProvider({ children }: { children: React.ReactNode }) {
  const [state, setState] = useState<CoachState>(IDLE)
  const stateRef = useRef(state)
  useEffect(() => {
    stateRef.current = state
  }, [state])
  const abortRef = useRef<AbortController | null>(null)

  const stop = useCallback(() => {
    abortRef.current?.abort()
    abortRef.current = null
    setState(s => (s.status === 'streaming' ? { ...s, status: s.answer ? 'done' : 'idle' } : s))
  }, [])

  const ask = useCallback(async (question: string) => {
    const trimmed = question.trim()
    if (!trimmed || stateRef.current.status === 'streaming') return

    const controller = new AbortController()
    abortRef.current = controller
    setState({ asked: trimmed, answer: '', sources: [], status: 'streaming', error: null })
    track('coach_question_asked')

    try {
      for await (const event of streamSSE('/coach/ask', { question: trimmed }, controller.signal)) {
        const e = event as unknown as CoachSSEEvent
        if (e.type === 'sources') {
          setState(s => ({ ...s, sources: e.sources }))
        } else if (e.type === 'token') {
          setState(s => ({ ...s, answer: s.answer + e.text }))
        } else if (e.type === 'error') {
          setState(s => ({ ...s, status: 'error', error: e.message }))
          return
        } else if (e.type === 'done') {
          setState(s => ({ ...s, status: 'done' }))
        }
      }
    } catch (err) {
      if (controller.signal.aborted) return
      setState(s => ({ ...s, status: 'error', error: String(err) }))
    }
  }, [])

  const value = useMemo<CoachContextValue>(() => ({ ...state, ask, stop }), [state, ask, stop])

  return <CoachContext.Provider value={value}>{children}</CoachContext.Provider>
}
