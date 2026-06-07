import React, { useEffect } from 'react'

interface ModalProps {
  open: boolean
  onClose?: () => void
  title?: string
  children: React.ReactNode
  blocking?: boolean
  maxWidth?: string
}

export function Modal({ open, onClose, title, children, blocking = false, maxWidth = 'max-w-lg' }: ModalProps) {
  useEffect(() => {
    if (open) document.body.style.overflow = 'hidden'
    else document.body.style.overflow = ''
    return () => { document.body.style.overflow = '' }
  }, [open])

  if (!open) return null

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      onClick={blocking ? undefined : onClose}
    >
      <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" />
      <div
        className={`relative z-10 w-full ${maxWidth} bg-slate-900 border border-slate-700 rounded-xl shadow-2xl`}
        onClick={(e) => e.stopPropagation()}
      >
        {(title || (!blocking && onClose)) && (
          <div className="flex items-center justify-between px-5 py-4 border-b border-slate-700">
            {title && <h2 className="text-lg font-semibold text-slate-100">{title}</h2>}
            {!blocking && onClose && (
              <button onClick={onClose} className="text-slate-400 hover:text-slate-200 text-xl leading-none">×</button>
            )}
          </div>
        )}
        <div className="p-5">{children}</div>
      </div>
    </div>
  )
}
