import { llmHeaders, looksLikeKeyError, openLlmKeyModal } from '../lib/llmKey'

const BASE = '/api'

export async function apiFetch<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...llmHeaders(),
      ...options?.headers,
    },
  })
  if (!res.ok) {
    const text = await res.text()
    if (res.status === 400 && looksLikeKeyError(text)) openLlmKeyModal()
    throw new Error(`${res.status} ${res.statusText}: ${text}`)
  }
  return res.json() as Promise<T>
}

export async function* streamSSE(path: string, body: unknown): AsyncGenerator<Record<string, unknown>> {
  const res = await fetch(`${BASE}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...llmHeaders() },
    body: JSON.stringify(body),
  })
  if (!res.ok || !res.body) throw new Error(`SSE request failed: ${res.status}`)

  const reader = res.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    const parts = buffer.split('\n\n')
    buffer = parts.pop() ?? ''
    for (const part of parts) {
      const line = part.trim()
      if (line.startsWith('data: ')) {
        try {
          const event = JSON.parse(line.slice(6))
          // Backend reports a missing/invalid key as an error event — surface the
          // key modal so the user can fix it without hunting for the button.
          if (
            event?.type === 'error' &&
            typeof event.message === 'string' &&
            looksLikeKeyError(event.message)
          ) {
            openLlmKeyModal()
          }
          yield event
        } catch {
          // skip malformed
        }
      }
    }
  }
}
