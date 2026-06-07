import { apiFetch } from './client'
import type { GroceryItem } from '../types'

export const groceryApi = {
  list: () => apiFetch<GroceryItem[]>('/grocery'),

  ignore: (itemName: string) =>
    apiFetch<{ ignored: string }>(`/grocery/${encodeURIComponent(itemName)}/ignore`, {
      method: 'PATCH',
    }),

  markBought: (item: string, quantity: string, category = 'other') =>
    apiFetch<{ added: string[] }>('/grocery/mark-bought', {
      method: 'POST',
      body: JSON.stringify({ item, quantity, category }),
    }),
}
