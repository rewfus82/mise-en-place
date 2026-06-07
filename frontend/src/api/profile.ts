import { apiFetch } from './client'
import type { TdeeResponse, UserProfile } from '../types'

export const profileApi = {
  get: () => apiFetch<UserProfile>('/profile'),
  update: (data: Partial<UserProfile>) =>
    apiFetch<UserProfile>('/profile', {
      method: 'PUT',
      body: JSON.stringify(data),
    }),
  getTdee: () => apiFetch<TdeeResponse>('/profile/tdee'),
}
