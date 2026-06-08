// Thin wrapper over GA4's gtag. Safe to call even if the GA script hasn't loaded
// (or was blocked) — calls just no-op. NEVER pass PII or API keys here; only
// action names and harmless counters.

type Params = Record<string, unknown>

function gtag(...args: unknown[]) {
  const w = window as unknown as { gtag?: (...a: unknown[]) => void }
  if (typeof w.gtag === 'function') w.gtag(...args)
}

/** Fire a custom event, e.g. track('plan_started', { num_days: 7 }). */
export function track(event: string, params?: Params) {
  gtag('event', event, params ?? {})
}

/** Send a SPA page_view (GA config has send_page_view disabled — we drive it). */
export function trackPageView(path: string) {
  gtag('event', 'page_view', {
    page_path: path,
    page_location: window.location.origin + path,
    page_title: document.title,
  })
}
