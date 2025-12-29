import { useState, useEffect, useRef } from 'react'
import { useQuery, useMutation } from '@tanstack/react-query'
import { motion } from 'framer-motion'
import {
  CogIcon,
  BellIcon,
  ServerStackIcon,
  ShieldCheckIcon,
  FolderIcon,
  CpuChipIcon,
  ArrowPathIcon,
  CheckCircleIcon,
  ExclamationCircleIcon,
  SparklesIcon,
  CloudArrowUpIcon,
  TrashIcon,
  PlayIcon,
  PaperAirplaneIcon,
  EnvelopeIcon,
} from '@heroicons/react/24/outline'
import toast from 'react-hot-toast'
import { systemApi, settingsApi, SettingsData } from '../services'

interface YoloModel {
  name: string
  display_name: string
  type: string
  size: string
  path?: string
  category?: string  // 'yolo' or 'owlv2'
  description?: string
}

type Settings = SettingsData

// Event types for notification filtering
const eventTypes = [
  { id: 'all', label: 'All Events', color: 'primary' },
  { id: 'intrusion', label: 'Intrusion', color: 'red' },
  { id: 'theft_attempt', label: 'Theft Attempt', color: 'red' },
  { id: 'suspicious', label: 'Suspicious Activity', color: 'orange' },
  { id: 'fire_detected', label: 'Fire Detected', color: 'red' },
  { id: 'smoke_detected', label: 'Smoke Detected', color: 'orange' },
  { id: 'delivery', label: 'Delivery', color: 'green' },
  { id: 'visitor', label: 'Visitor', color: 'green' },
  { id: 'package_left', label: 'Package Left', color: 'cyan' },
  { id: 'loitering', label: 'Loitering', color: 'yellow' },
  { id: 'person_detected', label: 'Person Detected', color: 'blue' },
  { id: 'vehicle_detected', label: 'Vehicle Detected', color: 'blue' },
  { id: 'animal_detected', label: 'Animal Detected', color: 'purple' },
]

const defaultSettings: Settings = {
  detection: {
    model: 'yolov8n',
    confidence_threshold: 0.5,
    enabled_classes: ['person', 'car', 'truck', 'dog', 'cat'],
    inference_device: 'cuda',
    owlv2_queries: ['a person', 'a car', 'a fire', 'a lighter', 'a dog', 'a cat', 'a weapon', 'a knife', 'a suspicious object'],
  },
  vlm: {
    provider: 'ollama',
    model: 'llava',
    ollama_url: 'http://localhost:11434',
    openai_api_key: '',
    openai_model: 'gpt-4o',
    openai_base_url: '',
    gemini_api_key: '',
    gemini_model: 'gemini-2.0-flash-exp',
    auto_summarize: true,
    summarize_delay_seconds: 5,
    safety_scan_enabled: true,
    safety_scan_interval: 30,
  },
  storage: {
    recordings_path: '/data/recordings',
    snapshots_path: '/data/snapshots',
    max_storage_gb: 500,
    retention_days: 30,
  },
  notifications: {
    enabled: true,
    min_severity: 'high',
    event_types: ['all'],
    telegram: {
      enabled: false,
      bot_token: '',
      chat_id: '',
      send_photo: true,
      send_summary: true,
      send_details: true,
    },
    email: {
      enabled: false,
      smtp_host: '',
      smtp_port: 587,
      smtp_user: '',
      smtp_password: '',
      from_address: '',
      recipients: [],
      send_photo: true,
      send_summary: true,
      send_details: true,
    },
  },
}

const detectionClasses = [
  'person', 'bicycle', 'car', 'motorcycle', 'airplane', 'bus', 'train', 'truck',
  'boat', 'traffic light', 'fire hydrant', 'stop sign', 'parking meter', 'bench',
  'bird', 'cat', 'dog', 'horse', 'sheep', 'cow', 'elephant', 'bear', 'zebra',
  'giraffe', 'backpack', 'umbrella', 'handbag', 'tie', 'suitcase', 'frisbee',
]

