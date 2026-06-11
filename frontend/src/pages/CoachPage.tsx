import { useState, useRef, useEffect } from 'react'
import { useCoach } from '../context/CoachContext'
import type { CoachSource } from '../types'
import { Button } from '../components/ui/Button'

const SUGGESTIONS = [
  'How much protein per kg should I eat to build muscle?',
  'How do I dose creatine?',
  'When should I take caffeine before a workout?',
  'How much protein can I absorb in one meal?',
  'How fast should I lose weight to keep muscle?',
]

/** Render answer text, turning [n] citation markers into clickable superscripts. */
function renderAnswer(text: string, sources: CoachSource[]) {
  const byN = new Map(sources.map(s => [s.n, s]))
  const parts = text.split(/(\[\d+\])/g)
  return parts.map((part, i) => {
    const m = part.match(/^\[(\d+)\]$/)
    if (!m) return <span key={i}>{part}</span>
    const n = Number(m[1])
    const src = byN.get(n)
    const sup = (
      <sup className="text-emerald-400 font-semibold">[{n}]</sup>
    )
    return src?.url ? (
      <a
        key={i}
        href={src.url}
        target="_blank"
        rel="noopener noreferrer"
        title={src.citation}
        className="hover:underline"
      >
        {sup}
      </a>
    ) : (
      <span key={i}>{sup}</span>
    )
  })
}

export function CoachPage() {
  const { asked, answer, sources, status, error, ask, stop } = useCoach()
  const [question, setQuestion] = useState('')
  const [copied, setCopied] = useState(false)
  const answerEndRef = useRef<HTMLDivElement>(null)

  const copyAnswer = async () => {
    try {
      await navigator.clipboard.writeText(answer)
      setCopied(true)
      setTimeout(() => setCopied(false), 1500)
    } catch { /* clipboard unavailable */ }
  }

  useEffect(() => {
    answerEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [answer])

  const submit = (q: string) => {
    if (!q.trim() || status === 'streaming') return
    setQuestion('')
    ask(q)
  }

  return (
    <div className="max-w-2xl mx-auto px-6 py-8 space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-slate-100">Nutrition Coach</h1>
        <p className="text-sm text-slate-400 mt-1">
          Evidence-based answers, grounded in sports-nutrition research and cited to source.
        </p>
      </div>

      {/* Ask box */}
      <div className="flex gap-2">
        <input
          type="text"
          value={question}
          onChange={e => setQuestion(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && submit(question)}
          placeholder="Ask about protein, creatine, caffeine, cutting…"
          className="flex-1 bg-slate-800 border border-slate-700 rounded-lg px-4 py-2.5 text-sm text-slate-100 placeholder-slate-500 focus:outline-none focus:border-emerald-500"
        />
        {status === 'streaming' ? (
          <Button variant="secondary" onClick={stop}>
            Stop
          </Button>
        ) : (
          <Button variant="primary" onClick={() => submit(question)} disabled={!question.trim()}>
            Ask
          </Button>
        )}
      </div>

      {/* Empty state: suggested questions */}
      {status === 'idle' && (
        <div className="space-y-2">
          <p className="text-xs text-slate-500 uppercase tracking-wider font-medium">Try asking</p>
          <div className="flex flex-wrap gap-2">
            {SUGGESTIONS.map(s => (
              <button
                key={s}
                onClick={() => submit(s)}
                className="text-xs text-slate-300 bg-slate-800 hover:bg-slate-700 border border-slate-700 rounded-full px-3 py-1.5 transition-colors cursor-pointer"
              >
                {s}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Conversation */}
      {asked && (
        <div className="space-y-4">
          <div className="text-sm font-medium text-slate-300 bg-slate-800/50 border border-slate-700/60 rounded-lg px-4 py-2.5">
            {asked}
          </div>

          {error ? (
            <div className="text-sm text-rose-400 bg-rose-500/10 border border-rose-500/20 rounded-lg px-4 py-3">
              {error}
            </div>
          ) : (
            <div className="bg-slate-900 border border-slate-800 rounded-xl px-5 py-4">
              {answer === '' && status === 'streaming' ? (
                <div className="flex items-center gap-2 text-slate-500 text-sm">
                  <span className="w-4 h-4 border-2 border-emerald-400 border-t-transparent rounded-full animate-spin" />
                  Searching the research…
                </div>
              ) : (
                <p className="text-sm text-slate-200 leading-relaxed whitespace-pre-wrap">
                  {renderAnswer(answer, sources)}
                  {status === 'streaming' && <span className="animate-pulse">▋</span>}
                </p>
              )}
              <div ref={answerEndRef} />
              {answer && status !== 'streaming' && (
                <div className="flex justify-end mt-2 pt-2 border-t border-slate-800/60">
                  <button
                    onClick={copyAnswer}
                    className="text-[11px] text-slate-500 hover:text-emerald-400 transition-colors cursor-pointer flex items-center gap-1"
                  >
                    {copied ? (
                      <>
                        <svg className="w-3 h-3" fill="none" viewBox="0 0 12 12">
                          <path d="M2 6l2.5 2.5L10 3" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
                        </svg>
                        Copied
                      </>
                    ) : (
                      <>
                        <svg className="w-3 h-3" fill="none" viewBox="0 0 12 12">
                          <rect x="3" y="3" width="6" height="6" rx="1" stroke="currentColor" strokeWidth="1.2" />
                          <path d="M2 8V2h6" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" />
                        </svg>
                        Copy
                      </>
                    )}
                  </button>
                </div>
              )}
            </div>
          )}

          {/* Sources */}
          {sources.length > 0 && (
            <div className="space-y-2">
              <p className="text-xs text-slate-500 uppercase tracking-wider font-medium">Sources</p>
              <ol className="space-y-1.5">
                {sources.map(s => (
                  <li key={s.n} className="text-xs text-slate-400 flex gap-2">
                    <span className="text-emerald-400 font-semibold shrink-0">[{s.n}]</span>
                    <span>
                      {s.url ? (
                        <a
                          href={s.url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-slate-300 hover:text-emerald-400 hover:underline"
                        >
                          {s.citation}
                        </a>
                      ) : (
                        <span className="text-slate-300">{s.citation}</span>
                      )}
                      {s.title && <span className="text-slate-500"> — {s.title}</span>}
                      {s.section && <span className="text-slate-600"> · {s.section}</span>}
                    </span>
                  </li>
                ))}
              </ol>
              <p className="text-[10px] text-slate-600 pt-1">
                Educational information, not medical advice. Sources are open-access ISSN
                position stands (CC BY).
              </p>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
