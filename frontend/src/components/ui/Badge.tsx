import type { ReactNode } from 'react'

type Color = 'emerald' | 'amber' | 'rose' | 'slate' | 'blue' | 'violet' | 'warning'
type Size = 'sm' | 'md'

const colors: Record<Color, string> = {
  emerald: 'bg-emerald-500/15 text-emerald-400',
  amber:   'bg-amber-400/15 text-amber-400',
  warning: 'bg-amber-400/15 text-amber-400',
  rose:    'bg-rose-500/15 text-rose-400',
  slate:   'bg-slate-700/80 text-slate-300',
  blue:    'bg-blue-500/15 text-blue-400',
  violet:  'bg-violet-500/15 text-violet-400',
}

const sizes: Record<Size, string> = {
  sm: 'px-1.5 py-0.5 text-[10px]',
  md: 'px-2 py-0.5 text-xs',
}

interface BadgeProps {
  label?: string
  children?: ReactNode
  color?: Color
  size?: Size
}

export function Badge({ label, children, color = 'slate', size = 'md' }: BadgeProps) {
  return (
    <span className={`inline-block rounded-full font-medium leading-none ${colors[color]} ${sizes[size]}`}>
      {children ?? label}
    </span>
  )
}
