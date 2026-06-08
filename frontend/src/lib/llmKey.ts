// BYOK (bring-your-own-key) credential handling — client side only.
//
// This is a public demo: the visitor supplies their own provider + API key. We keep
// it in localStorage and attach it to API requests via headers. The key is sent only
// to this app's backend, which uses it in-memory for that request and never stores it.

export type LlmProvider = 'anthropic' | 'openai'

export interface LlmCreds {
  provider: LlmProvider
  key: string
}

const STORAGE_KEY = 'mep.llm'

export const PROVIDER_LABELS: Record<LlmProvider, string> = {
  anthropic: 'Claude (Anthropic)',
  openai: 'ChatGPT (OpenAI)',
}

export const PROVIDER_KEY_HELP: Record<LlmProvider, { prefix: string; url: string }> = {
  anthropic: { prefix: 'sk-ant-', url: 'https://console.anthropic.com/settings/keys' },
  openai: { prefix: 'sk-', url: 'https://platform.openai.com/api-keys' },
}

export function getLlmCreds(): LlmCreds | null {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return null
    const parsed = JSON.parse(raw)
    if (
      parsed &&
      (parsed.provider === 'anthropic' || parsed.provider === 'openai') &&
      typeof parsed.key === 'string' &&
      parsed.key.trim()
    ) {
      return { provider: parsed.provider, key: parsed.key }
    }
  } catch {
    /* corrupt value — treat as unset */
  }
  return null
}

export function setLlmCreds(creds: LlmCreds): void {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(creds))
  window.dispatchEvent(new CustomEvent('llm-key:changed'))
}

export function clearLlmCreds(): void {
  localStorage.removeItem(STORAGE_KEY)
  window.dispatchEvent(new CustomEvent('llm-key:changed'))
}

/** Headers to attach to any request that may trigger an LLM call. Empty if unset. */
export function llmHeaders(): Record<string, string> {
  const creds = getLlmCreds()
  return creds ? { 'X-LLM-Provider': creds.provider, 'X-LLM-Key': creds.key } : {}
}

/** Ask the app to pop the key modal (e.g. after a missing/invalid-key error). */
export function openLlmKeyModal(): void {
  window.dispatchEvent(new CustomEvent('llm-key:open'))
}

/** Heuristic: does this error text look like a missing/invalid key problem? */
export function looksLikeKeyError(text: string): boolean {
  return /api key|provider|unauthorized|401|invalid x-api-key|authentication/i.test(text)
}
