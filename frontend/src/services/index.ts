import api from './api'
import type {
  LoginRequest,
  Token,
  RegisterRequest,
  User,
  UserWithStats,
  Camera,
  CameraWithStats,
  CameraCreate,
  CameraTestResult,
  Event,
  EventWithCamera,
  EventStats,
  ChatRequest,
  ChatResponse,
  ChatSession,
  SystemStats,
  SystemHealth,
} from '../types'

// Auth API
export const authApi = {
  login: async (data: LoginRequest): Promise<Token> => {
    const formData = new FormData()
    formData.append('username', data.username)
    formData.append('password', data.password)
    const response = await api.post('/auth/login', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    return response.data
  },
  
  register: async (data: RegisterRequest): Promise<User> => {
    const response = await api.post('/auth/register', data)
    return response.data
  },
  
  refresh: async (refreshToken: string): Promise<Token> => {
    const response = await api.post('/auth/refresh', { refresh_token: refreshToken })
    return response.data
  },
  
  logout: async (): Promise<void> => {
    await api.post('/auth/logout')
  },
}

// User API
export const userApi = {
  getCurrentUser: async (): Promise<User> => {
    const response = await api.get('/users/me')
    return response.data
  },
  
  updateCurrentUser: async (data: Partial<User>): Promise<User> => {
    const response = await api.put('/users/me', data)
    return response.data
  },
  
  changePassword: async (currentPassword: string, newPassword: string): Promise<void> => {
    await api.put('/users/me/password', {
      current_password: currentPassword,
      new_password: newPassword,
    })
  },
  
  listUsers: async (): Promise<UserWithStats[]> => {
    const response = await api.get('/users')
    return response.data
  },
  
  createUser: async (data: RegisterRequest & { role: string }): Promise<User> => {
    const response = await api.post('/users', data)
    return response.data
  },
  
  updateUser: async (userId: number, data: Partial<User>): Promise<User> => {
    const response = await api.put(`/users/${userId}`, data)
    return response.data
  },
  
  deleteUser: async (userId: number): Promise<void> => {
    await api.delete(`/users/${userId}`)
  },
}

// Camera API
export const cameraApi = {
  listCameras: async (): Promise<CameraWithStats[]> => {
    const response = await api.get('/cameras')
    return response.data
  },
  
  getCamera: async (id: number): Promise<CameraWithStats> => {
    const response = await api.get(`/cameras/${id}`)
    return response.data
  },
  
  createCamera: async (data: CameraCreate): Promise<Camera> => {
    const response = await api.post('/cameras', data)
    return response.data
  },
  
  updateCamera: async (id: number, data: Partial<CameraCreate>): Promise<Camera> => {
    const response = await api.put(`/cameras/${id}`, data)
    return response.data
  },
  
  deleteCamera: async (id: number): Promise<void> => {
    await api.delete(`/cameras/${id}`)
  },
  
  testCamera: async (id: number): Promise<CameraTestResult> => {
    const response = await api.post(`/cameras/${id}/test`)
    return response.data
  },
  
  startStream: async (id: number): Promise<{ message: string; status: string }> => {
    const response = await api.post(`/cameras/${id}/start`)
    return response.data
  },
  
  stopStream: async (id: number): Promise<{ message: string }> => {
    const response = await api.post(`/cameras/${id}/stop`)
    return response.data
  },
  
  getStreamUrl: (id: number): string => {
    return `${api.defaults.baseURL}/cameras/${id}/stream`
  },
}

// Event API
export const eventApi = {
  listEvents: async (params?: {
    camera_id?: number
    event_type?: string
    severity?: string
    start_date?: string
    end_date?: string
    is_acknowledged?: boolean
    skip?: number
    limit?: number
  }): Promise<EventWithCamera[]> => {
    const response = await api.get('/events', { params })
    return response.data
  },
  
  getEvent: async (id: number): Promise<EventWithCamera> => {
    const response = await api.get(`/events/${id}`)
    return response.data
  },
  
  updateEvent: async (id: number, data: { is_acknowledged?: boolean; notes?: string }): Promise<Event> => {
    const response = await api.put(`/events/${id}`, data)
    return response.data
  },
  
  deleteEvent: async (id: number): Promise<void> => {
    await api.delete(`/events/${id}`)
  },
  
  getStats: async (): Promise<EventStats> => {
    const response = await api.get('/events/stats')
    return response.data
  },
  
  acknowledgeAll: async (cameraId?: number): Promise<{ message: string }> => {
    const response = await api.post('/events/acknowledge-all', null, {
      params: cameraId ? { camera_id: cameraId } : {},
    })
    return response.data
  },
  
  regenerateSummary: async (id: number): Promise<Event> => {
    const response = await api.post(`/events/${id}/regenerate-summary`)
    return response.data
  },
  
  getFrameUrl: (id: number): string => {
    return `${api.defaults.baseURL}/events/${id}/frame`
  },
  
  getThumbnailUrl: (id: number): string => {
    return `${api.defaults.baseURL}/events/${id}/thumbnail`
  },
}

// Assistant API
export const assistantApi = {
  chat: async (data: ChatRequest): Promise<ChatResponse> => {
    const response = await api.post('/assistant/chat', data)
    return response.data
  },
  
  listSessions: async (): Promise<ChatSession[]> => {
    const response = await api.get('/assistant/sessions')
    return response.data
  },
  
  getSession: async (id: number): Promise<ChatSession> => {
    const response = await api.get(`/assistant/sessions/${id}`)
    return response.data
  },
  
  deleteSession: async (id: number): Promise<void> => {
    await api.delete(`/assistant/sessions/${id}`)
  },
  
  getSuggestions: async (): Promise<{ suggestions: string[] }> => {
    const response = await api.get('/assistant/suggestions')
    return response.data
  },
}

// System API
export const systemApi = {
  getStats: async (): Promise<SystemStats> => {
    const response = await api.get('/system/stats')
    return response.data
  },
  
  getHealth: async (): Promise<SystemHealth> => {
    const response = await api.get('/system/health')
    return response.data
  },
  
  getActiveStreams: async (): Promise<{ active_count: number; streams: unknown[] }> => {
    const response = await api.get('/system/streams')
    return response.data
  },
  
  getModels: async (): Promise<{ models: string[] }> => {
    const response = await api.get('/system/models')
    return response.data
  },
  
  testOllamaConnection: async (url?: string): Promise<{ status: string; url: string; models: string[]; model_count?: number; error?: string }> => {
    const response = await api.post('/system/ollama/test', null, { params: url ? { url } : {} })
    return response.data
  },
  
  restartDetector: async (): Promise<{ message: string }> => {
    const response = await api.post('/system/restart-detector')
    return response.data
  },
  
  clearStreams: async (): Promise<{ message: string }> => {
    const response = await api.post('/system/clear-streams')
    return response.data
  },
  
  // YOLO Model Management
  getYoloModels: async (): Promise<{ models: Array<{ name: string; display_name: string; type: string; size: string; path?: string }> }> => {
    const response = await api.get('/system/yolo-models')
    return response.data
  },
  
  uploadYoloModel: async (formData: FormData): Promise<{ message: string; model: unknown }> => {
    const response = await api.post('/system/yolo-models/upload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    })
    return response.data
  },
  
  deleteYoloModel: async (modelName: string): Promise<{ message: string }> => {
    const response = await api.delete(`/system/yolo-models/${modelName}`)
    return response.data
  },
  
  getModelClasses: async (modelName: string): Promise<{ model: string; classes: string[]; class_count: number }> => {
    const response = await api.get(`/system/yolo-models/${modelName}/classes`)
    return response.data
  },
  
  activateYoloModel: async (modelName: string): Promise<{ message: string; model: string }> => {
    const response = await api.post(`/system/yolo-models/${modelName}/activate`)
    return response.data
  },
}

// Settings API
export interface TelegramSettings {
  enabled: boolean
  bot_token?: string
  chat_id?: string
  send_photo: boolean
  send_summary: boolean
  send_details: boolean
}

export interface EmailSettings {
  enabled: boolean
  smtp_host?: string
  smtp_port: number
  smtp_user?: string
  smtp_password?: string
  from_address?: string
  recipients: string[]
  send_photo: boolean
  send_summary: boolean
  send_details: boolean
}

export interface SettingsData {
  detection: {
    model: string
    confidence_threshold: number
    enabled_classes: string[]
    inference_device: string
  }
  vlm: {
    model: string
    ollama_url: string
    auto_summarize: boolean
    summarize_delay_seconds: number
  }
  storage: {
    recordings_path: string
    snapshots_path: string
    max_storage_gb: number
    retention_days: number
  }
  notifications: {
    enabled: boolean
    min_severity: string
    event_types: string[]
    telegram: TelegramSettings
    email: EmailSettings
  }
  updated_at?: string
}

export const settingsApi = {
  get: async (): Promise<SettingsData> => {
    const response = await api.get('/settings')
    return response.data
  },
  
  update: async (data: Partial<SettingsData>): Promise<SettingsData> => {
    const response = await api.put('/settings', data)
    return response.data
  },
}
