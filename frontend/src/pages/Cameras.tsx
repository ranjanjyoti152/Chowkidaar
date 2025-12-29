import { useState, useEffect } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { motion, AnimatePresence } from 'framer-motion'
import {
  PlusIcon,
  VideoCameraIcon,
  TrashIcon,
  PencilIcon,
  PlayIcon,
  StopIcon,
  XMarkIcon,
  SignalIcon,
} from '@heroicons/react/24/outline'
import { cameraApi } from '../services'
import { useAuthStore } from '../store/authStore'
import type { Camera, CameraCreate, CameraStatus } from '../types'
import toast from 'react-hot-toast'

const statusConfig: Record<CameraStatus, { color: string; label: string }> = {
  online: { color: 'bg-green-500', label: 'Online' },
  offline: { color: 'bg-gray-500', label: 'Offline' },
  connecting: { color: 'bg-yellow-500', label: 'Connecting' },
  error: { color: 'bg-red-500', label: 'Error' },
  disabled: { color: 'bg-gray-600', label: 'Disabled' },
}

export default function Cameras() {
  const [showAddModal, setShowAddModal] = useState(false)
  const [editingCamera, setEditingCamera] = useState<Camera | null>(null)
  const [fullscreenCamera, setFullscreenCamera] = useState<Camera | null>(null)
  const queryClient = useQueryClient()
  const { token } = useAuthStore()

  const { data: cameras, isLoading } = useQuery({
    queryKey: ['cameras'],
    queryFn: cameraApi.listCameras,
  })

  const createMutation = useMutation({
    mutationFn: cameraApi.createCamera,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['cameras'] })
      setShowAddModal(false)
      toast.success('Camera added successfully')
    },
    onError: () => toast.error('Failed to add camera'),
  })

  const deleteMutation = useMutation({
    mutationFn: cameraApi.deleteCamera,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['cameras'] })
      toast.success('Camera deleted')
    },
    onError: () => toast.error('Failed to delete camera'),
  })

  const startStreamMutation = useMutation({
    mutationFn: cameraApi.startStream,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['cameras'] })
      toast.success('Stream started')
    },
    onError: () => toast.error('Failed to start stream'),
  })

  const stopStreamMutation = useMutation({
    mutationFn: cameraApi.stopStream,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['cameras'] })
      toast.success('Stream stopped')
    },
    onError: () => toast.error('Failed to stop stream'),
  })

  const testMutation = useMutation({
    mutationFn: cameraApi.testCamera,
    onSuccess: (result) => {
      if (result.success) {
        toast.success(`Connection successful! ${result.resolution} @ ${result.fps}fps`)
      } else {
        toast.error(result.message)
      }
    },
    onError: () => toast.error('Connection test failed'),
  })

  // Handle ESC key to close fullscreen modal
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && fullscreenCamera) {
        setFullscreenCamera(null)
      }
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [fullscreenCamera])

  return (
    <div className="page-container">
      {/* Header */}
      <div className="page-header">
        <div>
          <h1 className="page-title">Cameras</h1>
          <p className="text-gray-300 mt-1">Manage your RTSP camera sources</p>
        </div>
        <button
          onClick={() => setShowAddModal(true)}
          className="btn-primary"
        >
          <PlusIcon className="w-5 h-5" />
          Add Camera
        </button>
      </div>

      {/* Camera Grid */}
      {isLoading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {[1, 2, 3].map((i) => (
            <div key={i} className="glass-card p-6">
              <div className="aspect-video skeleton mb-4" />
              <div className="h-6 skeleton mb-2" />
              <div className="h-4 skeleton w-2/3" />
            </div>
          ))}
        </div>
      ) : cameras && cameras.length > 0 ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {cameras.map((camera) => (
            <motion.div
              key={camera.id}
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              className="glass-card overflow-hidden group"
            >
              {/* Video Preview - Click to open fullscreen */}
              <div
                className="relative aspect-video bg-dark-400 cursor-pointer"
                onClick={() => setFullscreenCamera(camera)}
              >
                {camera.status === 'online' ? (
                  <img
                    src={`${cameraApi.getStreamUrl(camera.id)}&token=${token}`}
                    alt={camera.name}
                    className="w-full h-full object-cover"
                  />
                ) : (
                  <div className="w-full h-full flex items-center justify-center">
                    <VideoCameraIcon className="w-16 h-16 text-gray-600" />
                  </div>
                )}

                {/* Status Badge */}
                <div className="absolute top-3 left-3">
                  <span className={`badge ${statusConfig[camera.status].color} text-white border-none`}>
                    {statusConfig[camera.status].label}
                  </span>
                </div>

                {/* Controls Overlay */}
                <div className="absolute inset-0 bg-black/60 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center gap-3">
                  {camera.status === 'online' ? (
                    <button
                      onClick={() => stopStreamMutation.mutate(camera.id)}
                      className="p-3 rounded-full bg-red-500/80 text-white hover:bg-red-500"
                    >
                      <StopIcon className="w-6 h-6" />
                    </button>
                  ) : (
                    <button
                      onClick={() => startStreamMutation.mutate(camera.id)}
                      className="p-3 rounded-full bg-green-500/80 text-white hover:bg-green-500"
                    >
                      <PlayIcon className="w-6 h-6" />
                    </button>
                  )}
                  <button
                    onClick={() => testMutation.mutate(camera.id)}
                    className="p-3 rounded-full bg-primary-500/80 text-white hover:bg-primary-500"
                  >
                    <SignalIcon className="w-6 h-6" />
                  </button>
                </div>
              </div>

              {/* Camera Info */}
              <div className="p-4">
                <div className="flex items-start justify-between">
                  <div>
                    <h3 className="text-lg font-semibold text-white">{camera.name}</h3>
                    <p className="text-sm text-gray-300">{camera.location || 'No location'}</p>
                  </div>
                  <div className="flex gap-1">
                    <button
                      onClick={() => setEditingCamera(camera)}
                      className="p-2 rounded-lg text-gray-400 hover:text-white hover:bg-white/10"
                    >
                      <PencilIcon className="w-4 h-4" />
                    </button>
                    <button
                      onClick={() => {
                        if (confirm('Delete this camera?')) {
                          deleteMutation.mutate(camera.id)
                        }
                      }}
                      className="p-2 rounded-lg text-gray-400 hover:text-red-400 hover:bg-red-500/10"
                    >
                      <TrashIcon className="w-4 h-4" />
                    </button>
                  </div>
                </div>

                {/* Stats */}
                <div className="mt-4 pt-4 border-t border-white/15 flex items-center gap-4">
                  <div className="flex items-center gap-2">
                    <span className="text-xs text-gray-400">Events Today</span>
                    <span className="text-sm font-semibold text-white">{camera.events_today}</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="text-xs text-gray-400">FPS</span>
                    <span className="text-sm font-semibold text-white">{camera.fps}</span>
                  </div>
                  {camera.detection_enabled && (
                    <span className="badge-primary text-xs">Detection ON</span>
                  )}
                </div>
              </div>
            </motion.div>
          ))}
        </div>
      ) : (
        <div className="glass-card p-12 text-center">
          <VideoCameraIcon className="w-16 h-16 text-gray-600 mx-auto mb-4" />
          <h3 className="text-xl font-semibold text-white mb-2">No cameras yet</h3>
          <p className="text-gray-400 mb-6">Add your first RTSP camera to get started</p>
          <button
            onClick={() => setShowAddModal(true)}
            className="btn-primary"
          >
            <PlusIcon className="w-5 h-5" />
            Add Camera
          </button>
        </div>
      )}

      {/* Add Camera Modal */}
      <AnimatePresence>
        {showAddModal && (
          <CameraModal
            onClose={() => setShowAddModal(false)}
            onSubmit={(data) => createMutation.mutate(data)}
            isLoading={createMutation.isPending}
          />
        )}
      </AnimatePresence>

      {/* Edit Camera Modal */}
      <AnimatePresence>
        {editingCamera && (
          <CameraModal
            camera={editingCamera}
            onClose={() => setEditingCamera(null)}
            onSubmit={(data) => {
              cameraApi.updateCamera(editingCamera.id, data).then(() => {
                queryClient.invalidateQueries({ queryKey: ['cameras'] })
                setEditingCamera(null)
                toast.success('Camera updated')
              })
            }}
            isLoading={false}
          />
        )}
      </AnimatePresence>

      {/* Fullscreen Camera Modal */}
      <AnimatePresence>
        {fullscreenCamera && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-50 flex items-center justify-center bg-black/90 backdrop-blur-md"
            onClick={() => setFullscreenCamera(null)}
          >
            <motion.div
              initial={{ scale: 0.9, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0.9, opacity: 0 }}
              transition={{ type: 'spring', damping: 25, stiffness: 300 }}
              onClick={(e) => e.stopPropagation()}
              className="relative w-[95vw] max-w-7xl"
            >
              {/* Header */}
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-4">
                  <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-primary-400 to-primary-600 flex items-center justify-center shadow-lg shadow-primary-500/40">
                    <VideoCameraIcon className="w-6 h-6 text-white" />
                  </div>
                  <div>
                    <h2 className="text-2xl font-bold text-white">{fullscreenCamera.name}</h2>
                    <p className="text-gray-400">{fullscreenCamera.location || 'No location'}</p>
                  </div>
                  <span className={`badge ${statusConfig[fullscreenCamera.status].color} text-white border-none ml-4`}>
                    {statusConfig[fullscreenCamera.status].label}
                  </span>
                </div>
                <button
                  onClick={() => setFullscreenCamera(null)}
                  className="p-3 rounded-xl bg-white/10 text-white hover:bg-white/20 transition-all duration-200"
                >
                  <XMarkIcon className="w-6 h-6" />
                </button>
              </div>

              {/* Video Feed */}
              <div className="glass-card overflow-hidden rounded-2xl">
                <div className="relative aspect-video bg-dark-400">
                  {fullscreenCamera.status === 'online' ? (
                    <img
                      src={`${cameraApi.getStreamUrl(fullscreenCamera.id)}&token=${token}`}
                      alt={fullscreenCamera.name}
                      className="w-full h-full object-contain"
                    />
                  ) : (
                    <div className="w-full h-full flex flex-col items-center justify-center">
                      <VideoCameraIcon className="w-24 h-24 text-gray-600 mb-4" />
                      <p className="text-gray-400 text-lg">Camera is {fullscreenCamera.status}</p>
                    </div>
                  )}
                </div>
              </div>

              {/* Controls */}
              <div className="flex items-center justify-center gap-4 mt-4">
                {fullscreenCamera.status === 'online' ? (
                  <button
                    onClick={() => {
                      stopStreamMutation.mutate(fullscreenCamera.id)
                      setFullscreenCamera(null)
                    }}
                    className="btn-danger flex items-center gap-2"
                  >
                    <StopIcon className="w-5 h-5" />
                    Stop Stream
                  </button>
                ) : (
                  <button
                    onClick={() => {
                      startStreamMutation.mutate(fullscreenCamera.id)
                      setFullscreenCamera(null)
                    }}
                    className="btn-success flex items-center gap-2"
                  >
                    <PlayIcon className="w-5 h-5" />
                    Start Stream
                  </button>
                )}
                <button
                  onClick={() => {
                    testMutation.mutate(fullscreenCamera.id)
                  }}
                  className="btn-primary flex items-center gap-2"
                >
                  <SignalIcon className="w-5 h-5" />
                  Test Connection
                </button>
                <button
                  onClick={() => {
                    setEditingCamera(fullscreenCamera)
                    setFullscreenCamera(null)
                  }}
                  className="btn-secondary flex items-center gap-2"
                >
                  <PencilIcon className="w-5 h-5" />
                  Edit Camera
                </button>
              </div>

              {/* Stats */}
              <div className="flex items-center justify-center gap-8 mt-4 text-sm">
                <div className="flex items-center gap-2">
                  <span className="text-gray-400">Events Today:</span>
                  <span className="font-semibold text-white">{fullscreenCamera.events_today}</span>
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-gray-400">FPS:</span>
                  <span className="font-semibold text-white">{fullscreenCamera.fps}</span>
                </div>
                {fullscreenCamera.detection_enabled && (
                  <span className="badge-primary">Detection ON</span>
                )}
              </div>

              {/* Hint */}
              <p className="text-center text-gray-500 text-sm mt-4">
                Press ESC or click outside to close
              </p>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}

