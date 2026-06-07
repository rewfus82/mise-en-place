import { usePantry } from '../../hooks/usePantry'
import { PantryParser } from './PantryParser'
import { PantryTable } from './PantryTable'

export function PantryView() {
  const { data: items = [], isLoading } = usePantry()

  return (
    <div className="max-w-2xl mx-auto px-6 py-8 space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-slate-100">Pantry</h1>
        <p className="text-sm text-slate-400 mt-1">
          {items.length} item{items.length !== 1 ? 's' : ''} on hand
        </p>
      </div>

      <PantryParser />

      {isLoading ? (
        <div className="text-slate-500 text-sm">Loading...</div>
      ) : (
        <PantryTable items={items} />
      )}
    </div>
  )
}
