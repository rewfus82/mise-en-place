import { Button } from '../ui/Button'

interface SelectionToolbarProps {
  selectedCount: number
  onPlan: () => void
  onClear: () => void
}

export function SelectionToolbar({ selectedCount, onPlan, onClear }: SelectionToolbarProps) {
  if (selectedCount === 0) return null

  return (
    <div className="
      fixed bottom-8 left-1/2 -translate-x-1/2 z-40
      flex items-center gap-4
      bg-slate-800 border border-slate-600/80
      rounded-2xl px-5 py-3
      shadow-2xl shadow-black/60
      backdrop-blur-sm
      animate-in fade-in slide-in-from-bottom-2 duration-200
    ">
      <div className="flex items-center gap-2">
        <div className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
        <span className="text-sm font-medium text-slate-200">
          {selectedCount} day{selectedCount !== 1 ? 's' : ''} selected
        </span>
      </div>
      <div className="w-px h-4 bg-slate-600" />
      <Button variant="primary" size="sm" onClick={onPlan}>
        Plan →
      </Button>
      <button
        onClick={onClear}
        className="text-xs text-slate-500 hover:text-slate-300 transition-colors cursor-pointer"
      >
        Clear
      </button>
    </div>
  )
}
