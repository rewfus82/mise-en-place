import { useState } from 'react'
import { usePantryMutations } from '../../hooks/usePantry'
import { Button } from '../ui/Button'
import type { PantryItem } from '../../types'

interface PantryTableProps {
  items: PantryItem[]
}

export function PantryTable({ items }: PantryTableProps) {
  const [search, setSearch] = useState('')
  const { remove, clear } = usePantryMutations()

  const filtered = items.filter(i =>
    i.item.toLowerCase().includes(search.toLowerCase())
  )

  const grouped = filtered.reduce<Record<string, PantryItem[]>>((acc, item) => {
    const cat = item.category || 'Other'
    if (!acc[cat]) acc[cat] = []
    acc[cat].push(item)
    return acc
  }, {})

  if (items.length === 0) {
    return (
      <div className="text-center py-10 text-slate-500 text-sm">
        Your pantry is empty. Add items above.
      </div>
    )
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3">
        <input
          type="text"
          value={search}
          onChange={e => setSearch(e.target.value)}
          placeholder="Search pantry..."
          className="flex-1 bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm text-slate-100 placeholder-slate-500 focus:outline-none focus:border-emerald-500"
        />
        <Button
          variant="danger"
          size="sm"
          onClick={() => window.confirm('Clear entire pantry?') && clear.mutate()}
          loading={clear.isPending}
        >
          Clear All
        </Button>
      </div>

      {Object.entries(grouped).sort().map(([category, catItems]) => (
        <div key={category}>
          <div className="text-xs text-slate-500 uppercase tracking-wide font-medium mb-2 px-1">{category}</div>
          <div className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden">
            {catItems.map((item, i) => (
              <div
                key={item.id}
                className={`flex items-center justify-between px-4 py-3 ${i > 0 ? 'border-t border-slate-800' : ''}`}
              >
                <div>
                  <span className="text-sm text-slate-200">{item.item}</span>
                  <span className="text-xs text-slate-500 ml-2">{item.quantity}</span>
                </div>
                <button
                  onClick={() => remove.mutate(item.item)}
                  className="text-xs text-slate-500 hover:text-rose-400 transition-colors cursor-pointer px-2 py-1"
                >
                  Remove
                </button>
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  )
}
