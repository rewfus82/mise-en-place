import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { calendarApi } from '../api/calendar'

export function useCalendarMonth(year: number, month: number) {
  return useQuery({
    queryKey: ['calendar', year, month],
    queryFn: () => calendarApi.getMonth(year, month),
  })
}

export function useUnconfirmedDays() {
  return useQuery({
    queryKey: ['unconfirmed'],
    queryFn: calendarApi.getUnconfirmed,
  })
}

export function useCalendarMutations() {
  const qc = useQueryClient()

  const invalidateAll = () => {
    qc.invalidateQueries({ queryKey: ['calendar'] })
    qc.invalidateQueries({ queryKey: ['unconfirmed'] })
    qc.invalidateQueries({ queryKey: ['grocery'] })
  }

  const deleteDay = useMutation({
    mutationFn: (date: string) => calendarApi.deleteDay(date),
    onSuccess: invalidateAll,
  })

  const skipDay = useMutation({
    mutationFn: (date: string) => calendarApi.skipDay(date),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['unconfirmed'] }),
  })

  const toggleEaten = useMutation({
    mutationFn: ({ date, mealId, eaten }: { date: string; mealId: number; eaten: boolean }) =>
      calendarApi.toggleEaten(date, mealId, eaten),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['calendar'] })
    },
  })

  const toggleSkipped = useMutation({
    mutationFn: ({ date, mealId, skipped }: { date: string; mealId: number; skipped: boolean }) =>
      calendarApi.toggleSkipped(date, mealId, skipped),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['calendar'] }),
  })

  const endDay = useMutation({
    mutationFn: (date: string) => calendarApi.endDay(date),
    onSuccess: invalidateAll,
  })

  return { deleteDay, skipDay, toggleEaten, toggleSkipped, endDay }
}
