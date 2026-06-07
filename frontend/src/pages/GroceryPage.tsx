import { GroceryList } from '../components/grocery/GroceryList'
import { useGrocery } from '../hooks/useGrocery'

export function GroceryPage() {
  const { data: items = [] } = useGrocery()

  return (
    <div className="max-w-2xl mx-auto px-6 py-8 space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-slate-100">Grocery List</h1>
        <p className="text-sm text-slate-400 mt-1">
          {items.length === 0
            ? 'Nothing needed right now'
            : `${items.length} item${items.length !== 1 ? 's' : ''} to buy`}
        </p>
      </div>
      <GroceryList />
    </div>
  )
}
