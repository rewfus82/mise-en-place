import { useState } from 'react'
import { usePantryMutations } from '../../hooks/usePantry'
import { Button } from '../ui/Button'
import { Modal } from '../ui/Modal'

interface AmbiguousQtyPromptProps {
  items: Array<{ item: string; quantity: string | null; unit: string | null }>
  onClose: () => void
}

export function AmbiguousQtyPrompt({ items, onClose }: AmbiguousQtyPromptProps) {
  const [checked, setChecked] = useState<Set<string>>(new Set())
  const { deplete } = usePantryMutations()

  if (items.length === 0) return null

  const toggle = (item: string) =>
    setChecked(prev => {
      const next = new Set(prev)
      if (next.has(item)) next.delete(item)
      else next.add(item)
      return next
    })

  const handleConfirm = async () => {
    if (checked.size > 0) {
      await deplete.mutateAsync(Array.from(checked))
    }
    onClose()
  }

  return (
    <Modal open title="Did you finish any of these?" blocking>
      <p className="text-sm text-slate-400 mb-4">
        I couldn't calculate exact amounts for these items. Check off anything you used up completely.
      </p>
      <div className="space-y-2 mb-5">
        {items.map(({ item, quantity, unit }) => (
          <label key={item} className="flex items-center gap-3 cursor-pointer p-2 rounded-lg hover:bg-slate-800">
            <input
              type="checkbox"
              checked={checked.has(item)}
              onChange={() => toggle(item)}
              className="w-4 h-4 accent-emerald-500"
            />
            <div>
              <span className="text-sm text-slate-200">{item}</span>
              {quantity && (
                <span className="text-xs text-slate-500 ml-2">{quantity} {unit ?? ''}</span>
              )}
            </div>
          </label>
        ))}
      </div>
      <div className="flex gap-2 justify-end">
        <Button variant="ghost" onClick={onClose}>None of these</Button>
        <Button variant="primary" onClick={handleConfirm} loading={deplete.isPending}>
          Remove selected
        </Button>
      </div>
    </Modal>
  )
}
