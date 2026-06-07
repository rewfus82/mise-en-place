import { apiFetch } from './client'
import type { MealDay, MealPrep } from '../types'

export const calendarApi = {
  getMonth: (year: number, month: number) =>
    apiFetch<MealDay[]>(`/calendar/${year}/${month}`),

  getUnconfirmed: () =>
    apiFetch<MealDay[]>('/calendar/unconfirmed'),

  deleteDay: (date: string) =>
    apiFetch<{ deleted: string }>(`/calendar/${date}`, { method: 'DELETE' }),

  skipDay: (date: string) =>
    apiFetch<{ skipped: string }>(`/calendar/${date}/skip`, { method: 'POST' }),

  regenerateDay: (date: string, special_requests = '') =>
    apiFetch<{ date: string; meal_count: number }>('/plan/day', {
      method: 'POST',
      body: JSON.stringify({ date, special_requests }),
    }),

  toggleEaten: (date: string, mealId: number, eaten: boolean) =>
    apiFetch<{ meal_id: number; eaten: boolean }>(
      `/days/${date}/meals/${mealId}/eaten`,
      { method: 'PATCH', body: JSON.stringify({ eaten }) }
    ),

  toggleSkipped: (date: string, mealId: number, skipped: boolean) =>
    apiFetch<{ meal_id: number; skipped: boolean }>(
      `/days/${date}/meals/${mealId}/skipped`,
      { method: 'PATCH', body: JSON.stringify({ skipped }) }
    ),

  endDay: (date: string) =>
    apiFetch<{ auto_deducted: unknown[]; needs_confirmation: unknown[] }>(
      `/days/${date}/end`,
      { method: 'POST' }
    ),

  getMealPreps: () =>
    apiFetch<MealPrep[]>('/calendar/meal-preps'),
}
