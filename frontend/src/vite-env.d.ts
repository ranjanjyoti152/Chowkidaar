/// <reference types="vite/client" />

interface ImportMetaEnv {
  // Backend Server Configuration
  readonly VITE_API_BASE_URL: string
  readonly VITE_WS_BASE_URL: string
  
  // Edge Device Configuration
  readonly VITE_DEVICE_ID: string
  readonly VITE_DEVICE_NAME: string
  
  // UI Configuration
  readonly VITE_REFRESH_INTERVAL: string
  readonly VITE_ENABLE_ANIMATIONS: string
  
  // Debug
  readonly VITE_DEBUG: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
