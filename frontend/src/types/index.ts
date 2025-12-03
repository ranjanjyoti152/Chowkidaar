// API Types for Chowkidaar NVR

// Auth Types
export interface LoginRequest {
  username: string
  password: string
}

export interface Token {
  access_token: string
  refresh_token: string
  token_type: string
}

export interface RegisterRequest {
  email: string
  username: string
  password: string
  full_name?: string
}

// User Types
export type UserRole = 'admin' | 'operator' | 'viewer'

export interface User {
  id: number
  email: string
  username: string
  full_name?: string
  role: UserRole
  is_active: boolean
  is_superuser: boolean
  created_at: string
  last_login?: string
}

export interface UserWithStats extends User {
  cameras_count: number
  events_count: number
}

// Camera Types
export type CameraStatus = 'online' | 'offline' | 'connecting' | 'error' | 'disabled'
export type CameraType = 'rtsp' | 'http' | 'onvif'

export interface Camera {
  id: number
  name: string
  description?: string
  stream_url: string
  camera_type: CameraType
  location?: string
  status: CameraStatus
  is_enabled: boolean
  detection_enabled: boolean
  recording_enabled: boolean
  fps: number
  resolution_width?: number
  resolution_height?: number
  last_seen?: string
  error_message?: string
  owner_id: number
  created_at: string
  updated_at: string
}

export interface CameraWithStats extends Camera {
  events_today: number
  events_total: number
  uptime_percentage: number
}

export interface CameraCreate {
  name: string
  description?: string
  stream_url: string
  camera_type?: CameraType
  location?: string
  username?: string
  password?: string
  is_enabled?: boolean
  detection_enabled?: boolean
  recording_enabled?: boolean
  fps?: number
}

export interface CameraTestResult {
  success: boolean
  message: string
  resolution?: string
  fps?: number
}

// Event Types
export type EventType = 
  | 'person_detected'
  | 'vehicle_detected'
  | 'fire_detected'
  | 'smoke_detected'
  | 'animal_detected'
  | 'motion_detected'
  | 'intrusion'
  | 'loitering'
  | 'custom'

export type EventSeverity = 'low' | 'medium' | 'high' | 'critical'

export interface DetectedObject {
  class_name: string
  confidence: number
  bbox: number[]
}

export interface Event {
  id: number
  event_type: EventType
  severity: EventSeverity
  camera_id: number
  detected_objects: {
    objects: DetectedObject[]
    count: number
  }
  confidence_score: number
  frame_path?: string
  thumbnail_path?: string
  detection_metadata: Record<string, unknown>
  summary?: string
  summary_generated_at?: string
  timestamp: string
  duration_seconds?: number
  is_acknowledged: boolean
  acknowledged_at?: string
  notes?: string
  user_id: number
  created_at: string
}

export interface EventWithCamera extends Event {
  camera_name: string
  camera_location?: string
}

export interface EventStats {
  total_events: number
  events_by_type: Record<string, number>
  events_by_severity: Record<string, number>
  events_by_camera: Record<string, number>
  events_today: number
  events_this_week: number
  events_this_month: number
}

// Chat/Assistant Types
export interface ChatMessage {
  id: number
  session_id?: number
  role: 'user' | 'assistant' | 'system'
  content: string
  event_id?: number
  metadata?: Record<string, unknown>
  created_at: string
}

export interface ChatSession {
  id: number
  title?: string
  user_id: number
  context: Record<string, unknown>
  created_at: string
  updated_at: string
  messages: ChatMessage[]
}

export interface ChatRequest {
  message: string
  session_id?: number
  include_events_context?: boolean
  event_ids?: number[]
}

export interface ChatResponse {
  response: string
  session_id: number
  related_events?: number[]
  metadata?: Record<string, unknown>
}

// System Types
export interface CPUStats {
  usage_percent: number
  cores: number
  frequency_mhz: number
  temperature?: number
}

export interface MemoryStats {
  total_gb: number
  used_gb: number
  available_gb: number
  usage_percent: number
}

export interface DiskStats {
  total_gb: number
  used_gb: number
  free_gb: number
  usage_percent: number
  mount_point: string
}

export interface GPUStats {
  id: number
  name: string
  memory_total_mb: number
  memory_used_mb: number
  memory_free_mb: number
  usage_percent: number
  temperature?: number
}

export interface NetworkStats {
  bytes_sent: number
  bytes_recv: number
  packets_sent: number
  packets_recv: number
}

export interface InferenceStats {
  model_name: string
  inference_count: number
  average_inference_time_ms: number
  last_inference_time_ms: number
  fps: number
}

export interface SystemStats {
  cpu: CPUStats
  memory: MemoryStats
  disks: DiskStats[]
  gpus: GPUStats[]
  network: NetworkStats
  inference?: InferenceStats
  active_streams: number
  total_cameras: number
  timestamp: string
}

export interface SystemHealth {
  status: 'healthy' | 'warning' | 'critical'
  cpu_status: string
  memory_status: string
  gpu_status: string
  disk_status: string
  ollama_status: string
  database_status: string
  issues: string[]
}
