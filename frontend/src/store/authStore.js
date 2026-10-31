import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import api from '../utils/api'

const useAuthStore = create(
  persist(
    (set, get) => ({
      user: null,
      token: null,
      refreshToken: null,
      isAuthenticated: false,

      setToken: (token, refreshToken) => {
        set({ token, refreshToken })
        if (token) {
          localStorage.setItem('access_token', token)
          if (refreshToken) localStorage.setItem('refresh_token', refreshToken)
        }
      },

      login: async (email, password) => {
        const res = await api.post('/auth/login', { email, password })
        const { access_token, refresh_token, user } = res.data
        localStorage.setItem('access_token', access_token)
        if (refresh_token) localStorage.setItem('refresh_token', refresh_token)
        set({ user, token: access_token, refreshToken: refresh_token, isAuthenticated: true })
        return user
      },

      register: async (email, username, password, full_name, phone, is_human) => {
        const res = await api.post('/auth/register', { email, username, password, full_name, phone, is_human })
        const { access_token, refresh_token, user } = res.data
        localStorage.setItem('access_token', access_token)
        if (refresh_token) localStorage.setItem('refresh_token', refresh_token)
        set({ user, token: access_token, refreshToken: refresh_token, isAuthenticated: true })
        return user
      },

      logout: () => {
        localStorage.removeItem('access_token')
        localStorage.removeItem('refresh_token')
        set({ user: null, token: null, refreshToken: null, isAuthenticated: false })
      },

      refreshUser: async () => {
        try {
          const res = await api.get('/auth/me')
          set({ user: res.data.user })
        } catch (err) {
          if (err.response?.status === 401) {
            get().logout()
          }
        }
      },

      updateUser: (updates) => set(state => ({ user: { ...state.user, ...updates } })),
    }),
    {
      name: 'excel-analytics-auth',
      partialize: (state) => ({
        user: state.user,
        token: state.token,
        refreshToken: state.refreshToken,
        isAuthenticated: state.isAuthenticated,
      }),
    }
  )
)

export default useAuthStore
