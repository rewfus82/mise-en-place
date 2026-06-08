import { useState } from 'react'
import { track } from '../../lib/analytics'
import { usePantryMutations } from '../../hooks/usePantry'
import { Button } from '../ui/Button'

export function PantryParser() {
  const [text, setText] = useState('')
  const [result, setResult] = useState<{ added: string[]; skipped: string[] } | null>(null)
  const { parse } = usePantryMutations()

  const handleParse = async () => {
    const res = await parse.mutateAsync(text)
    track('pantry_parsed', { added: res.added.length, skipped: res.skipped.length })
    setResult(res)
    if (res.added.length > 0) setText('')
  }

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-xl p-4 space-y-3">
      <div>
        <label className="text-sm font-medium text-slate-200 block mb-1.5">Add items by description</label>
        <p className="text-xs text-slate-500 mb-2">Type naturally, e.g. "2 lbs chicken breast, a dozen eggs, 1 cup rice"</p>
        <textarea
          value={text}
          onChange={e => { setText(e.target.value); setResult(null) }}
          placeholder="Describe what you have..."
          rows={3}
          className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm text-slate-100 placeholder-slate-500 resize-none focus:outline-none focus:border-emerald-500"
        />
      </div>

      {result && (
        <div className="space-y-1 text-xs">
          {result.added.length > 0 && (
            <div className="text-emerald-400">Added: {result.added.join(', ')}</div>
          )}
          {result.skipped.length > 0 && (
            <div className="text-amber-400">Couldn't parse: {result.skipped.join(', ')}</div>
          )}
        </div>
      )}

      <Button
        variant="primary"
        onClick={handleParse}
        loading={parse.isPending}
        disabled={!text.trim()}
      >
        Parse & Add
      </Button>
    </div>
  )
}
