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
      <div className="flex items-center justify-center h-full text-slate-500 text-sm">
        Loading calendar...
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
