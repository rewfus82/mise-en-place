import { useQuery } from '@tanstack/react-query'
import { calendarApi } from '../api/calendar'

const TODAY_KEY = 'lastDailyPromptCheck'

export function useDailyPrompt() {
  const today = new Date().toISOString().split('T')[0]
  const lastChecked = localStorage.getItem(TODAY_KEY)
  const alreadyCheckedToday = lastChecked === today

  const query = useQuery({
    queryKey: ['unconfirmed'],
    queryFn: calendarApi.getUnconfirmed,
    enabled: !alreadyCheckedToday,
  })

  const shouldShow = !alreadyCheckedToday && (query.data?.length ?? 0) > 0

  const markChecked = () => {
    localStorage.setItem(TODAY_KEY, today)
  }

  return { shouldShow, unconfirmedDays: query.data ?? [], markChecked }
}
