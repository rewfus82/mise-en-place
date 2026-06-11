import { useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useCalendarMonth } from '../hooks/useCalendar'
import { profileApi } from '../api/profile'
import { weightLogApi } from '../api/weightLog'
import { CalendarView } from '../components/calendar/CalendarView'

export function CalendarPage() {
  const now = new Date()
  const [year, setYear] = useState(now.getFullYear())
  const [month, setMonth] = useState(now.getMonth() + 1)

  const { data: days = [], isLoading } = useCalendarMonth(year, month)
  const { data: profile } = useQuery({ queryKey: ['profile'], queryFn: profileApi.get })
  const { data: weightEntries = [] } = useQuery({
    queryKey: ['weight-log'],
    queryFn: weightLogApi.list,
  })

  const weightByDate = useMemo(() => {
    const map = new Map<string, number>()
    for (const e of weightEntries) map.set(e.date, e.weight_kg)
    return map
  }, [weightEntries])

  if (isLoading) {
    return (
      <div className="h-screen flex flex-col px-6 py-4">
        <div className="h-7 w-44 bg-slate-800 rounded animate-pulse mb-5" />
        <div className="grid grid-cols-7 gap-2 mb-2">
          {Array.from({ length: 7 }).map((_, i) => (
            <div key={i} className="h-3 w-10 mx-auto bg-slate-800/70 rounded animate-pulse" />
          ))}
        </div>
        <div className="space-y-2">
          {Array.from({ length: 4 }).map((_, w) => (
            <div key={w} className="grid grid-cols-7 gap-2">
              {Array.from({ length: 7 }).map((_, d) => (
                <div key={d} className="min-h-[92px] rounded-xl bg-slate-900 border border-slate-800/60 animate-pulse" />
              ))}
            </div>
          ))}
        </div>
      </div>
    )
  }

  return (
    <div className="h-screen flex flex-col">
      <CalendarView
        year={year}
        month={month}
        days={days}
        profile={profile}
        weightByDate={weightByDate}
        onMonthChange={(y, m) => { setYear(y); setMonth(m) }}
      />
    </div>
  )
}
