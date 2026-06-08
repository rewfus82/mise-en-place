import { useEffect, useState } from 'react'
import { track } from '../lib/analytics'
import {
  clearLlmCreds,
  getLlmCreds,
  PROVIDER_KEY_HELP,
  PROVIDER_LABELS,
  setLlmCreds,
  type LlmProvider,
} from '../lib/llmKey'

/**
 * BYOK control: a sidebar button showing connection status that opens a modal to
 * enter/replace/clear the visitor's own Claude or OpenAI key. The key lives only in
 * localStorage + request headers; it is never sent anywhere but this app's backend.
 *
 * Self-contained: also opens itself in response to the global `llm-key:open` event
 * dispatched by the API client when a request fails for a missing/invalid key.
 */
export function LlmKeyButton() {
  const [creds, setCreds] = useState(getLlmCreds())
  const [open, setOpen] = useState(false)

  useEffect(() => {
    const onChanged = () => setCreds(getLlmCreds())
    const onOpen = () => setOpen(true)
    window.addEventListener('llm-key:changed', onChanged)
    window.addEventListener('llm-key:open', onOpen)
    return () => {
      window.removeEventListener('llm-key:changed', onChanged)
      window.removeEventListener('llm-key:open', onOpen)
    }
  }, [])

  return (
    <>
      <button
        onClick={() => setOpen(true)}
        className="w-full flex items-center gap-2 rounded-lg px-3 py-2 text-xs font-medium
                   text-slate-300 bg-slate-800/70 hover:bg-slate-800 transition-colors"
      >
        <span
          className={`w-2 h-2 rounded-full shrink-0 ${
            creds ? 'bg-emerald-400' : 'bg-amber-400'
          }`}
        />
        {creds ? `AI: ${PROVIDER_LABELS[creds.provider].split(' ')[0]}` : 'Connect AI to start'}
      </button>

      {open && <LlmKeyModal onClose={() => setOpen(false)} />}
    </>
  )
}

function LlmKeyModal({ onClose }: { onClose: () => void }) {
  const existing = getLlmCreds()
  const [provider, setProvider] = useState<LlmProvider>(existing?.provider ?? 'anthropic')
  const [key, setKey] = useState(existing?.key ?? '')
  const [show, setShow] = useState(false)

  const help = PROVIDER_KEY_HELP[provider]

  function save() {
    if (!key.trim()) return
    setLlmCreds({ provider, key: key.trim() })
    track('ai_provider_connected', { provider })
    onClose()
  }

  function disconnect() {
    clearLlmCreds()
    onClose()
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4"
      onClick={onClose}
    >
      <div
        className="w-full max-w-md rounded-2xl bg-slate-900 border border-slate-700 p-6 shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <h2 className="text-lg font-bold text-slate-100">Connect your AI provider</h2>
        <p className="mt-1 text-sm text-slate-400">
          This is a live demo that runs on <strong className="text-slate-200">your own</strong> API
          key. Pick a provider and paste a key — it's stored only in this browser and sent only to
          this app's backend, which uses it for your requests and never saves it.
        </p>

        <label className="mt-5 block text-xs font-medium uppercase tracking-wide text-slate-500">
          Provider
        </label>
        <div className="mt-2 grid grid-cols-2 gap-2">
          {(['anthropic', 'openai'] as LlmProvider[]).map((p) => (
            <button
              key={p}
              onClick={() => setProvider(p)}
              className={`rounded-lg border px-3 py-2 text-sm font-medium transition-colors ${
                provider === p
                  ? 'border-emerald-500 bg-emerald-500/10 text-emerald-300'
                  : 'border-slate-700 text-slate-300 hover:border-slate-600'
              }`}
            >
              {PROVIDER_LABELS[p]}
            </button>
          ))}
        </div>

        <label className="mt-5 block text-xs font-medium uppercase tracking-wide text-slate-500">
          API key
        </label>
        <div className="mt-2 flex items-center gap-2">
          <input
            type={show ? 'text' : 'password'}
            value={key}
            onChange={(e) => setKey(e.target.value)}
            placeholder={`${help.prefix}…`}
            autoComplete="off"
            spellCheck={false}
            className="flex-1 rounded-lg bg-slate-950 border border-slate-700 px-3 py-2 text-sm
                       text-slate-100 placeholder-slate-600 focus:border-emerald-500 focus:outline-none"
            onKeyDown={(e) => e.key === 'Enter' && save()}
          />
          <button
            onClick={() => setShow((s) => !s)}
            className="rounded-lg border border-slate-700 px-3 py-2 text-xs text-slate-400 hover:text-slate-200"
          >
            {show ? 'Hide' : 'Show'}
          </button>
        </div>
        <a
          href={help.url}
          target="_blank"
          rel="noopener noreferrer"
          className="mt-2 inline-block text-xs text-emerald-400 hover:underline"
        >
          Get a {PROVIDER_LABELS[provider].split(' ')[0]} key ↗
        </a>

        <div className="mt-6 flex items-center justify-between gap-3">
          {existing ? (
            <button
              onClick={disconnect}
              className="text-sm text-slate-400 hover:text-red-400 transition-colors"
            >
              Disconnect
            </button>
          ) : (
            <span />
          )}
          <div className="flex gap-2">
            <button
              onClick={onClose}
              className="rounded-lg px-4 py-2 text-sm text-slate-300 hover:text-slate-100"
            >
              Cancel
            </button>
            <button
              onClick={save}
              disabled={!key.trim()}
              className="rounded-lg bg-emerald-500 px-4 py-2 text-sm font-semibold text-slate-950
                         hover:bg-emerald-400 disabled:opacity-40 disabled:cursor-not-allowed"
            >
              Save key
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
