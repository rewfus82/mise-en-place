import { apiFetch } from './client'
import type { PantryItem } from '../types'

export const pantryApi = {
  list: () => apiFetch<PantryItem[]>('/pantry'),

  add: (items: Array<{ item: string; quantity: string; category: string }>) =>
    apiFetch<{ added: string[]; skipped: string[] }>('/pantry', {
      method: 'POST',
      body: JSON.stringify({ items }),
    }),

  remove: (itemName: string) =>
    apiFetch<{ removed: string[] }>(`/pantry/${encodeURIComponent(itemName)}`, {
      method: 'DELETE',
    }),

  clear: () =>
    apiFetch<{ cleared: boolean }>('/pantry', { method: 'DELETE' }),

  parse: (text: string) =>
    apiFetch<{ added: string[]; skipped: string[] }>('/pantry/parse', {
      method: 'POST',
      body: JSON.stringify({ text }),
    }),

  deplete: (items: string[]) =>
    apiFetch<{ removed: string[] }>('/pantry/deplete', {
      method: 'POST',
      body: JSON.stringify({ items }),
    }),
}