export default function Settings() {
  const [activeTab, setActiveTab] = useState('detection')
  const [settings, setSettings] = useState<Settings>(defaultSettings)
  const [ollamaModels, setOllamaModels] = useState<string[]>([])
  const [ollamaStatus, setOllamaStatus] = useState<'checking' | 'online' | 'offline'>('checking')
  const [isLoadingModels, setIsLoadingModels] = useState(false)
  const [yoloModels, setYoloModels] = useState<YoloModel[]>([])
  const [modelClasses, setModelClasses] = useState<string[]>(detectionClasses)
  const [isLoadingClasses, setIsLoadingClasses] = useState(false)
  const [isUploading, setIsUploading] = useState(false)
  const [activeYoloModel, setActiveYoloModel] = useState<string>('')
  const [settingsLoaded, setSettingsLoaded] = useState(false)  // Track if settings loaded from API
  const fileInputRef = useRef<HTMLInputElement>(null)
  const [newOwlQuery, setNewOwlQuery] = useState('')  // For adding new OWLv2 queries

  // Derive detector type from settings model (not separate state)
  const detectorType = settings.detection.model.startsWith('owlv2') ? 'owlv2' : 'yolo'

  // Provider-specific states
  const [openaiModels, setOpenaiModels] = useState<string[]>([])
  const [openaiStatus, setOpenaiStatus] = useState<'checking' | 'online' | 'offline' | 'idle'>('idle')
  const [geminiModels, setGeminiModels] = useState<string[]>([])
  const [geminiStatus, setGeminiStatus] = useState<'checking' | 'online' | 'offline' | 'idle'>('idle')
  const [isTestingProvider, setIsTestingProvider] = useState(false)

  // Ollama model download state
  const [newOllamaModel, setNewOllamaModel] = useState('')
  const [isPullingModel, setIsPullingModel] = useState(false)
  const [pullProgress, setPullProgress] = useState<{ percent: number; status: string }>({ percent: 0, status: '' })

  // Available models for each provider
  const openaiModelOptions = [
    'gpt-4o',
    'gpt-4o-mini',
    'gpt-4-turbo',
    'gpt-4',
    'gpt-3.5-turbo',
    'o1-preview',
    'o1-mini',
  ]

  const geminiModelOptions = [
    'gemini-2.0-flash-exp',
    'gemini-1.5-flash',
    'gemini-1.5-flash-8b',
    'gemini-1.5-pro',
    'gemini-1.0-pro-vision',
  ]

  // Fetch Ollama models via backend API (avoids CORS issues)
  const fetchOllamaModels = async (url: string) => {
    setIsLoadingModels(true)
    setOllamaStatus('checking')
    try {
      const response = await systemApi.testOllamaConnection(url)
      if (response.status === 'online') {
        setOllamaModels(response.models || [])
        setOllamaStatus('online')
        if (response.models.length > 0 && !response.models.includes(settings.vlm.model)) {
          setSettings(prev => ({
            ...prev,
            vlm: { ...prev.vlm, model: response.models[0] }
          }))
        }
      } else {
        setOllamaStatus('offline')
        setOllamaModels([])
      }
    } catch {
      setOllamaStatus('offline')
      setOllamaModels([])
    }
    setIsLoadingModels(false)
  }

  // Test OpenAI connection
  const testOpenAIConnection = async (apiKey: string, baseUrl?: string) => {
    if (!apiKey) {
      toast.error('Please enter an OpenAI API key')
      return
    }
    setIsTestingProvider(true)
    setOpenaiStatus('checking')
    try {
      const response = await systemApi.testLLMProvider({
        provider: 'openai',
        api_key: apiKey,
        url: baseUrl || undefined,
      })
      if (response.status === 'online') {
        setOpenaiModels(response.models || openaiModelOptions)
        setOpenaiStatus('online')
        toast.success(`OpenAI connected (${response.models?.length || 0} models available)`)
      } else {
        setOpenaiStatus('offline')
        setOpenaiModels([])
        toast.error(response.error || 'Failed to connect to OpenAI')
      }
    } catch (error) {
      setOpenaiStatus('offline')
      setOpenaiModels([])
      toast.error('Failed to test OpenAI connection')
    }
    setIsTestingProvider(false)
  }

  // Test Gemini connection
  const testGeminiConnection = async (apiKey: string) => {
    if (!apiKey) {
      toast.error('Please enter a Gemini API key')
      return
    }
    setIsTestingProvider(true)
    setGeminiStatus('checking')
    try {
      const response = await systemApi.testLLMProvider({
        provider: 'gemini',
        api_key: apiKey,
      })
      if (response.status === 'online') {
        setGeminiModels(response.models || geminiModelOptions)
        setGeminiStatus('online')
        toast.success(`Gemini connected (${response.models?.length || 0} models available)`)
      } else {
        setGeminiStatus('offline')
        setGeminiModels([])
        toast.error(response.error || 'Failed to connect to Gemini')
      }
    } catch (error) {
      setGeminiStatus('offline')
      setGeminiModels([])
      toast.error('Failed to test Gemini connection')
    }
    setIsTestingProvider(false)
  }

  const { isLoading } = useQuery({
    queryKey: ['settings'],
    queryFn: async () => {
      try {
        const data = await settingsApi.get()
        // Merge received data with defaults to ensure all fields exist
        const mergedSettings: Settings = {
          detection: {
            ...defaultSettings.detection,
            ...data.detection,
          },
          vlm: {
            ...defaultSettings.vlm,
            ...data.vlm,
          },
          storage: {
            ...defaultSettings.storage,
            ...data.storage,
          },
          notifications: {
            ...defaultSettings.notifications,
            ...data.notifications,
            telegram: {
              ...defaultSettings.notifications.telegram,
              ...data.notifications?.telegram,
            },
            email: {
              ...defaultSettings.notifications.email,
              ...data.notifications?.email,
            },
          },
        }
        setSettings(mergedSettings)
        // Set active model from loaded settings
        if (mergedSettings.detection?.model) {
          setActiveYoloModel(mergedSettings.detection.model)
          // detectorType is now derived from settings.detection.model automatically
        }
        // Fetch classes for the saved model
        if (mergedSettings.detection?.model) {
          fetchModelClasses(mergedSettings.detection.model)
        }
        // Fetch Ollama models with saved URL
        if (mergedSettings.vlm?.ollama_url) {
          fetchOllamaModels(mergedSettings.vlm.ollama_url)
        }
        setSettingsLoaded(true)  // Mark settings as loaded from API
        return mergedSettings
      } catch {
        // Only use defaults if fetch fails
        fetchOllamaModels(defaultSettings.vlm.ollama_url)
        return defaultSettings
      }
    },
  })

  const saveMutation = useMutation({
    mutationFn: async (newSettings: Settings) => {
      console.log('📤 Saving settings:', JSON.stringify(newSettings, null, 2))
      const result = await settingsApi.update(newSettings)
      console.log('📥 Response:', JSON.stringify(result, null, 2))
      return result
    },
    onSuccess: (data) => {
      console.log('✅ Save successful, updating state')
      // Merge response with defaults to ensure all fields exist
      const mergedSettings: Settings = {
        detection: {
          ...defaultSettings.detection,
          ...data.detection,
        },
        vlm: {
          ...defaultSettings.vlm,
          ...data.vlm,
        },
        storage: {
          ...defaultSettings.storage,
          ...data.storage,
        },
        notifications: {
          ...defaultSettings.notifications,
          ...data.notifications,
          telegram: {
            ...defaultSettings.notifications.telegram,
            ...data.notifications?.telegram,
          },
          email: {
            ...defaultSettings.notifications.email,
            ...data.notifications?.email,
          },
        },
      }
      setSettings(mergedSettings)
      toast.success('Settings saved successfully')
    },
    onError: (error) => {
      console.error('❌ Save failed:', error)
      toast.error('Failed to save settings')
    },
  })

  const tabs = [
    { id: 'detection', name: 'Detection', icon: CpuChipIcon },
    { id: 'vlm', name: 'Vision LLM', icon: ServerStackIcon },
    { id: 'storage', name: 'Storage', icon: FolderIcon },
    { id: 'notifications', name: 'Notifications', icon: BellIcon },
    { id: 'security', name: 'Security', icon: ShieldCheckIcon },
  ]

  const handleSave = () => {
    saveMutation.mutate(settings)
  }

  const handleOllamaUrlChange = (url: string) => {
    setSettings(prev => ({
      ...prev,
      vlm: { ...prev.vlm, ollama_url: url }
    }))
  }

  const handleTestConnection = () => {
    fetchOllamaModels(settings.vlm.ollama_url)
  }

  // Pull/download an Ollama model with streaming progress
  const pullOllamaModel = async (modelName: string) => {
    if (!modelName.trim()) {
      toast.error('Please enter a model name')
      return
    }

    setIsPullingModel(true)
    setPullProgress({ percent: 0, status: 'Starting download...' })

    try {
      // Get auth token for SSE request
      const token = localStorage.getItem('access_token')
      const streamUrl = systemApi.getOllamaPullStreamUrl(modelName.trim(), settings.vlm.ollama_url)

      // Create EventSource for SSE with auth
      const response = await fetch(streamUrl, {
        method: 'GET',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Accept': 'text/event-stream'
        }
      })

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`)
      }

      const reader = response.body?.getReader()
      if (!reader) {
        throw new Error('No response body')
      }

      const decoder = new TextDecoder()
      let buffer = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() || ''

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const data = JSON.parse(line.slice(6))

              if (data.status === 'complete') {
                toast.success(`Model ${modelName} downloaded successfully!`)
                setNewOllamaModel('')
                setPullProgress({ percent: 100, status: 'Complete!' })

                if (data.models) {
                  setOllamaModels(data.models)
                } else {
                  fetchOllamaModels(settings.vlm.ollama_url)
                }

                // Auto-select the new model
                setSettings(prev => ({
                  ...prev,
                  vlm: { ...prev.vlm, model: modelName.trim() }
                }))
                setIsPullingModel(false)
                return

              } else if (data.status === 'error') {
                toast.error(data.message || 'Download failed')
                setIsPullingModel(false)
                return

              } else {
                // Update progress
                const status = data.status || 'Downloading...'
                const displayStatus = status.length > 30 ? status.slice(0, 30) + '...' : status
                setPullProgress({
                  percent: data.percent || 0,
                  status: `${displayStatus} ${data.percent ? `(${data.percent}%)` : ''}`
                })
              }
            } catch {
              // Ignore JSON parse errors
            }
          }
        }
      }

      // If we get here without completion, refresh models anyway
      fetchOllamaModels(settings.vlm.ollama_url)

    } catch (error) {
      console.error('Failed to pull model:', error)
      toast.error('Failed to download model. Check Ollama connection.')
    }

    setIsPullingModel(false)
    setPullProgress({ percent: 0, status: '' })
  }

  // Fetch YOLO models
  const fetchYoloModels = async () => {
    try {
      const response = await systemApi.getYoloModels()
      setYoloModels(response.models || [])
    } catch (error) {
      console.error('Failed to fetch YOLO models:', error)
    }
  }

  // Fetch model classes
  const fetchModelClasses = async (modelName: string) => {
    setIsLoadingClasses(true)
    try {
      const response = await systemApi.getModelClasses(modelName)
      setModelClasses(response.classes || detectionClasses)
      // Update enabled classes to only include valid ones
      setSettings(prev => ({
        ...prev,
        detection: {
          ...prev.detection,
          enabled_classes: prev.detection.enabled_classes.filter(c =>
            response.classes?.includes(c)
          )
        }
      }))
    } catch (error) {
      console.error('Failed to fetch model classes:', error)
      setModelClasses(detectionClasses)
    }
    setIsLoadingClasses(false)
  }

  // Upload custom model
  const handleModelUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]
    if (!file) return

    if (!file.name.endsWith('.pt')) {
      toast.error('Only .pt files are allowed')
      return
    }

    setIsUploading(true)
    try {
      const formData = new FormData()
      formData.append('file', file)
      formData.append('name', file.name.replace('.pt', ''))

      await systemApi.uploadYoloModel(formData)
      toast.success('Model uploaded successfully')
      fetchYoloModels()
    } catch (error) {
      toast.error('Failed to upload model')
    }
    setIsUploading(false)
    if (fileInputRef.current) fileInputRef.current.value = ''
  }

  // Delete custom model
  const handleDeleteModel = async (modelName: string) => {
    if (!confirm(`Delete model "${modelName}"?`)) return

    try {
      await systemApi.deleteYoloModel(modelName)
      toast.success('Model deleted')
      fetchYoloModels()
    } catch (error) {
      toast.error('Failed to delete model')
    }
  }

  // Activate model
  const handleActivateModel = async (modelName: string) => {
    try {
      await systemApi.activateYoloModel(modelName)
      setActiveYoloModel(modelName)
      // Update settings and save to database ONLY if settings have been loaded from API
      // This prevents overwriting saved settings with defaults
      if (settingsLoaded) {
        const newSettings = {
          ...settings,
          detection: { ...settings.detection, model: modelName }
        }
        setSettings(newSettings)
        // Auto-save to database after model activation
        saveMutation.mutate(newSettings)
      } else {
        console.warn('Skipping auto-save - settings not loaded from API yet')
        // Just update local state, don't save
        setSettings(prev => ({
          ...prev,
          detection: { ...prev.detection, model: modelName }
        }))
      }
      // Fetch model classes only for YOLO models (not OWLv2)
      if (!modelName.startsWith('owlv2')) {
        fetchModelClasses(modelName)
      }
    } catch (error) {
      toast.error('Failed to activate model')
    }
  }

  // Initial fetch - only fetch YOLO models list, settings will load classes
  useEffect(() => {
    fetchYoloModels()
  }, [])

  if (isLoading) {
    return (
      <div className="page-container">
        <div className="page-header">
          <div className="h-8 w-48 skeleton" />
        </div>
        <div className="h-96 skeleton" />
      </div>
    )
  }

  return (
    <div className="page-container">
      {/* Header */}
      <div className="page-header">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-primary-500/30 flex items-center justify-center">
            <CogIcon className="w-5 h-5 text-primary-300" />
          </div>
          <div>
            <h1 className="page-title">Settings</h1>
            <p className="text-gray-300 mt-1">Configure Chowkidaar NVR</p>
          </div>
        </div>
        <button
          onClick={handleSave}
          disabled={saveMutation.isPending}
          className="btn-primary"
        >
          {saveMutation.isPending ? 'Saving...' : 'Save Changes'}
        </button>
      </div>

      <div className="flex gap-6">
        {/* Tabs */}
        <div className="w-48 flex-shrink-0">
          <nav className="space-y-1">
            {tabs.map((tab) => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`w-full flex items-center gap-3 px-4 py-3 rounded-xl text-left transition-all ${activeTab === tab.id
                  ? 'bg-primary-500/30 text-primary-300'
                  : 'text-gray-300 hover:text-white hover:bg-white/10'
                  }`}
              >
                <tab.icon className="w-5 h-5" />
                <span className="font-medium">{tab.name}</span>
              </button>
            ))}
          </nav>
        </div>

        {/* Content */}
        <div className="flex-1">
          <motion.div
            key={activeTab}
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            className="glass-card p-6"
          >
            {activeTab === 'detection' && (
              <div className="space-y-6">
                <div className="flex items-center justify-between">
                  <h2 className="text-lg font-semibold text-white flex items-center gap-2">
                    <CpuChipIcon className="w-5 h-5 text-primary-400" />
                    Detection Settings
                  </h2>
                  <span className="text-sm text-gray-400">
                    Active: <span className="text-primary-400 font-medium">{activeYoloModel}</span>
                  </span>
                </div>

                {/* Detector Type Toggle - YOLO vs OWLv2 */}
                <div className="p-4 rounded-xl bg-gradient-to-r from-blue-500/10 to-purple-500/10 border border-blue-500/20">
                  <label className="text-sm font-medium text-gray-300 mb-3 block">
                    Detection Engine
                  </label>
                  <div className="grid grid-cols-2 gap-3">
                    <button
                      onClick={() => {
                        // Auto-select first YOLO model - activate and save
                        const firstYolo = yoloModels.find(m => m.category !== 'owlv2')
                        if (firstYolo) {
                          handleActivateModel(firstYolo.name)
                        }
                      }}
                      className={`p-4 rounded-xl border transition-all ${detectorType === 'yolo'
                        ? 'bg-blue-500/20 border-blue-500/50 text-blue-300'
                        : 'bg-white/5 border-white/10 text-gray-400 hover:border-white/20'
                        }`}
                    >
                      <div className="font-semibold mb-1">🎯 YOLO</div>
                      <div className="text-xs opacity-70">Fast fixed-class detection (80 classes)</div>
                    </button>
                    <button
                      onClick={() => {
                        // Auto-select first OWLv2 model - activate and save
                        const firstOwl = yoloModels.find(m => m.category === 'owlv2')
                        if (firstOwl) {
                          handleActivateModel(firstOwl.name)
                        }
                      }}
                      className={`p-4 rounded-xl border transition-all ${detectorType === 'owlv2'
                        ? 'bg-purple-500/20 border-purple-500/50 text-purple-300'
                        : 'bg-white/5 border-white/10 text-gray-400 hover:border-white/20'
                        }`}
                    >
                      <div className="font-semibold mb-1">🦉 OWLv2</div>
                      <div className="text-xs opacity-70">Open-vocabulary - detect anything by text</div>
                    </button>
                  </div>
                </div>

                {/* Model Selection */}
                <div className="p-4 rounded-xl bg-gradient-to-r from-primary-500/10 to-cyan-500/10 border border-primary-500/20">
                  <div className="flex items-center justify-between mb-4">
                    <label className="text-sm font-medium text-gray-300">
                      {detectorType === 'yolo' ? 'YOLO Models' : 'OWLv2 Models'}
                    </label>
                    {detectorType === 'yolo' && (
                      <div className="flex items-center gap-2">
                        <input
                          type="file"
                          ref={fileInputRef}
                          onChange={handleModelUpload}
                          accept=".pt"
                          className="hidden"
                        />
                        <button
                          onClick={() => fileInputRef.current?.click()}
                          disabled={isUploading}
                          className="btn-secondary text-sm px-3 py-1.5 flex items-center gap-1.5"
                        >
                          {isUploading ? (
                            <ArrowPathIcon className="w-4 h-4 animate-spin" />
                          ) : (
                            <CloudArrowUpIcon className="w-4 h-4" />
                          )}
                          Upload Custom
                        </button>
                      </div>
                    )}
                  </div>

                  <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3">
                    {yoloModels
                      .filter(model => detectorType === 'owlv2' ? model.category === 'owlv2' : model.category !== 'owlv2')
                      .map((model) => (
                        <div
                          key={model.name}
                          className={`relative p-3 rounded-xl transition-all border cursor-pointer group ${settings.detection.model === model.name
                            ? 'bg-primary-500/20 border-primary-500/50'
                            : 'bg-white/5 border-white/10 hover:border-white/20 hover:bg-white/10'
                            }`}
                          onClick={() => {
                            // Activate the model and save to database
                            handleActivateModel(model.name)
                          }}
                        >
                          <div className="flex items-start justify-between">
                            <div className="flex-1 min-w-0">
                              <p className={`font-medium truncate ${settings.detection.model === model.name ? 'text-primary-400' : 'text-gray-200'
                                }`}>
                                {model.display_name || model.name.split('/').pop()?.replace('.pt', '')}
                              </p>
                              <p className="text-xs text-gray-500 mt-0.5">{model.size}</p>
                              {model.description && (
                                <p className="text-xs text-gray-500 mt-1 line-clamp-2">{model.description}</p>
                              )}
                            </div>
                            {model.type === 'custom' && (
                              <button
                                onClick={(e) => {
                                  e.stopPropagation()
                                  handleDeleteModel(model.name)
                                }}
                                className="opacity-0 group-hover:opacity-100 p-1 rounded text-red-400 hover:bg-red-500/20 transition-all"
                              >
                                <TrashIcon className="w-4 h-4" />
                              </button>
                            )}
                          </div>
                          <div className="flex items-center gap-2 mt-2">
                            <span className={`text-xs px-2 py-0.5 rounded-full ${model.category === 'owlv2'
                              ? 'bg-purple-500/20 text-purple-400'
                              : model.type === 'builtin'
                                ? 'bg-blue-500/20 text-blue-400'
                                : 'bg-cyan-500/20 text-cyan-400'
                              }`}>
                              {model.category === 'owlv2' ? 'OWLv2' : model.type}
                            </span>
                            {settings.detection.model === model.name && (
                              <button
                                onClick={(e) => {
                                  e.stopPropagation()
                                  handleActivateModel(model.name)
                                }}
                                className="text-xs px-2 py-0.5 rounded-full bg-green-500/20 text-green-400 flex items-center gap-1"
                              >
                                <PlayIcon className="w-3 h-3" />
                                Activate
                              </button>
                            )}
                          </div>
                        </div>
                      ))}
                  </div>
                </div>

                {/* Inference Device */}
                <div className="grid grid-cols-2 gap-6">
                  <div>
                    <label className="block text-sm font-medium text-gray-400 mb-2">
                      Inference Device
                    </label>
                    <select
                      value={settings.detection.inference_device}
                      onChange={(e) =>
                        setSettings({
                          ...settings,
                          detection: { ...settings.detection, inference_device: e.target.value },
                        })
                      }
                      className="input"
                    >
                      <option value="cuda">CUDA (GPU)</option>
                      <option value="cpu">CPU</option>
                      <option value="mps">MPS (Apple Silicon)</option>
                    </select>
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-400 mb-2">
                      Confidence Threshold: {(settings.detection.confidence_threshold * 100).toFixed(0)}%
                    </label>
                    <input
                      type="range"
                      min="0.1"
                      max="1"
                      step="0.05"
                      value={settings.detection.confidence_threshold}
                      onChange={(e) =>
                        setSettings({
                          ...settings,
                          detection: {
                            ...settings.detection,
                            confidence_threshold: parseFloat(e.target.value),
                          },
                        })
                      }
                      className="w-full h-2 bg-white/10 rounded-lg appearance-none cursor-pointer accent-primary-500"
                    />
                  </div>
                </div>

                {/* Detection Classes - Only for YOLO */}
                {detectorType === 'yolo' && (
                  <div>
                    <div className="flex items-center justify-between mb-3">
                      <label className="text-sm font-medium text-gray-400">
                        Detection Classes
                      </label>
                      <div className="flex items-center gap-2">
                        {isLoadingClasses && (
                          <ArrowPathIcon className="w-4 h-4 text-gray-500 animate-spin" />
                        )}
                        <span className="text-xs text-gray-500">
                          {settings.detection.enabled_classes.length}/{modelClasses.length} selected
                        </span>
                        <button
                          onClick={() => setSettings({
                            ...settings,
                            detection: { ...settings.detection, enabled_classes: [...modelClasses] }
                          })}
                          className="text-xs text-primary-400 hover:text-primary-300"
                        >
                          Select All
                        </button>
                        <button
                          onClick={() => setSettings({
                            ...settings,
                            detection: { ...settings.detection, enabled_classes: [] }
                          })}
                          className="text-xs text-gray-400 hover:text-gray-300"
                        >
                          Clear
                        </button>
                      </div>
                    </div>
                    <div className="flex flex-wrap gap-2 max-h-48 overflow-y-auto p-2 bg-white/5 rounded-xl">
                      {modelClasses.map((cls) => (
                        <button
                          key={cls}
                          onClick={() => {
                            const enabled = settings.detection.enabled_classes
                            setSettings({
                              ...settings,
                              detection: {
                                ...settings.detection,
                                enabled_classes: enabled.includes(cls)
                                  ? enabled.filter((c) => c !== cls)
                                  : [...enabled, cls],
                              },
                            })
                          }}
                          className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-all ${settings.detection.enabled_classes.includes(cls)
                            ? 'bg-primary-500/20 text-primary-400 border border-primary-500/30'
                            : 'bg-white/5 text-gray-400 border border-white/10 hover:border-white/20'
                            }`}
                        >
                          {cls}
                        </button>
                      ))}
                    </div>
                  </div>
                )}

                {/* OWLv2 Custom Queries - Only for OWLv2 */}
                {detectorType === 'owlv2' && (
                  <div className="p-4 rounded-xl bg-gradient-to-r from-purple-500/10 to-pink-500/10 border border-purple-500/20">
                    <div className="flex items-center justify-between mb-3">
                      <label className="text-sm font-medium text-gray-300">
                        🦉 OWLv2 Detection Queries
                      </label>
                      <span className="text-xs text-gray-500">
                        {settings.detection.owlv2_queries?.length || 0} queries
                      </span>
                    </div>
                    <p className="text-xs text-gray-400 mb-3">
                      Enter text descriptions of objects you want to detect. OWLv2 can find anything you describe!
                    </p>

                    {/* Add new query */}
                    <div className="flex gap-2 mb-3">
                      <input
                        type="text"
                        value={newOwlQuery}
                        onChange={(e) => setNewOwlQuery(e.target.value)}
                        onKeyDown={(e) => {
                          if (e.key === 'Enter' && newOwlQuery.trim()) {
                            const queries = settings.detection.owlv2_queries || []
                            if (!queries.includes(newOwlQuery.trim())) {
                              setSettings({
                                ...settings,
                                detection: {
                                  ...settings.detection,
                                  owlv2_queries: [...queries, newOwlQuery.trim()]
                                }
                              })
                            }
                            setNewOwlQuery('')
                          }
                        }}
                        placeholder="e.g., 'a person wearing a red shirt', 'a delivery package'"
                        className="input flex-1 text-sm"
                      />
                      <button
                        onClick={() => {
                          if (newOwlQuery.trim()) {
                            const queries = settings.detection.owlv2_queries || []
                            if (!queries.includes(newOwlQuery.trim())) {
                              setSettings({
                                ...settings,
                                detection: {
                                  ...settings.detection,
                                  owlv2_queries: [...queries, newOwlQuery.trim()]
                                }
                              })
                            }
                            setNewOwlQuery('')
                          }
                        }}
                        className="btn-primary text-sm px-4"
                      >
                        Add
                      </button>
                    </div>

                    {/* Query list */}
                    <div className="flex flex-wrap gap-2 max-h-48 overflow-y-auto">
                      {(settings.detection.owlv2_queries || []).map((query, index) => (
                        <div
                          key={index}
                          className="flex items-center gap-1 px-3 py-1.5 rounded-lg bg-purple-500/20 text-purple-300 border border-purple-500/30 text-sm"
                        >
                          <span>{query}</span>
                          <button
                            onClick={() => {
                              const queries = settings.detection.owlv2_queries || []
                              setSettings({
                                ...settings,
                                detection: {
                                  ...settings.detection,
                                  owlv2_queries: queries.filter((_, i) => i !== index)
                                }
                              })
                            }}
                            className="ml-1 text-purple-400 hover:text-red-400 transition-colors"
                          >
                            ×
                          </button>
                        </div>
                      ))}
                    </div>

                    {/* Quick add suggestions */}
                    <div className="mt-3 pt-3 border-t border-white/10">
                      <p className="text-xs text-gray-500 mb-2">Quick add:</p>
                      <div className="flex flex-wrap gap-1">
                        {['a person running', 'a fire or flames', 'a weapon', 'a package', 'a vehicle', 'smoke'].map(suggestion => (
                          <button
                            key={suggestion}
                            onClick={() => {
                              const queries = settings.detection.owlv2_queries || []
                              if (!queries.includes(suggestion)) {
                                setSettings({
                                  ...settings,
                                  detection: {
                                    ...settings.detection,
                                    owlv2_queries: [...queries, suggestion]
                                  }
                                })
                              }
                            }}
                            disabled={(settings.detection.owlv2_queries || []).includes(suggestion)}
                            className="text-xs px-2 py-1 rounded bg-white/5 text-gray-400 hover:bg-white/10 hover:text-gray-300 disabled:opacity-50 disabled:cursor-not-allowed transition-all"
                          >
                            + {suggestion}
                          </button>
                        ))}
                      </div>
                    </div>
                  </div>
                )}
              </div>
            )}

            {activeTab === 'vlm' && (
              <div className="space-y-6">
                <div className="flex items-center justify-between">
                  <h2 className="text-lg font-semibold text-white flex items-center gap-2">
                    <SparklesIcon className="w-5 h-5 text-primary-400" />
                    Vision LLM Settings
                  </h2>
                  <div className="flex items-center gap-2">
                    {settings.vlm.provider === 'ollama' && ollamaStatus === 'checking' && (
                      <span className="flex items-center gap-1.5 text-yellow-400 text-sm">
                        <ArrowPathIcon className="w-4 h-4 animate-spin" />
                        Checking...
                      </span>
                    )}
                    {settings.vlm.provider === 'ollama' && ollamaStatus === 'online' && (
                      <span className="flex items-center gap-1.5 text-green-400 text-sm">
                        <CheckCircleIcon className="w-4 h-4" />
                        Connected ({ollamaModels.length} models)
                      </span>
                    )}
                    {settings.vlm.provider === 'ollama' && ollamaStatus === 'offline' && (
                      <span className="flex items-center gap-1.5 text-red-400 text-sm">
                        <ExclamationCircleIcon className="w-4 h-4" />
                        Offline
                      </span>
                    )}
                    {settings.vlm.provider === 'openai' && openaiStatus === 'online' && (
                      <span className="flex items-center gap-1.5 text-green-400 text-sm">
                        <CheckCircleIcon className="w-4 h-4" />
                        OpenAI Connected
                      </span>
                    )}
                    {settings.vlm.provider === 'gemini' && geminiStatus === 'online' && (
                      <span className="flex items-center gap-1.5 text-green-400 text-sm">
                        <CheckCircleIcon className="w-4 h-4" />
                        Gemini Connected
                      </span>
                    )}
                  </div>
                </div>

                {/* Active Provider Toggle */}
                <div className="p-4 rounded-xl bg-gradient-to-r from-primary-500/10 to-cyan-500/10 border border-primary-500/20">
                  <div className="flex items-center justify-between mb-4">
                    <label className="text-sm font-medium text-gray-300">
                      Active LLM Provider
                    </label>
                    <span className="text-xs text-primary-400 font-medium">
                      Using: {settings.vlm.provider === 'ollama' ? 'Ollama' : settings.vlm.provider === 'openai' ? 'OpenAI' : 'Gemini'}
                    </span>
                  </div>

                  {/* Toggle Buttons */}
                  <div className="flex rounded-xl bg-black/30 p-1">
                    {[
                      { id: 'ollama', name: 'Ollama', icon: '🏠' },
                      { id: 'openai', name: 'OpenAI', icon: '🤖' },
                      { id: 'gemini', name: 'Gemini', icon: '✨' },
                    ].map((provider) => (
                      <button
                        key={provider.id}
                        onClick={() =>
                          setSettings({
                            ...settings,
                            vlm: { ...settings.vlm, provider: provider.id },
                          })
                        }
                        className={`flex-1 py-3 px-4 rounded-lg text-center transition-all font-medium ${settings.vlm.provider === provider.id
                          ? 'bg-primary-500 text-white shadow-lg'
                          : 'text-gray-400 hover:text-white hover:bg-white/10'
                          }`}
                      >
                        <span className="mr-2">{provider.icon}</span>
                        {provider.name}
                      </button>
                    ))}
                  </div>
                </div>

                {/* Ollama Settings */}
                {settings.vlm.provider === 'ollama' && (
                  <>
                    <div className="p-4 rounded-xl bg-white/5 border border-white/10">
                      <label className="block text-sm font-medium text-gray-300 mb-2">
                        Ollama Server URL
                      </label>
                      <div className="flex gap-3">
                        <input
                          type="text"
                          value={settings.vlm.ollama_url}
                          onChange={(e) => handleOllamaUrlChange(e.target.value)}
                          className="input flex-1"
                          placeholder="http://localhost:11434"
                        />
                        <button
                          onClick={handleTestConnection}
                          disabled={isLoadingModels}
                          className="btn-secondary px-4 flex items-center gap-2"
                        >
                          {isLoadingModels ? (
                            <ArrowPathIcon className="w-4 h-4 animate-spin" />
                          ) : (
                            <ArrowPathIcon className="w-4 h-4" />
                          )}
                          Test
                        </button>
                      </div>
                    </div>

                    {/* Ollama Model Selection */}
                    <div>
                      <label className="block text-sm font-medium text-gray-400 mb-2">
                        Select Model
                      </label>
                      {ollamaModels.length > 0 ? (
                        <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
                          {ollamaModels.map((model) => (
                            <button
                              key={model}
                              onClick={() =>
                                setSettings({
                                  ...settings,
                                  vlm: { ...settings.vlm, model: model },
                                })
                              }
                              className={`p-3 rounded-xl text-left transition-all border ${settings.vlm.model === model
                                ? 'bg-primary-500/20 border-primary-500/50 text-primary-400'
                                : 'bg-white/5 border-white/10 text-gray-300 hover:border-white/20 hover:bg-white/10'
                                }`}
                            >
                              <p className="font-medium truncate">{model.split(':')[0]}</p>
                              <p className="text-xs text-gray-500 mt-1">
                                {model.includes(':') ? model.split(':')[1] : 'latest'}
                              </p>
                            </button>
                          ))}
                        </div>
                      ) : (
                        <div className="p-6 rounded-xl bg-white/5 border border-white/10 text-center">
                          {ollamaStatus === 'checking' ? (
                            <div className="flex flex-col items-center gap-2">
                              <ArrowPathIcon className="w-8 h-8 text-gray-500 animate-spin" />
                              <p className="text-gray-400">Loading models...</p>
                            </div>
                          ) : (
                            <div className="flex flex-col items-center gap-2">
                              <ExclamationCircleIcon className="w-8 h-8 text-gray-500" />
                              <p className="text-gray-400">No models found</p>
                              <p className="text-sm text-gray-500">
                                Check if Ollama is running at the specified URL
                              </p>
                            </div>
                          )}
                        </div>
                      )}
                    </div>

                    {/* Download New Model */}
                    {ollamaStatus === 'online' && (
                      <div className="p-4 rounded-xl bg-gradient-to-r from-green-500/10 to-cyan-500/10 border border-green-500/20">
                        <label className="block text-sm font-medium text-gray-300 mb-2">
                          Download New Model
                        </label>
                        <div className="flex gap-3">
                          <input
                            type="text"
                            value={newOllamaModel}
                            onChange={(e) => setNewOllamaModel(e.target.value)}
                            onKeyDown={(e) => {
                              if (e.key === 'Enter' && !isPullingModel) {
                                pullOllamaModel(newOllamaModel)
                              }
                            }}
                            className="input flex-1"
                            placeholder="e.g., llava, gemma3:4b, llama3.2"
                            disabled={isPullingModel}
                          />
                          <button
                            onClick={() => pullOllamaModel(newOllamaModel)}
                            disabled={isPullingModel || !newOllamaModel.trim()}
                            className="btn-primary px-4 flex items-center gap-2"
                          >
                            {isPullingModel ? (
                              <>
                                <ArrowPathIcon className="w-4 h-4 animate-spin" />
                                Downloading...
                              </>
                            ) : (
                              <>
                                <CloudArrowUpIcon className="w-4 h-4" />
                                Download
                              </>
                            )}
                          </button>
                        </div>

                        {/* Progress Bar */}
                        {isPullingModel && (
                          <div className="mt-3">
                            <div className="flex items-center justify-between mb-1">
                              <span className="text-xs text-gray-400">{pullProgress.status}</span>
                              <span className="text-xs text-primary-400 font-medium">{pullProgress.percent}%</span>
                            </div>
                            <div className="w-full h-2 bg-white/10 rounded-full overflow-hidden">
                              <div
                                className="h-full bg-gradient-to-r from-primary-500 to-cyan-500 rounded-full transition-all duration-300 ease-out"
                                style={{ width: `${pullProgress.percent}%` }}
                              />
                            </div>
                          </div>
                        )}

                        <p className="text-xs text-gray-500 mt-2">
                          Enter a model name from <a href="https://ollama.com/library" target="_blank" rel="noopener noreferrer" className="text-primary-400 hover:underline">ollama.com/library</a>.
                          Popular VLM models: llava, llava-llama3, bakllava, gemma3:4b
                        </p>
                      </div>
                    )}
                  </>
                )}

                {/* OpenAI Settings */}
                {settings.vlm.provider === 'openai' && (
                  <>
                    <div className="p-4 rounded-xl bg-white/5 border border-white/10 space-y-4">
                      <div>
                        <label className="block text-sm font-medium text-gray-300 mb-2">
                          OpenAI API Key
                        </label>
                        <div className="flex gap-3">
                          <input
                            type="password"
                            value={settings.vlm.openai_api_key || ''}
                            onChange={(e) =>
                              setSettings({
                                ...settings,
                                vlm: { ...settings.vlm, openai_api_key: e.target.value },
                              })
                            }
                            className="input flex-1"
                            placeholder="sk-..."
                          />
                          <button
                            onClick={() => testOpenAIConnection(settings.vlm.openai_api_key || '', settings.vlm.openai_base_url)}
                            disabled={isTestingProvider}
                            className="btn-secondary px-4 flex items-center gap-2"
                          >
                            {isTestingProvider && openaiStatus === 'checking' ? (
                              <ArrowPathIcon className="w-4 h-4 animate-spin" />
                            ) : (
                              <ArrowPathIcon className="w-4 h-4" />
                            )}
                            Test
                          </button>
                        </div>
                      </div>

                      <div>
                        <label className="block text-sm font-medium text-gray-300 mb-2">
                          Custom Base URL (Optional)
                        </label>
                        <input
                          type="text"
                          value={settings.vlm.openai_base_url || ''}
                          onChange={(e) =>
                            setSettings({
                              ...settings,
                              vlm: { ...settings.vlm, openai_base_url: e.target.value },
                            })
                          }
                          className="input"
                          placeholder="https://api.openai.com/v1 (default)"
                        />
                        <p className="text-xs text-gray-500 mt-1">
                          For OpenAI-compatible APIs like Azure OpenAI, OpenRouter, etc.
                        </p>
                      </div>
                    </div>

                    {/* OpenAI Model Selection */}
                    <div>
                      <div className="flex items-center justify-between mb-2">
                        <label className="block text-sm font-medium text-gray-400">
                          Select Model
                        </label>
                        {openaiStatus === 'online' && openaiModels.length > 0 && (
                          <span className="text-xs text-green-400">
                            {openaiModels.length} models fetched
                          </span>
                        )}
                      </div>
                      <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
                        {(openaiModels.length > 0 ? openaiModels : openaiModelOptions).map((model) => (
                          <button
                            key={model}
                            onClick={() =>
                              setSettings({
                                ...settings,
                                vlm: { ...settings.vlm, openai_model: model },
                              })
                            }
                            className={`p-3 rounded-xl text-left transition-all border ${settings.vlm.openai_model === model
                              ? 'bg-primary-500/20 border-primary-500/50 text-primary-400'
                              : 'bg-white/5 border-white/10 text-gray-300 hover:border-white/20 hover:bg-white/10'
                              }`}
                          >
                            <p className="font-medium truncate">{model}</p>
                            <p className="text-xs text-gray-500 mt-1">
                              {model.includes('4o') || model.includes('vision') ? '👁️ Vision' :
                                model.includes('o1') || model.includes('o3') ? '🧠 Reasoning' :
                                  model.includes('turbo') ? '⚡ Fast' : '💬 Chat'}
                            </p>
                          </button>
                        ))}
                      </div>
                    </div>
                  </>
                )}

                {/* Gemini Settings */}
                {settings.vlm.provider === 'gemini' && (
                  <>
                    <div className="p-4 rounded-xl bg-white/5 border border-white/10">
                      <label className="block text-sm font-medium text-gray-300 mb-2">
                        Gemini API Key
                      </label>
                      <div className="flex gap-3">
                        <input
                          type="password"
                          value={settings.vlm.gemini_api_key || ''}
                          onChange={(e) =>
                            setSettings({
                              ...settings,
                              vlm: { ...settings.vlm, gemini_api_key: e.target.value },
                            })
                          }
                          className="input flex-1"
                          placeholder="AIza..."
                        />
                        <button
                          onClick={() => testGeminiConnection(settings.vlm.gemini_api_key || '')}
                          disabled={isTestingProvider}
                          className="btn-secondary px-4 flex items-center gap-2"
                        >
                          {isTestingProvider && geminiStatus === 'checking' ? (
                            <ArrowPathIcon className="w-4 h-4 animate-spin" />
                          ) : (
                            <ArrowPathIcon className="w-4 h-4" />
                          )}
                          Test
                        </button>
                      </div>
                      <p className="text-xs text-gray-500 mt-2">
                        Get your API key from <a href="https://aistudio.google.com/apikey" target="_blank" rel="noopener noreferrer" className="text-primary-400 hover:underline">Google AI Studio</a>
                      </p>
                    </div>

                    {/* Gemini Model Selection */}
                    <div>
                      <div className="flex items-center justify-between mb-2">
                        <label className="block text-sm font-medium text-gray-400">
                          Select Model
                        </label>
                        {geminiStatus === 'online' && geminiModels.length > 0 && (
                          <span className="text-xs text-green-400">
                            {geminiModels.length} models fetched
                          </span>
                        )}
                      </div>
                      <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
                        {(geminiModels.length > 0 ? geminiModels : geminiModelOptions).map((model) => (
                          <button
                            key={model}
                            onClick={() =>
                              setSettings({
                                ...settings,
                                vlm: { ...settings.vlm, gemini_model: model },
                              })
                            }
                            className={`p-3 rounded-xl text-left transition-all border ${settings.vlm.gemini_model === model
                              ? 'bg-primary-500/20 border-primary-500/50 text-primary-400'
                              : 'bg-white/5 border-white/10 text-gray-300 hover:border-white/20 hover:bg-white/10'
                              }`}
                          >
                            <p className="font-medium truncate">{model.replace('gemini-', '').replace('models/', '')}</p>
                            <p className="text-xs text-gray-500 mt-1">
                              {model.includes('2.0') ? '🚀 Latest' :
                                model.includes('flash') ? '⚡ Fast' :
                                  model.includes('pro') ? '🎯 Advanced' :
                                    model.includes('vision') ? '👁️ Vision' : '💬 Standard'}
                            </p>
                          </button>
                        ))}
                      </div>
                    </div>
                  </>
                )}

                {/* Auto-Summarize Toggle */}
                <div className="flex items-center justify-between p-4 rounded-xl bg-white/5 border border-white/10">
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-lg bg-primary-500/20 flex items-center justify-center">
                      <SparklesIcon className="w-5 h-5 text-primary-400" />
                    </div>
                    <div>
                      <p className="text-white font-medium">Auto-Summarize Events</p>
                      <p className="text-sm text-gray-400">
                        Generate AI summaries for detected events automatically
                      </p>
                    </div>
                  </div>
                  <button
                    onClick={() =>
                      setSettings({
                        ...settings,
                        vlm: { ...settings.vlm, auto_summarize: !settings.vlm.auto_summarize },
                      })
                    }
                    className={`relative w-14 h-7 rounded-full transition-colors ${settings.vlm.auto_summarize ? 'bg-primary-500' : 'bg-white/20'
                      }`}
                  >
                    <div
                      className={`absolute top-1 w-5 h-5 rounded-full bg-white shadow-lg transition-transform ${settings.vlm.auto_summarize ? 'translate-x-8' : 'translate-x-1'
                        }`}
                    />
                  </button>
                </div>

                {/* Summarization Delay */}
                <div className="p-4 rounded-xl bg-white/5 border border-white/10">
                  <div className="flex items-center justify-between mb-3">
                    <label className="text-sm font-medium text-gray-300">
                      Summarization Delay
                    </label>
                    <span className="text-primary-400 font-semibold">
                      {settings.vlm.summarize_delay_seconds}s
                    </span>
                  </div>
                  <input
                    type="range"
                    min="1"
                    max="30"
                    step="1"
                    value={settings.vlm.summarize_delay_seconds}
                    onChange={(e) =>
                      setSettings({
                        ...settings,
                        vlm: {
                          ...settings.vlm,
                          summarize_delay_seconds: parseInt(e.target.value),
                        },
                      })
                    }
                    className="w-full h-2 bg-white/10 rounded-lg appearance-none cursor-pointer accent-primary-500"
                  />
                  <div className="flex justify-between text-xs text-gray-500 mt-2">
                    <span>1s (Fast)</span>
                    <span>30s (Delayed)</span>
                  </div>
                </div>
              </div>
            )}

            {activeTab === 'storage' && (
              <div className="space-y-6">
                <h2 className="text-lg font-semibold text-white">Storage Settings</h2>

                <div className="grid grid-cols-2 gap-6">
                  <div>
                    <label className="block text-sm font-medium text-gray-400 mb-2">
                      Recordings Path
                    </label>
                    <input
                      type="text"
                      value={settings.storage.recordings_path}
                      onChange={(e) =>
                        setSettings({
                          ...settings,
                          storage: { ...settings.storage, recordings_path: e.target.value },
                        })
                      }
                      className="input"
                    />
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-400 mb-2">
                      Snapshots Path
                    </label>
                    <input
                      type="text"
                      value={settings.storage.snapshots_path}
                      onChange={(e) =>
                        setSettings({
                          ...settings,
                          storage: { ...settings.storage, snapshots_path: e.target.value },
                        })
                      }
                      className="input"
                    />
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-6">
                  <div>
                    <label className="block text-sm font-medium text-gray-400 mb-2">
                      Max Storage (GB)
                    </label>
                    <input
                      type="number"
                      value={settings.storage.max_storage_gb}
                      onChange={(e) =>
                        setSettings({
                          ...settings,
                          storage: { ...settings.storage, max_storage_gb: parseInt(e.target.value) },
                        })
                      }
                      className="input"
                    />
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-400 mb-2">
                      Retention Days
                    </label>
                    <input
                      type="number"
                      value={settings.storage.retention_days}
                      onChange={(e) =>
                        setSettings({
                          ...settings,
                          storage: { ...settings.storage, retention_days: parseInt(e.target.value) },
                        })
                      }
                      className="input"
                    />
                  </div>
                </div>
              </div>
            )}

            {activeTab === 'notifications' && (
              <div className="space-y-6">
                <div className="flex items-center justify-between">
                  <h2 className="text-lg font-semibold text-white flex items-center gap-2">
                    <BellIcon className="w-5 h-5 text-primary-400" />
                    Notification Settings
                  </h2>
                </div>

                {/* Master Toggle */}
                <div className="flex items-center justify-between p-4 rounded-xl bg-gradient-to-r from-primary-500/10 to-cyan-500/10 border border-primary-500/20">
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-lg bg-primary-500/20 flex items-center justify-center">
                      <BellIcon className="w-5 h-5 text-primary-400" />
                    </div>
                    <div>
                      <p className="text-white font-medium">Enable Notifications</p>
                      <p className="text-sm text-gray-400">Receive alerts for events via Telegram & Email</p>
                    </div>
                  </div>
                  <button
                    onClick={() =>
                      setSettings({
                        ...settings,
                        notifications: {
                          ...settings.notifications,
                          enabled: !settings.notifications.enabled,
                        },
                      })
                    }
                    className={`relative w-14 h-7 rounded-full transition-colors ${settings.notifications.enabled ? 'bg-primary-500' : 'bg-white/20'
                      }`}
                  >
                    <div
                      className={`absolute top-1 w-5 h-5 rounded-full bg-white shadow-lg transition-transform ${settings.notifications.enabled ? 'translate-x-8' : 'translate-x-1'
                        }`}
                    />
                  </button>
                </div>

                {/* Minimum Severity */}
                <div className="grid grid-cols-2 gap-6">
                  <div>
                    <label className="block text-sm font-medium text-gray-400 mb-2">
                      Minimum Severity
                    </label>
                    <select
                      value={settings.notifications.min_severity}
                      onChange={(e) =>
                        setSettings({
                          ...settings,
                          notifications: {
                            ...settings.notifications,
                            min_severity: e.target.value,
                          },
                        })
                      }
                      className="input"
                    >
                      <option value="low">Low (All events)</option>
                      <option value="medium">Medium</option>
                      <option value="high">High</option>
                      <option value="critical">Critical only</option>
                    </select>
                  </div>
                </div>

                {/* Event Types Filter */}
                <div>
                  <div className="flex items-center justify-between mb-3">
                    <label className="text-sm font-medium text-gray-300">
                      Event Types to Notify
                    </label>
                    <div className="flex items-center gap-2">
                      <span className="text-xs text-gray-500">
                        {(settings.notifications.event_types || []).includes('all')
                          ? 'All events'
                          : `${settings.notifications.event_types?.length || 0} selected`}
                      </span>
                      <button
                        onClick={() => setSettings({
                          ...settings,
                          notifications: {
                            ...settings.notifications,
                            event_types: ['all']
                          }
                        })}
                        className="text-xs text-primary-400 hover:text-primary-300"
                      >
                        All
                      </button>
                      <button
                        onClick={() => setSettings({
                          ...settings,
                          notifications: { ...settings.notifications, event_types: [] }
                        })}
                        className="text-xs text-gray-400 hover:text-gray-300"
                      >
                        Clear
                      </button>
                    </div>
                  </div>
                  <div className="flex flex-wrap gap-2 p-3 bg-white/5 rounded-xl border border-white/10">
                    {eventTypes.map((event) => (
                      <button
                        key={event.id}
                        onClick={() => {
                          const current = settings.notifications.event_types || []
                          let newTypes: string[]

                          if (event.id === 'all') {
                            // If clicking "All", set only "all"
                            newTypes = current.includes('all') ? [] : ['all']
                          } else {
                            // If clicking specific event
                            if (current.includes('all')) {
                              // Remove "all" and add specific event
                              newTypes = [event.id]
                            } else if (current.includes(event.id)) {
                              // Remove this event
                              newTypes = current.filter((e) => e !== event.id)
                            } else {
                              // Add this event
                              newTypes = [...current, event.id]
                            }
                          }

                          setSettings({
                            ...settings,
                            notifications: {
                              ...settings.notifications,
                              event_types: newTypes,
                            },
                          })
                        }}
                        className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-all ${(settings.notifications.event_types || []).includes(event.id)
                          ? event.id === 'all'
                            ? 'bg-primary-500/30 text-primary-300 border border-primary-500/50'
                            : 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30'
                          : 'bg-white/5 text-gray-400 border border-white/10 hover:border-white/20'
                          }`}
                      >
                        {event.id === 'all' ? '🌐 ' : ''}{event.label}
                      </button>
                    ))}
                  </div>
                </div>

                {/* Telegram Settings */}
                <div className="p-4 rounded-xl bg-white/5 border border-white/10">
                  <div className="flex items-center justify-between mb-4">
                    <div className="flex items-center gap-3">
                      <div className="w-10 h-10 rounded-lg bg-blue-500/20 flex items-center justify-center">
                        <PaperAirplaneIcon className="w-5 h-5 text-blue-400" />
                      </div>
                      <div>
                        <p className="text-white font-medium">Telegram</p>
                        <p className="text-sm text-gray-400">Send event alerts to Telegram</p>
                      </div>
                    </div>
                    <button
                      onClick={() =>
                        setSettings({
                          ...settings,
                          notifications: {
                            ...settings.notifications,
                            telegram: {
                              ...settings.notifications.telegram,
                              enabled: !settings.notifications.telegram?.enabled,
                            },
                          },
                        })
                      }
                      className={`relative w-14 h-7 rounded-full transition-colors ${settings.notifications.telegram?.enabled ? 'bg-blue-500' : 'bg-white/20'
                        }`}
                    >
                      <div
                        className={`absolute top-1 w-5 h-5 rounded-full bg-white shadow-lg transition-transform ${settings.notifications.telegram?.enabled ? 'translate-x-8' : 'translate-x-1'
                          }`}
                      />
                    </button>
                  </div>

                  {settings.notifications.telegram?.enabled && (
                    <div className="space-y-4 pt-4 border-t border-white/10">
                      <div className="grid grid-cols-2 gap-4">
                        <div>
                          <label className="block text-sm font-medium text-gray-400 mb-2">
                            Bot Token
                          </label>
                          <input
                            type="password"
                            value={settings.notifications.telegram?.bot_token || ''}
                            onChange={(e) =>
                              setSettings({
                                ...settings,
                                notifications: {
                                  ...settings.notifications,
                                  telegram: {
                                    ...settings.notifications.telegram,
                                    bot_token: e.target.value,
                                  },
                                },
                              })
                            }
                            placeholder="123456789:ABCDEFGH..."
                            className="input"
                          />
                          <p className="text-xs text-gray-500 mt-1">Get from @BotFather</p>
                        </div>
                        <div>
                          <label className="block text-sm font-medium text-gray-400 mb-2">
                            Chat ID
                          </label>
                          <input
                            type="text"
                            value={settings.notifications.telegram?.chat_id || ''}
                            onChange={(e) =>
                              setSettings({
                                ...settings,
                                notifications: {
                                  ...settings.notifications,
                                  telegram: {
                                    ...settings.notifications.telegram,
                                    chat_id: e.target.value,
                                  },
                                },
                              })
                            }
                            placeholder="-1001234567890"
                            className="input"
                          />
                          <p className="text-xs text-gray-500 mt-1">User or Group Chat ID</p>
                        </div>
                      </div>

                      {/* What to send */}
                      <div>
                        <label className="block text-sm font-medium text-gray-400 mb-3">
                          Include in Notification
                        </label>
                        <div className="flex flex-wrap gap-3">
                          <label className="flex items-center gap-2 cursor-pointer">
                            <input
                              type="checkbox"
                              checked={settings.notifications.telegram?.send_photo ?? true}
                              onChange={(e) =>
                                setSettings({
                                  ...settings,
                                  notifications: {
                                    ...settings.notifications,
                                    telegram: {
                                      ...settings.notifications.telegram,
                                      send_photo: e.target.checked,
                                    },
                                  },
                                })
                              }
                              className="w-4 h-4 rounded border-gray-600 bg-white/10 text-primary-500 focus:ring-primary-500"
                            />
                            <span className="text-gray-300">📸 Photo</span>
                          </label>
                          <label className="flex items-center gap-2 cursor-pointer">
                            <input
                              type="checkbox"
                              checked={settings.notifications.telegram?.send_summary ?? true}
                              onChange={(e) =>
                                setSettings({
                                  ...settings,
                                  notifications: {
                                    ...settings.notifications,
                                    telegram: {
                                      ...settings.notifications.telegram,
                                      send_summary: e.target.checked,
                                    },
                                  },
                                })
                              }
                              className="w-4 h-4 rounded border-gray-600 bg-white/10 text-primary-500 focus:ring-primary-500"
                            />
                            <span className="text-gray-300">📝 AI Summary</span>
                          </label>
                          <label className="flex items-center gap-2 cursor-pointer">
                            <input
                              type="checkbox"
                              checked={settings.notifications.telegram?.send_details ?? true}
                              onChange={(e) =>
                                setSettings({
                                  ...settings,
                                  notifications: {
                                    ...settings.notifications,
                                    telegram: {
                                      ...settings.notifications.telegram,
                                      send_details: e.target.checked,
                                    },
                                  },
                                })
                              }
                              className="w-4 h-4 rounded border-gray-600 bg-white/10 text-primary-500 focus:ring-primary-500"
                            />
                            <span className="text-gray-300">📋 Event Details</span>
                          </label>
                        </div>
                      </div>
                    </div>
                  )}
                </div>

                {/* Email Settings */}
                <div className="p-4 rounded-xl bg-white/5 border border-white/10">
                  <div className="flex items-center justify-between mb-4">
                    <div className="flex items-center gap-3">
                      <div className="w-10 h-10 rounded-lg bg-orange-500/20 flex items-center justify-center">
                        <EnvelopeIcon className="w-5 h-5 text-orange-400" />
                      </div>
                      <div>
                        <p className="text-white font-medium">Email</p>
                        <p className="text-sm text-gray-400">Send event alerts via Email</p>
                      </div>
                    </div>
                    <button
                      onClick={() =>
                        setSettings({
                          ...settings,
                          notifications: {
                            ...settings.notifications,
                            email: {
                              ...settings.notifications.email,
                              enabled: !settings.notifications.email?.enabled,
                            },
                          },
                        })
                      }
                      className={`relative w-14 h-7 rounded-full transition-colors ${settings.notifications.email?.enabled ? 'bg-orange-500' : 'bg-white/20'
                        }`}
                    >
                      <div
                        className={`absolute top-1 w-5 h-5 rounded-full bg-white shadow-lg transition-transform ${settings.notifications.email?.enabled ? 'translate-x-8' : 'translate-x-1'
                          }`}
                      />
                    </button>
                  </div>

                  {settings.notifications.email?.enabled && (
                    <div className="space-y-4 pt-4 border-t border-white/10">
                      {/* SMTP Settings */}
                      <div className="grid grid-cols-2 gap-4">
                        <div>
                          <label className="block text-sm font-medium text-gray-400 mb-2">
                            SMTP Host
                          </label>
                          <input
                            type="text"
                            value={settings.notifications.email?.smtp_host || ''}
                            onChange={(e) =>
                              setSettings({
                                ...settings,
                                notifications: {
                                  ...settings.notifications,
                                  email: {
                                    ...settings.notifications.email,
                                    smtp_host: e.target.value,
                                  },
                                },
                              })
                            }
                            placeholder="smtp.gmail.com"
                            className="input"
                          />
                        </div>
                        <div>
                          <label className="block text-sm font-medium text-gray-400 mb-2">
                            SMTP Port
                          </label>
                          <input
                            type="number"
                            value={settings.notifications.email?.smtp_port || 587}
                            onChange={(e) =>
                              setSettings({
                                ...settings,
                                notifications: {
                                  ...settings.notifications,
                                  email: {
                                    ...settings.notifications.email,
                                    smtp_port: parseInt(e.target.value),
                                  },
                                },
                              })
                            }
                            placeholder="587"
                            className="input"
                          />
                        </div>
                      </div>

                      <div className="grid grid-cols-2 gap-4">
                        <div>
                          <label className="block text-sm font-medium text-gray-400 mb-2">
                            SMTP Username
                          </label>
                          <input
                            type="text"
                            value={settings.notifications.email?.smtp_user || ''}
                            onChange={(e) =>
                              setSettings({
                                ...settings,
                                notifications: {
                                  ...settings.notifications,
                                  email: {
                                    ...settings.notifications.email,
                                    smtp_user: e.target.value,
                                  },
                                },
                              })
                            }
                            placeholder="your-email@gmail.com"
                            className="input"
                          />
                        </div>
                        <div>
                          <label className="block text-sm font-medium text-gray-400 mb-2">
                            SMTP Password
                          </label>
                          <input
                            type="password"
                            value={settings.notifications.email?.smtp_password || ''}
                            onChange={(e) =>
                              setSettings({
                                ...settings,
                                notifications: {
                                  ...settings.notifications,
                                  email: {
                                    ...settings.notifications.email,
                                    smtp_password: e.target.value,
                                  },
                                },
                              })
                            }
                            placeholder="App password"
                            className="input"
                          />
                        </div>
                      </div>

                      <div className="grid grid-cols-2 gap-4">
                        <div>
                          <label className="block text-sm font-medium text-gray-400 mb-2">
                            From Address
                          </label>
                          <input
                            type="email"
                            value={settings.notifications.email?.from_address || ''}
                            onChange={(e) =>
                              setSettings({
                                ...settings,
                                notifications: {
                                  ...settings.notifications,
                                  email: {
                                    ...settings.notifications.email,
                                    from_address: e.target.value,
                                  },
                                },
                              })
                            }
                            placeholder="chowkidaar@example.com"
                            className="input"
                          />
                        </div>
                        <div>
                          <label className="block text-sm font-medium text-gray-400 mb-2">
                            Recipients (comma separated)
                          </label>
                          <input
                            type="text"
                            value={(settings.notifications.email?.recipients || []).join(', ')}
                            onChange={(e) =>
                              setSettings({
                                ...settings,
                                notifications: {
                                  ...settings.notifications,
                                  email: {
                                    ...settings.notifications.email,
                                    recipients: e.target.value.split(',').map(s => s.trim()).filter(Boolean),
                                  },
                                },
                              })
                            }
                            placeholder="admin@example.com, security@example.com"
                            className="input"
                          />
                        </div>
                      </div>

                      {/* What to send */}
                      <div>
                        <label className="block text-sm font-medium text-gray-400 mb-3">
                          Include in Email
                        </label>
                        <div className="flex flex-wrap gap-3">
                          <label className="flex items-center gap-2 cursor-pointer">
                            <input
                              type="checkbox"
                              checked={settings.notifications.email?.send_photo ?? true}
                              onChange={(e) =>
                                setSettings({
                                  ...settings,
                                  notifications: {
                                    ...settings.notifications,
                                    email: {
                                      ...settings.notifications.email,
                                      send_photo: e.target.checked,
                                    },
                                  },
                                })
                              }
                              className="w-4 h-4 rounded border-gray-600 bg-white/10 text-primary-500 focus:ring-primary-500"
                            />
                            <span className="text-gray-300">📸 Photo Attachment</span>
                          </label>
                          <label className="flex items-center gap-2 cursor-pointer">
                            <input
                              type="checkbox"
                              checked={settings.notifications.email?.send_summary ?? true}
                              onChange={(e) =>
                                setSettings({
                                  ...settings,
                                  notifications: {
                                    ...settings.notifications,
                                    email: {
                                      ...settings.notifications.email,
                                      send_summary: e.target.checked,
                                    },
                                  },
                                })
                              }
                              className="w-4 h-4 rounded border-gray-600 bg-white/10 text-primary-500 focus:ring-primary-500"
                            />
                            <span className="text-gray-300">📝 AI Summary</span>
                          </label>
                          <label className="flex items-center gap-2 cursor-pointer">
                            <input
                              type="checkbox"
                              checked={settings.notifications.email?.send_details ?? true}
                              onChange={(e) =>
                                setSettings({
                                  ...settings,
                                  notifications: {
                                    ...settings.notifications,
                                    email: {
                                      ...settings.notifications.email,
                                      send_details: e.target.checked,
                                    },
                                  },
                                })
                              }
                              className="w-4 h-4 rounded border-gray-600 bg-white/10 text-primary-500 focus:ring-primary-500"
                            />
                            <span className="text-gray-300">📋 Event Details</span>
                          </label>
                        </div>
                      </div>
                    </div>
                  )}
                </div>
              </div>
            )}

            {activeTab === 'security' && (
              <div className="space-y-6">
                <h2 className="text-lg font-semibold text-white">Security Settings</h2>

                <div className="p-4 rounded-xl bg-yellow-500/10 border border-yellow-500/30">
                  <p className="text-yellow-400 font-medium">Security Configuration</p>
                  <p className="text-sm text-gray-400 mt-1">
                    Security settings are managed through the Admin panel and environment
                    variables for maximum security.
                  </p>
                </div>

                <div className="space-y-4">
                  <div className="flex items-center justify-between p-4 rounded-xl bg-white/5">
                    <div>
                      <p className="text-white font-medium">JWT Token Expiry</p>
                      <p className="text-sm text-gray-400">Set via ACCESS_TOKEN_EXPIRE_MINUTES</p>
                    </div>
                    <span className="text-primary-400">30 minutes</span>
                  </div>

                  <div className="flex items-center justify-between p-4 rounded-xl bg-white/5">
                    <div>
                      <p className="text-white font-medium">Password Hashing</p>
                      <p className="text-sm text-gray-400">Algorithm used for password storage</p>
                    </div>
                    <span className="text-primary-400">bcrypt</span>
                  </div>

                  <div className="flex items-center justify-between p-4 rounded-xl bg-white/5">
                    <div>
                      <p className="text-white font-medium">CORS Policy</p>
                      <p className="text-sm text-gray-400">Cross-origin resource sharing</p>
                    </div>
                    <span className="text-green-400">Configured</span>
                  </div>
                </div>
              </div>
            )}
          </motion.div>
        </div>
      </div>
    </div>
  )
}
