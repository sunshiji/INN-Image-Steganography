import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { authApi } from '@/api/auth'

export interface User {
  id: number
  username: string
  email?: string
  fullName?: string
  isActive: boolean
  isAdmin: boolean
  createdAt: string
}

export const useUserStore = defineStore('user', () => {
  const token = ref<string | null>(localStorage.getItem('token'))
  const user = ref<User | null>(null)
  const initialized = ref(false)

  const isLoggedIn = computed(() => !!token.value && initialized.value)
  const isAdmin = computed(() => user.value?.isAdmin ?? false)

  async function login(username: string, password: string) {
    const response = await authApi.login(username, password)
    token.value = response.access_token
    localStorage.setItem('token', response.access_token)
    await fetchUserInfo()
    return response
  }

  async function register(username: string, password: string, email?: string, fullName?: string) {
    return await authApi.register(username, password, email, fullName)
  }

  async function logout() {
    try {
      await authApi.logout()
    } catch (e) {
      console.error('Logout error:', e)
    } finally {
      token.value = null
      user.value = null
      localStorage.removeItem('token')
    }
  }

  async function fetchUserInfo() {
    try {
      const response = await authApi.getCurrentUser()
      user.value = response
      return response
    } catch (e) {
      console.error('Fetch user info error:', e)
      throw e
    }
  }

  async function initialize() {
    if (token.value) {
      try {
        await fetchUserInfo()
      } catch {
        token.value = null
        localStorage.removeItem('token')
      }
    }
    initialized.value = true
  }

  return {
    token,
    user,
    initialized,
    isLoggedIn,
    isAdmin,
    login,
    register,
    logout,
    fetchUserInfo,
    initialize
  }
})
