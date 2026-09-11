import { defineStore } from 'pinia'
import api from '../api'

export type LoginKind = 'developer' | 'admin' | 'student'

export const useAuthStore = defineStore('auth', {
  state: () => ({
    token: localStorage.getItem('sports_token') || '',
    user: JSON.parse(localStorage.getItem('sports_user') || 'null') as any,
  }),
  actions: {
    async login(kind: LoginKind, username: string, password: string) {
      const { data } = await api.post(`/auth/${kind}-login`, { username, password })
      this.token = data.access_token
      this.user = data.user
      localStorage.setItem('sports_token', data.access_token)
      localStorage.setItem('sports_user', JSON.stringify(data.user))
      return data
    },
    logout() {
      this.token = ''
      this.user = null
      localStorage.removeItem('sports_token')
      localStorage.removeItem('sports_user')
    },
  },
})
