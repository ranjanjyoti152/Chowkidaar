import axios from 'axios'
import { useAuthStore } from '../store/authStore'

// Backend server URL from .env
export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '/api/v1'
export const WS_BASE_URL = import.meta.env.VITE_WS_BASE_URL || 'ws://localhost:8001/ws'

console.log('🔗 API Base URL:', API_BASE_URL)

// Edge device configuration
export const DEVICE_ID = import.meta.env.VITE_DEVICE_ID || localStorage.getItem('device_id') || generateDeviceId()
export const DEVICE_NAME = import.meta.env.VITE_DEVICE_NAME || 'Edge Device'
export const REFRESH_INTERVAL = Number(import.meta.env.VITE_REFRESH_INTERVAL) || 5000
export const ENABLE_ANIMATIONS = import.meta.env.VITE_ENABLE_ANIMATIONS !== 'false'

function generateDeviceId(): string {
  const id = `edge-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`
  localStorage.setItem('device_id', id)
  return id
}

export const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
    'X-Device-ID': DEVICE_ID,
    'X-Device-Name': DEVICE_NAME,
  },
})

// Request interceptor to add auth token
api.interceptors.request.use(
  (config) => {
    const token = useAuthStore.getState().token
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  (error) => Promise.reject(error)
)

// Response interceptor to handle auth errors
api.interceptors.response.use(
  (response) => response,
  async (error) => {
    if (error.response?.status === 401) {
      const authStore = useAuthStore.getState()
      
      // Try to refresh token
      if (authStore.refreshToken) {
        try {
          const response = await axios.post(`${API_BASE_URL}/auth/refresh`, {
            refresh_token: authStore.refreshToken,
          })
          
          const { access_token, refresh_token } = response.data
          authStore.setTokens(access_token, refresh_token)
          
          // Retry the original request
          error.config.headers.Authorization = `Bearer ${access_token}`
          return api.request(error.config)
        } catch {
          authStore.logout()
        }
      } else {
        authStore.logout()
      }
    }
    
    return Promise.reject(error)
  }
)

export default api