function CameraModal({
  camera,
  onClose,
  onSubmit,
  isLoading,
}: {
  camera?: Camera
  onClose: () => void
  onSubmit: (data: CameraCreate) => void
  isLoading: boolean
}) {
  const [formData, setFormData] = useState<CameraCreate>({
    name: camera?.name || '',
    description: camera?.description || '',
    stream_url: camera?.stream_url || '',
    camera_type: camera?.camera_type || 'rtsp',
    location: camera?.location || '',
    location_type: camera?.location_type || '',
    expected_activity: camera?.expected_activity || '',
    unexpected_activity: camera?.unexpected_activity || '',
    normal_conditions: camera?.normal_conditions || '',
    fps: camera?.fps || 15,
    detection_enabled: camera?.detection_enabled ?? true,
    is_enabled: camera?.is_enabled ?? true,
  })

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    onSubmit(formData)
  }

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm"
      onClick={onClose}
    >
      <motion.div
        initial={{ scale: 0.95, opacity: 0 }}
        animate={{ scale: 1, opacity: 1 }}
        exit={{ scale: 0.95, opacity: 0 }}
        onClick={(e) => e.stopPropagation()}
        className="glass-card w-full max-w-lg p-6"
      >
        <div className="flex items-center justify-between mb-6">
          <h2 className="text-xl font-semibold text-white">
            {camera ? 'Edit Camera' : 'Add Camera'}
          </h2>
          <button onClick={onClose} className="text-gray-400 hover:text-white">
            <XMarkIcon className="w-6 h-6" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="label">Camera Name</label>
            <input
              type="text"
              className="input"
              placeholder="Front Door Camera"
              value={formData.name}
              onChange={(e) => setFormData({ ...formData, name: e.target.value })}
              required
            />
          </div>

          <div>
            <label className="label">RTSP URL</label>
            <input
              type="text"
              className="input"
              placeholder="rtsp://admin:password@192.168.1.100:554/stream"
              value={formData.stream_url}
              onChange={(e) => setFormData({ ...formData, stream_url: e.target.value })}
              required
            />
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="label">Location</label>
              <input
                type="text"
                className="input"
                placeholder="Front entrance"
                value={formData.location}
                onChange={(e) => setFormData({ ...formData, location: e.target.value })}
              />
            </div>
            <div>
              <label className="label">FPS</label>
              <input
                type="number"
                className="input"
                min="1"
                max="60"
                value={formData.fps}
                onChange={(e) => setFormData({ ...formData, fps: parseInt(e.target.value) })}
              />
            </div>
          </div>

          <div>
            <label className="label">Description</label>
            <textarea
              className="input min-h-[80px]"
              placeholder="Optional description..."
              value={formData.description}
              onChange={(e) => setFormData({ ...formData, description: e.target.value })}
            />
          </div>

          {/* Context-Aware Detection Settings */}
          <div className="border border-primary-500/30 rounded-lg p-4 bg-primary-500/5">
            <h3 className="text-sm font-semibold text-primary-300 mb-3 flex items-center gap-2">
              🧠 AI Context Settings
              <span className="text-xs font-normal text-gray-400">(helps AI decide severity)</span>
            </h3>

            <div className="space-y-3">
              <div>
                <label className="label text-xs">Location Type</label>
                <select
                  className="input"
                  value={formData.location_type}
                  onChange={(e) => setFormData({ ...formData, location_type: e.target.value })}
                >
                  <option value="">Select location type...</option>
                  <option value="office">🏢 Office / Workspace</option>
                  <option value="kitchen">🍳 Kitchen</option>
                  <option value="entrance">🚪 Entrance / Door</option>
                  <option value="parking">🚗 Parking Area</option>
                  <option value="warehouse">📦 Warehouse / Storage</option>
                  <option value="bedroom">🛏️ Bedroom</option>
                  <option value="living_room">🛋️ Living Room</option>
                  <option value="lobby">🏛️ Lobby / Reception</option>
                  <option value="corridor">🚶 Corridor / Hallway</option>
                  <option value="outdoor">🌳 Outdoor / Garden</option>
                  <option value="server_room">🖥️ Server Room</option>
                  <option value="lab">🔬 Lab / Workshop</option>
                  <option value="retail">🛒 Retail / Shop</option>
                </select>
              </div>

              <div>
                <label className="label text-xs">Expected Activity ✅</label>
                <input
                  type="text"
                  className="input"
                  placeholder="e.g., 'people working on computers', 'cooking with fire and stove'"
                  value={formData.expected_activity}
                  onChange={(e) => setFormData({ ...formData, expected_activity: e.target.value })}
                />
                <p className="text-xs text-gray-500 mt-1">What normally happens here? (LOW severity)</p>
              </div>

              <div>
                <label className="label text-xs">Unexpected Activity ⚠️</label>
                <input
                  type="text"
                  className="input"
                  placeholder="e.g., 'running', 'fighting', 'strangers at night', 'fire outside stove'"
                  value={formData.unexpected_activity}
                  onChange={(e) => setFormData({ ...formData, unexpected_activity: e.target.value })}
                />
                <p className="text-xs text-gray-500 mt-1">What should trigger HIGH alerts?</p>
              </div>

              <div>
                <label className="label text-xs">Normal Conditions</label>
                <input
                  type="text"
                  className="input"
                  placeholder="e.g., '5-10 people during work hours', 'fire on stove is normal', 'empty at night'"
                  value={formData.normal_conditions}
                  onChange={(e) => setFormData({ ...formData, normal_conditions: e.target.value })}
                />
                <p className="text-xs text-gray-500 mt-1">What should NOT trigger high alerts?</p>
              </div>
            </div>
          </div>

          <div className="flex items-center gap-4">
            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="checkbox"
                checked={formData.detection_enabled}
                onChange={(e) =>
                  setFormData({ ...formData, detection_enabled: e.target.checked })
                }
                className="sr-only"
              />
              <span
                className={`w-10 h-6 rounded-full transition-colors ${formData.detection_enabled ? 'bg-primary-500' : 'bg-gray-600'
                  }`}
              >
                <span
                  className={`block w-4 h-4 mt-1 ml-1 rounded-full bg-white transition-transform ${formData.detection_enabled ? 'translate-x-4' : ''
                    }`}
                />
              </span>
              <span className="text-sm text-gray-300">Enable Detection</span>
            </label>
          </div>

          <div className="flex gap-3 pt-4">
            <button
              type="button"
              onClick={onClose}
              className="btn-secondary flex-1"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isLoading}
              className="btn-primary flex-1"
            >
              {isLoading ? 'Saving...' : camera ? 'Update' : 'Add Camera'}
            </button>
          </div>
        </form>
      </motion.div>
    </motion.div>
  )
}
