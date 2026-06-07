import { NavLink } from 'react-router-dom'

const links = [
  {
    to: '/calendar',
    label: 'Calendar',
    icon: (
      <svg className="w-4 h-4" fill="none" viewBox="0 0 20 20">
        <rect x="3" y="4" width="14" height="13" rx="2" stroke="currentColor" strokeWidth="1.5" />
        <path d="M3 8h14M7 2v4M13 2v4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
      </svg>
    ),
  },
  {
    to: '/pantry',
    label: 'Pantry',
    icon: (
      <svg className="w-4 h-4" fill="none" viewBox="0 0 20 20">
        <path d="M6 2h8l2 4H4L6 2z" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round" />
        <rect x="3" y="6" width="14" height="12" rx="1.5" stroke="currentColor" strokeWidth="1.5" />
        <path d="M8 10h4M8 13h4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
      </svg>
    ),
  },
  {
    to: '/grocery',
    label: 'Grocery',
    icon: (
      <svg className="w-4 h-4" fill="none" viewBox="0 0 20 20">
        <path d="M3 3h2l2.5 9.5h8L17 7H7" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
        <circle cx="9.5" cy="16.5" r="1" fill="currentColor" />
        <circle cx="14.5" cy="16.5" r="1" fill="currentColor" />
      </svg>
    ),
  },
  {
    to: '/profile',
    label: 'Profile',
    icon: (
      <svg className="w-4 h-4" fill="none" viewBox="0 0 20 20">
        <circle cx="10" cy="7" r="3" stroke="currentColor" strokeWidth="1.5" />
        <path d="M4 17c0-3.314 2.686-5 6-5s6 1.686 6 5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
      </svg>
    ),
  },
]

export function Sidebar() {
  return (
    <aside className="w-52 shrink-0 bg-slate-900 border-r border-slate-800/60 flex flex-col">
      {/* Brand */}
      <div className="px-5 py-5 border-b border-slate-800/60">
        <div className="text-base font-bold text-slate-100 tracking-tight">mise-en-place</div>
        <div className="text-[11px] text-slate-500 mt-0.5 font-medium uppercase tracking-wider">Meal Tracker</div>
      </div>

      {/* Nav */}
      <nav className="flex-1 px-3 py-4 space-y-0.5">
        {links.map(({ to, label, icon }) => (
          <NavLink
            key={to}
            to={to}
            className={({ isActive }) => `
              flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm transition-colors
              ${isActive
                ? 'bg-emerald-500/10 text-emerald-400 font-medium'
                : 'text-slate-400 hover:text-slate-100 hover:bg-slate-800/70'}
            `}
          >
            {icon}
            {label}
          </NavLink>
        ))}
      </nav>

      {/* Footer */}
      <div className="px-5 py-4 border-t border-slate-800/60">
        <div className="text-[10px] text-slate-600 font-medium">Powered by Claude + LangGraph</div>
      </div>
    </aside>
  )
}
