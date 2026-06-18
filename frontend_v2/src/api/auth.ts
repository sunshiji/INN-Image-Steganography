import api from './index'

export interface LoginResponse {
  access_token: string
  token_type: string
}

export interface UserInfo {
  id: number
  username: string
  email?: string
  fullName?: string
  isActive: boolean
  isAdmin: boolean
  createdAt: string
}

export const authApi = {
  async login(username: string, password: string): Promise<LoginResponse> {
    const response = await api.post('/auth/login', { username, password })
    return response.data
  },

  async register(
    username: string,
    password: string,
    email?: string,
    fullName?: string
  ): Promise<UserInfo> {
    const response = await api.post('/auth/register', { username, password, email, fullName })
    return response.data
  },

  async logout(): Promise<void> {
    await api.post('/auth/logout')
  },

  async getCurrentUser(): Promise<UserInfo> {
    const response = await api.get('/auth/me')
    return response.data
  }
}
