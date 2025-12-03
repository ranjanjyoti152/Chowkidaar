import { useQuery } from '@tanstack/react-query'
import { motion } from 'framer-motion'
import {
  VideoCameraIcon,
  BellAlertIcon,
  CpuChipIcon,
  ExclamationTriangleIcon,
  CheckCircleIcon,
} from '@heroicons/react/24/outline'
import { cameraApi, eventApi, systemApi } from '../services'
import { useAuthStore } from '../store/authStore'
import type { EventSeverity } from '../types'

const severityColors: Record<EventSeverity, string> = {
  low: 'bg-blue-500/30 text-blue-300 border-blue-400/50',
  medium: 'bg-yellow-500/30 text-yellow-300 border-yellow-400/50',
  high: 'bg-orange-500/30 text-orange-300 border-orange-400/50',
  critical: 'bg-red-500/30 text-red-300 border-red-400/50',
}

export default function Dashboard() {
  const { token } = useAuthStore()
  const { data: cameras, isLoading: camerasLoading } = useQuery({
    queryKey: ['cameras'],
    queryFn: cameraApi.listCameras,
  })

  const { data: events, isLoading: eventsLoading } = useQuery({
    queryKey: ['events', { limit: 10 }],
    queryFn: () => eventApi.listEvents({ limit: 10 }),
  })

  const { data: stats } = useQuery({
    queryKey: ['eventStats'],
    queryFn: eventApi.getStats,
  })

  const { data: systemStats } = useQuery({
    queryKey: ['systemStats'],
    queryFn: systemApi.getStats,
    refetchInterval: 5000,
  })

  const onlineCameras = cameras?.filter((c) => c.status === 'online').length || 0
  const totalCameras = cameras?.length || 0

  const statCards = [
    {
      name: 'Cameras Online',
      value: `${onlineCameras}/${totalCameras}`,
      icon: VideoCameraIcon,
      color: 'from-primary-400 to-primary-600',
    },
    {
      name: 'Events Today',
      value: stats?.events_today || 0,
      icon: BellAlertIcon,
      color: 'from-yellow-400 to-orange-500',
    },
    {
      name: 'Active Streams',
      value: systemStats?.active_streams || 0,
      icon: CpuChipIcon,
      color: 'from-green-400 to-emerald-500',
    },
    {
      name: 'Unacknowledged',
      value: events?.filter((e) => !e.is_acknowledged).length || 0,
      icon: ExclamationTriangleIcon,
      color: 'from-red-400 to-rose-500',
    },
  ]

  return (
    <div className="page-container">
      {/* Header */}
      <div className="page-header">
        <div>
          <h1 className="page-title">Dashboard</h1>
          <p className="text-gray-300 mt-1">Welcome to Chowkidaar NVR</p>
        </div>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {statCards.map((stat, index) => (
          <motion.div
            key={stat.name}
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: index * 0.1 }}
            className="glass-card p-6"
          >
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-300">{stat.name}</p>
                <p className="text-3xl font-bold text-white mt-1">{stat.value}</p>
              </div>
              <div
                className={`w-12 h-12 rounded-xl bg-gradient-to-br ${stat.color} flex items-center justify-center`}
              >
                <stat.icon className="w-6 h-6 text-white" />
              </div>
            </div>
          </motion.div>
        ))}
      </div>

      {/* Main Content Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Camera Feeds */}
        <div className="lg:col-span-2">
          <div className="glass-card p-6">
            <h2 className="text-lg font-semibold text-white mb-4">Camera Feeds</h2>
            {camerasLoading ? (
              <div className="grid grid-cols-2 gap-4">
                {[1, 2, 3, 4].map((i) => (
                  <div key={i} className="aspect-video skeleton" />
                ))}
              </div>
            ) : cameras && cameras.length > 0 ? (
              <div className="grid grid-cols-2 gap-4">
                {cameras.slice(0, 4).map((camera) => (
                  <div key={camera.id} className="relative video-container">
                    {camera.status === 'online' ? (
                      <img
                        src={`${cameraApi.getStreamUrl(camera.id)}?token=${token}`}
                        alt={camera.name}
                        className="w-full h-full object-cover"
                      />
                    ) : (
                      <div className="w-full h-full flex items-center justify-center bg-dark-400">
                        <VideoCameraIcon className="w-12 h-12 text-gray-600" />
                      </div>
                    )}
                    <div className="video-overlay">
                      <div className="absolute bottom-0 left-0 right-0 p-3">
                        <div className="flex items-center justify-between">
                          <span className="text-sm text-white font-medium">
                            {camera.name}
                          </span>
                          <span
                            className={`w-2 h-2 rounded-full ${
                              camera.status === 'online'
                                ? 'bg-green-500 animate-pulse'
                                : 'bg-gray-500'
                            }`}
                          />
                        </div>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="text-center py-12">
                <VideoCameraIcon className="w-12 h-12 text-gray-600 mx-auto mb-4" />
                <p className="text-gray-400">No cameras configured</p>
              </div>
            )}
          </div>
        </div>

        {/* Recent Events */}
        <div className="glass-card p-6">
          <h2 className="text-lg font-semibold text-white mb-4">Recent Events</h2>
          {eventsLoading ? (
            <div className="space-y-4">
              {[1, 2, 3, 4, 5].map((i) => (
                <div key={i} className="h-16 skeleton" />
              ))}
            </div>
          ) : events && events.length > 0 ? (
            <div className="space-y-3">
              {events.slice(0, 8).map((event) => (
                <motion.div
                  key={event.id}
                  initial={{ opacity: 0, x: -20 }}
                  animate={{ opacity: 1, x: 0 }}
                  className="flex items-center gap-3 p-3 rounded-xl bg-white/10 hover:bg-white/15 transition-colors cursor-pointer"
                >
                  <div
                    className={`w-10 h-10 rounded-lg flex items-center justify-center ${
                      event.is_acknowledged
                        ? 'bg-green-500/30'
                        : 'bg-red-500/30'
                    }`}
                  >
                    {event.is_acknowledged ? (
                      <CheckCircleIcon className="w-5 h-5 text-green-300" />
                    ) : (
                      <ExclamationTriangleIcon className="w-5 h-5 text-red-300" />
                    )}
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm text-white font-medium truncate">
                      {event.event_type.replace('_', ' ')}
                    </p>
                    <p className="text-xs text-gray-300 truncate">
                      {event.camera_name}
                    </p>
                  </div>
                  <span
                    className={`badge border ${severityColors[event.severity]}`}
                  >
                    {event.severity}
                  </span>
                </motion.div>
              ))}
            </div>
          ) : (
            <div className="text-center py-12">
              <BellAlertIcon className="w-12 h-12 text-gray-600 mx-auto mb-4" />
              <p className="text-gray-400">No events yet</p>
            </div>
          )}
        </div>
      </div>

      {/* System Stats */}
      {systemStats && (
        <div className="glass-card p-6">
          <h2 className="text-lg font-semibold text-white mb-4">System Resources</h2>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-6">
            {/* CPU */}
            <div>
              <div className="flex items-center justify-between mb-2">
                <span className="text-sm text-gray-300">CPU</span>
                <span className="text-sm font-medium text-white">
                  {systemStats.cpu.usage_percent.toFixed(1)}%
                </span>
              </div>
              <div className="h-2.5 bg-white/15 rounded-full overflow-hidden">
                <div
                  className="h-full bg-gradient-to-r from-primary-400 to-primary-500 transition-all"
                  style={{ width: `${systemStats.cpu.usage_percent}%` }}
                />
              </div>
            </div>

            {/* Memory */}
            <div>
              <div className="flex items-center justify-between mb-2">
                <span className="text-sm text-gray-300">Memory</span>
                <span className="text-sm font-medium text-white">
                  {systemStats.memory.usage_percent.toFixed(1)}%
                </span>
              </div>
              <div className="h-2.5 bg-white/15 rounded-full overflow-hidden">
                <div
                  className="h-full bg-gradient-to-r from-green-400 to-emerald-500 transition-all"
                  style={{ width: `${systemStats.memory.usage_percent}%` }}
                />
              </div>
            </div>

            {/* GPU (if available) */}
            {systemStats.gpus && systemStats.gpus.length > 0 && (
              <div>
                <div className="flex items-center justify-between mb-2">
                  <span className="text-sm text-gray-300">GPU</span>
                  <span className="text-sm font-medium text-white">
                    {systemStats.gpus[0].usage_percent.toFixed(1)}%
                  </span>
                </div>
                <div className="h-2.5 bg-white/15 rounded-full overflow-hidden">
                  <div
                    className="h-full bg-gradient-to-r from-purple-400 to-pink-500 transition-all"
                    style={{ width: `${systemStats.gpus[0].usage_percent}%` }}
                  />
                </div>
              </div>
            )}

            {/* Disk */}
            {systemStats.disks && systemStats.disks.length > 0 && (
              <div>
                <div className="flex items-center justify-between mb-2">
                  <span className="text-sm text-gray-300">Disk</span>
                  <span className="text-sm font-medium text-white">
                    {systemStats.disks[0].usage_percent.toFixed(1)}%
                  </span>
                </div>
                <div className="h-2.5 bg-white/15 rounded-full overflow-hidden">
                  <div
                    className="h-full bg-gradient-to-r from-yellow-400 to-orange-500 transition-all"
                    style={{ width: `${systemStats.disks[0].usage_percent}%` }}
                  />
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
