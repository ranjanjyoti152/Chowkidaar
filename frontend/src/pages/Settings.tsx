import { useState, useEffect, useRef } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
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
} from '@heroicons/react/24/outline'
import toast from 'react-hot-toast'
import { systemApi, settingsApi, SettingsData } from '../services'

interface YoloModel {
  name: string
  display_name: string
  type: string
  size: string
  path?: string
}

type Settings = SettingsData

const defaultSettings: Settings = {
  detection: {
    model: 'yolov8n',
    confidence_threshold: 0.5,
    enabled_classes: ['person', 'car', 'truck', 'dog', 'cat'],
    inference_device: 'cuda',
  },
  vlm: {
    model: 'llava',
    ollama_url: 'http://localhost:11434',
    auto_summarize: true,
    summarize_delay_seconds: 5,
  },
  storage: {
    recordings_path: '/data/recordings',
    snapshots_path: '/data/snapshots',
    max_storage_gb: 500,
    retention_days: 30,
  },
  notifications: {
    enabled: true,
    email_enabled: false,
    email_recipients: [],
    min_severity: 'high',
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
  const fileInputRef = useRef<HTMLInputElement>(null)
  const queryClient = useQueryClient()

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

  const { isLoading } = useQuery({
    queryKey: ['settings'],
    queryFn: async () => {
      try {
        const data = await settingsApi.get()
        setSettings(data)
        // Set active model from loaded settings
        if (data.detection?.model) {
          setActiveYoloModel(data.detection.model)
        }
        // Fetch classes for the saved model
        if (data.detection?.model) {
          fetchModelClasses(data.detection.model)
        }
        // Fetch Ollama models with saved URL
        if (data.vlm?.ollama_url) {
          fetchOllamaModels(data.vlm.ollama_url)
        }
        return data
      } catch {
        // Only use defaults if fetch fails
        fetchOllamaModels(defaultSettings.vlm.ollama_url)
        return defaultSettings
      }
    },
  })

  const saveMutation = useMutation({
    mutationFn: async (newSettings: Settings) => {
      return await settingsApi.update(newSettings)
    },
    onSuccess: (data) => {
      setSettings(data)
      queryClient.invalidateQueries({ queryKey: ['settings'] })
      toast.success('Settings saved successfully')
    },
    onError: () => {
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
      setSettings(prev => ({
        ...prev,
        detection: { ...prev.detection, model: modelName }
      }))
      toast.success(`Model "${modelName}" activated`)
      fetchModelClasses(modelName)
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
                className={`w-full flex items-center gap-3 px-4 py-3 rounded-xl text-left transition-all ${
                  activeTab === tab.id
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

                {/* YOLO Model Selection */}
                <div className="p-4 rounded-xl bg-gradient-to-r from-primary-500/10 to-cyan-500/10 border border-primary-500/20">
                  <div className="flex items-center justify-between mb-4">
                    <label className="text-sm font-medium text-gray-300">
                      YOLO Models
                    </label>
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
                  </div>
                  
                  <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3">
                    {yoloModels.map((model) => (
                      <div
                        key={model.name}
                        className={`relative p-3 rounded-xl transition-all border cursor-pointer group ${
                          settings.detection.model === model.name
                            ? 'bg-primary-500/20 border-primary-500/50'
                            : 'bg-white/5 border-white/10 hover:border-white/20 hover:bg-white/10'
                        }`}
                        onClick={() => {
                          setSettings({
                            ...settings,
                            detection: { ...settings.detection, model: model.name },
                          })
                          fetchModelClasses(model.name)
                        }}
                      >
                        <div className="flex items-start justify-between">
                          <div className="flex-1 min-w-0">
                            <p className={`font-medium truncate ${
                              settings.detection.model === model.name ? 'text-primary-400' : 'text-gray-200'
                            }`}>
                              {model.name.split('/').pop()?.replace('.pt', '')}
                            </p>
                            <p className="text-xs text-gray-500 mt-0.5">{model.size}</p>
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
                          <span className={`text-xs px-2 py-0.5 rounded-full ${
                            model.type === 'builtin' 
                              ? 'bg-blue-500/20 text-blue-400' 
                              : 'bg-purple-500/20 text-purple-400'
                          }`}>
                            {model.type}
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

                {/* Detection Classes */}
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
                        className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-all ${
                          settings.detection.enabled_classes.includes(cls)
                            ? 'bg-primary-500/20 text-primary-400 border border-primary-500/30'
                            : 'bg-white/5 text-gray-400 border border-white/10 hover:border-white/20'
                        }`}
                      >
                        {cls}
                      </button>
                    ))}
                  </div>
                </div>
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
                    {ollamaStatus === 'checking' && (
                      <span className="flex items-center gap-1.5 text-yellow-400 text-sm">
                        <ArrowPathIcon className="w-4 h-4 animate-spin" />
                        Checking...
                      </span>
                    )}
                    {ollamaStatus === 'online' && (
                      <span className="flex items-center gap-1.5 text-green-400 text-sm">
                        <CheckCircleIcon className="w-4 h-4" />
                        Connected ({ollamaModels.length} models)
                      </span>
                    )}
                    {ollamaStatus === 'offline' && (
                      <span className="flex items-center gap-1.5 text-red-400 text-sm">
                        <ExclamationCircleIcon className="w-4 h-4" />
                        Offline
                      </span>
                    )}
                  </div>
                </div>

                {/* Ollama URL with Test Button */}
                <div className="p-4 rounded-xl bg-gradient-to-r from-primary-500/10 to-cyan-500/10 border border-primary-500/20">
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

                {/* Model Selection */}
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
                          className={`p-3 rounded-xl text-left transition-all border ${
                            settings.vlm.model === model
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
                    className={`relative w-14 h-7 rounded-full transition-colors ${
                      settings.vlm.auto_summarize ? 'bg-primary-500' : 'bg-white/20'
                    }`}
                  >
                    <div
                      className={`absolute top-1 w-5 h-5 rounded-full bg-white shadow-lg transition-transform ${
                        settings.vlm.auto_summarize ? 'translate-x-8' : 'translate-x-1'
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
                <h2 className="text-lg font-semibold text-white">Notification Settings</h2>
                
                <div className="flex items-center justify-between p-4 rounded-xl bg-white/5">
                  <div>
                    <p className="text-white font-medium">Enable Notifications</p>
                    <p className="text-sm text-gray-400">Receive alerts for events</p>
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
                    className={`relative w-12 h-6 rounded-full transition-colors ${
                      settings.notifications.enabled ? 'bg-primary-500' : 'bg-white/20'
                    }`}
                  >
                    <div
                      className={`absolute top-1 w-4 h-4 rounded-full bg-white transition-transform ${
                        settings.notifications.enabled ? 'translate-x-7' : 'translate-x-1'
                      }`}
                    />
                  </button>
                </div>

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
