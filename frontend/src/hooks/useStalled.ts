import { useEffect, useState } from 'react'

/**
 * True when `active` and no fresh event has arrived for `thresholdMs`.
 * Used to surface a "still working — provider may be rate-limiting" hint when an
 * LLM call is silently backing off on 429s and the UI would otherwise look frozen.
 *
 * Staleness is derived from an interval-updated clock so the effect never calls
 * setState synchronously (which would trigger cascading renders).
 */
export function useStalled(lastEventAt: number, active: boolean, thresholdMs = 12000): boolean {
  const [now, setNow] = useState(() => Date.now())

  useEffect(() => {
    if (!active) return
    const id = setInterval(() => setNow(Date.now()), 2000)
    return () => clearInterval(id)
  }, [active])

  return active && now - lastEventAt > thresholdMs
}
