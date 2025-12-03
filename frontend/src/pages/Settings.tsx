import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { motion } from 'framer-motion'
import {
  CogIcon,
  BellIcon,
  ServerStackIcon,
  ShieldCheckIcon,
  FolderIcon,
  CpuChipIcon,
} from '@heroicons/react/24/outline'
import toast from 'react-hot-toast'

interface Settings {
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
    email_enabled: boolean
    email_recipients: string[]
    min_severity: string
  }
}

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
  const queryClient = useQueryClient()

  const { isLoading } = useQuery({
    queryKey: ['settings'],
    queryFn: async () => {
      // This would fetch from API
      return defaultSettings
    },
    onSuccess: (data: Settings) => {
      setSettings(data)
    },
  })

  const saveMutation = useMutation({
    mutationFn: async (newSettings: Settings) => {
      // This would save to API
      await new Promise((resolve) => setTimeout(resolve, 500))
      return newSettings
    },
    onSuccess: () => {
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
          <div className="w-10 h-10 rounded-xl bg-primary-500/20 flex items-center justify-center">
            <CogIcon className="w-5 h-5 text-primary-400" />
          </div>
          <div>
            <h1 className="page-title">Settings</h1>
            <p className="text-gray-400 mt-1">Configure Chowkidaar NVR</p>
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
                    ? 'bg-primary-500/20 text-primary-400'
                    : 'text-gray-400 hover:text-white hover:bg-white/5'
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
                <h2 className="text-lg font-semibold text-white">Detection Settings</h2>
                
                <div className="grid grid-cols-2 gap-6">
                  <div>
                    <label className="block text-sm font-medium text-gray-400 mb-2">
                      YOLO Model
                    </label>
                    <select
                      value={settings.detection.model}
                      onChange={(e) =>
                        setSettings({
                          ...settings,
                          detection: { ...settings.detection, model: e.target.value },
                        })
                      }
                      className="input"
                    >
                      <option value="yolov8n">YOLOv8n (Nano - Fast)</option>
                      <option value="yolov8s">YOLOv8s (Small)</option>
                      <option value="yolov8m">YOLOv8m (Medium)</option>
                      <option value="yolov8l">YOLOv8l (Large)</option>
                      <option value="yolov8x">YOLOv8x (XLarge - Accurate)</option>
                    </select>
                  </div>

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
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-400 mb-2">
                    Confidence Threshold: {settings.detection.confidence_threshold}
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
                    className="w-full h-2 bg-white/10 rounded-lg appearance-none cursor-pointer"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-400 mb-3">
                    Enabled Detection Classes
                  </label>
                  <div className="flex flex-wrap gap-2">
                    {detectionClasses.map((cls) => (
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
                <h2 className="text-lg font-semibold text-white">Vision LLM Settings</h2>
                
                <div className="grid grid-cols-2 gap-6">
                  <div>
                    <label className="block text-sm font-medium text-gray-400 mb-2">
                      Ollama Model
                    </label>
                    <select
                      value={settings.vlm.model}
                      onChange={(e) =>
                        setSettings({
                          ...settings,
                          vlm: { ...settings.vlm, model: e.target.value },
                        })
                      }
                      className="input"
                    >
                      <option value="llava">LLaVA</option>
                      <option value="llava:13b">LLaVA 13B</option>
                      <option value="llava:34b">LLaVA 34B</option>
                      <option value="bakllava">BakLLaVA</option>
                    </select>
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-400 mb-2">
                      Ollama URL
                    </label>
                    <input
                      type="text"
                      value={settings.vlm.ollama_url}
                      onChange={(e) =>
                        setSettings({
                          ...settings,
                          vlm: { ...settings.vlm, ollama_url: e.target.value },
                        })
                      }
                      className="input"
                      placeholder="http://localhost:11434"
                    />
                  </div>
                </div>

                <div className="flex items-center justify-between p-4 rounded-xl bg-white/5">
                  <div>
                    <p className="text-white font-medium">Auto-Summarize Events</p>
                    <p className="text-sm text-gray-400">
                      Automatically generate AI summaries for detected events
                    </p>
                  </div>
                  <button
                    onClick={() =>
                      setSettings({
                        ...settings,
                        vlm: { ...settings.vlm, auto_summarize: !settings.vlm.auto_summarize },
                      })
                    }
                    className={`relative w-12 h-6 rounded-full transition-colors ${
                      settings.vlm.auto_summarize ? 'bg-primary-500' : 'bg-white/20'
                    }`}
                  >
                    <div
                      className={`absolute top-1 w-4 h-4 rounded-full bg-white transition-transform ${
                        settings.vlm.auto_summarize ? 'translate-x-7' : 'translate-x-1'
                      }`}
                    />
                  </button>
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-400 mb-2">
                    Summarization Delay (seconds): {settings.vlm.summarize_delay_seconds}
                  </label>
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
                    className="w-full h-2 bg-white/10 rounded-lg appearance-none cursor-pointer"
                  />
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
