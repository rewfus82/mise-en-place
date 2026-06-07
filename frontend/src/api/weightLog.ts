import { apiFetch } from './client'
import type { MeasuredTdee, WeightEntry } from '../types'

export const weightLogApi = {
  list: () => apiFetch<WeightEntry[]>('/weight-log'),

  upsert: (date: string, weight_kg: number, notes?: string) =>
    apiFetch<WeightEntry>('/weight-log', {
      method: 'POST',
      body: JSON.stringify({ date, weight_kg, notes }),
    }),

  remove: (date: string) =>
    apiFetch<void>(`/weight-log/${date}`, { method: 'DELETE' }),

  getMeasuredTdee: () =>
    apiFetch<MeasuredTdee | null>('/weight-log/measured-tdee'),
}
