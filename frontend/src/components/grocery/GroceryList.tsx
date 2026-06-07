import { useGrocery, useGroceryMutations } from '../../hooks/useGrocery'
import { Badge } from '../ui/Badge'
import { Button } from '../ui/Button'
import type { GroceryItem } from '../../types'

function DateLabel({ date }: { date: string }) {
  const today = new Date().toISOString().split('T')[0]
  const tomorrow = new Date(Date.now() + 86400000).toISOString().split('T')[0]
  if (date === today) return <span className="text-rose-400 font-semibold">Today</span>
  if (date === tomorrow) return <span className="text-amber-400 font-semibold">Tomorrow</span>
  return <span>{new Date(date + 'T12:00:00').toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric' })}</span>
}

interface GroupedItem {
  date: string
  items: GroceryItem[]
}

export function GroceryList() {
  const { data: items = [], isLoading } = useGrocery()
  const { ignore, markBought } = useGroceryMutations()

  if (isLoading) return <div className="text-slate-500 text-sm p-6">Loading...</div>

  if (items.length === 0) {
    return (
      <div className="text-center py-16 space-y-2">
        <div className="text-4xl">✓</div>
        <div className="text-slate-300 font-medium">You're fully stocked</div>
        <div className="text-slate-500 text-sm">No grocery runs needed for planned meals</div>
      </div>
    )
  }

  // Group by needed_by_date
  const grouped = items.reduce<Record<string, GroceryItem[]>>((acc, item) => {
    const d = item.needed_by_date
    if (!acc[d]) acc[d] = []
    acc[d].push(item)
    return acc
  }, {})

  const sortedGroups: GroupedItem[] = Object.entries(grouped)
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([date, items]) => ({ date, items }))

  return (
    <div className="space-y-6">
      {sortedGroups.map(({ date, items: groupItems }) => (
        <div key={date}>
          <div className="text-sm font-medium text-slate-400 mb-2 px-1 flex items-center gap-2">
            Needed by <DateLabel date={date} />
          </div>
          <div className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden">
            {groupItems.map((item, i) => (
              <div
                key={item.ingredient}
                className={`flex items-center justify-between px-4 py-3 ${i > 0 ? 'border-t border-slate-800' : ''}`}
              >
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="text-sm text-slate-200">{item.ingredient}</span>
                    {!item.deficit_calculable && (
                      <Badge color="warning" size="sm">check manually</Badge>
                    )}
                  </div>
                  <div className="text-xs text-slate-500 mt-0.5">
                    {item.deficit_calculable
                      ? `${item.quantity_needed}${item.unit ? ` ${item.unit}` : ''} needed`
                      : 'Quantity unknown'}
                  </div>
                </div>
                <div className="flex gap-2 shrink-0 ml-3">
                  <Button
                    variant="primary"
                    size="sm"
                    onClick={() => markBought.mutate({
                      item: item.ingredient,
                      quantity: `${item.quantity_needed} ${item.unit ?? ''}`.trim(),
                    })}
                    loading={markBought.isPending}
                  >
                    Buy it
                  </Button>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => ignore.mutate(item.ingredient)}
                  >
                    Ignore
                  </Button>
                </div>
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  )
}
