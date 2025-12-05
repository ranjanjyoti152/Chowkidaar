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
  low: 'bg-blue-500/15 text-blue-300 border-blue-500/30',
  medium: 'bg-yellow-500/15 text-yellow-300 border-yellow-500/30',
  high: 'bg-orange-500/15 text-orange-300 border-orange-500/30',
  critical: 'bg-red-500/15 text-red-300 border-red-500/30',
}

// Animation variants
const containerVariants = {
  hidden: { opacity: 0 },
  visible: {
    opacity: 1,
    transition: { staggerChildren: 0.1 }
  }
}

const itemVariants = {
  hidden: { opacity: 0, y: 20 },
  visible: { 
    opacity: 1, 
    y: 0,
    transition: { duration: 0.3, ease: 'easeOut' }
  }
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
      shadowColor: 'shadow-primary-500/30',
    },
    {
      name: 'Events Today',
      value: stats?.events_today || 0,
      icon: BellAlertIcon,
      color: 'from-yellow-400 to-orange-500',
      shadowColor: 'shadow-orange-500/30',
    },
    {
      name: 'Active Streams',
      value: systemStats?.active_streams || 0,
      icon: CpuChipIcon,
      color: 'from-green-400 to-emerald-500',
      shadowColor: 'shadow-green-500/30',
    },
    {
      name: 'Unacknowledged',
      value: events?.filter((e) => !e.is_acknowledged).length || 0,
      icon: ExclamationTriangleIcon,
      color: 'from-red-400 to-rose-500',
      shadowColor: 'shadow-red-500/30',
    },
  ]

  return (
    <div className="page-container">
      {/* Header */}
      <motion.div 
        initial={{ opacity: 0, y: -10 }}
        animate={{ opacity: 1, y: 0 }}
        className="page-header"
      >
        <div>
          <h1 className="page-title">Dashboard</h1>
          <p className="text-gray-400 mt-1">Welcome to Chowkidaar NVR</p>
        </div>
      </motion.div>

      {/* Stats Grid */}
      <motion.div 
        variants={containerVariants}
        initial="hidden"
        animate="visible"
        className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4"
      >
        {statCards.map((stat, index) => (
          <motion.div
            key={stat.name}
            variants={itemVariants}
            whileHover={{ y: -4, transition: { duration: 0.2 } }}
            className="glass-card-hover p-6 group"
          >
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-400 font-medium">{stat.name}</p>
                <motion.p 
                  key={stat.value}
                  initial={{ opacity: 0, scale: 0.5 }}
                  animate={{ opacity: 1, scale: 1 }}
                  className="text-3xl font-bold text-white mt-1"
                >
                  {stat.value}
                </motion.p>
              </div>
              <motion.div
                whileHover={{ scale: 1.1, rotate: 5 }}
                className={`w-12 h-12 rounded-xl bg-gradient-to-br ${stat.color} ${stat.shadowColor} shadow-lg flex items-center justify-center`}
              >
                <stat.icon className="w-6 h-6 text-white" />
              </motion.div>
            </div>
          </motion.div>
        ))}
      </motion.div>

      {/* Main Content Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Camera Feeds */}
        <motion.div 
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.3 }}
          className="lg:col-span-2"
        >
          <div className="glass-card p-6">
            <h2 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
              <VideoCameraIcon className="w-5 h-5 text-primary-400" />
              Camera Feeds
            </h2>
            {camerasLoading ? (
              <div className="grid grid-cols-2 gap-4">
                {[1, 2, 3, 4].map((i) => (
                  <div key={i} className="aspect-video skeleton" />
                ))}
              </div>
            ) : cameras && cameras.length > 0 ? (
              <div className="grid grid-cols-2 gap-4">
                {cameras.slice(0, 4).map((camera, idx) => (
                  <motion.div 
                    key={camera.id} 
                    initial={{ opacity: 0, scale: 0.95 }}
                    animate={{ opacity: 1, scale: 1 }}
                    transition={{ delay: idx * 0.1 }}
                    whileHover={{ scale: 1.02 }}
                    className="relative video-container group cursor-pointer"
                  >
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
                    <div className="video-overlay group-hover:opacity-100 transition-opacity">
                      <div className="absolute bottom-0 left-0 right-0 p-3">
                        <div className="flex items-center justify-between">
                          <span className="text-sm text-white font-medium">
                            {camera.name}
                          </span>
                          <span
                            className={`w-2 h-2 rounded-full ${
                              camera.status === 'online'
                                ? 'bg-green-400 shadow-lg shadow-green-400/50'
                                : 'bg-gray-500'
                            }`}
                          />
                        </div>
                      </div>
                    </div>
                  </motion.div>
                ))}
              </div>
            ) : (
              <div className="text-center py-12">
                <VideoCameraIcon className="w-12 h-12 text-gray-600 mx-auto mb-4" />
                <p className="text-gray-400">No cameras configured</p>
              </div>
            )}
          </div>
        </motion.div>

        {/* Recent Events */}
        <motion.div 
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.4 }}
          className="glass-card p-6"
        >
          <h2 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
            <BellAlertIcon className="w-5 h-5 text-yellow-400" />
            Recent Events
          </h2>
          {eventsLoading ? (
            <div className="space-y-4">
              {[1, 2, 3, 4, 5].map((i) => (
                <div key={i} className="h-16 skeleton" />
              ))}
            </div>
          ) : events && events.length > 0 ? (
            <div className="space-y-3 max-h-[500px] overflow-y-auto scrollbar-hide">
              {events.slice(0, 8).map((event, idx) => (
                <motion.div
                  key={event.id}
                  initial={{ opacity: 0, x: -20 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: idx * 0.05 }}
                  whileHover={{ x: 4, backgroundColor: 'rgba(255,255,255,0.08)' }}
                  className="flex items-center gap-3 p-2 rounded-xl bg-white/5 cursor-pointer transition-all"
                >
                  {/* Event Thumbnail */}
                  <div className="w-14 h-14 rounded-lg overflow-hidden flex-shrink-0 bg-dark-400">
                    {event.thumbnail_path ? (
                      <img
                        src={`${eventApi.getThumbnailUrl(event.id)}?token=${token}`}
                        alt="Event"
                        className="w-full h-full object-cover"
                        onError={(e) => {
                          (e.target as HTMLImageElement).style.display = 'none';
                          (e.target as HTMLImageElement).parentElement!.innerHTML = '<div class="w-full h-full flex items-center justify-center bg-red-500/20"><svg class="w-6 h-6 text-gray-500" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" /></svg></div>';
                        }}
                      />
                    ) : (
                      <div className={`w-full h-full flex items-center justify-center ${
                        event.is_acknowledged ? 'bg-green-500/20' : 'bg-red-500/20'
                      }`}>
                        <ExclamationTriangleIcon className="w-6 h-6 text-gray-500" />
                      </div>
                    )}
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm text-white font-medium truncate">
                      {event.event_type.replace('_', ' ')}
                    </p>
                    <p className="text-xs text-gray-400 truncate">
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
        </motion.div>
      </div>

      {/* System Stats */}
      {systemStats && (
        <motion.div 
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.5 }}
          className="glass-card p-6"
        >
          <h2 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
            <CpuChipIcon className="w-5 h-5 text-purple-400" />
            System Resources
          </h2>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-6">
            {/* CPU */}
            <div className="group">
              <div className="flex items-center justify-between mb-2">
                <span className="text-sm text-gray-400">CPU</span>
                <span className="text-sm font-medium text-white">
                  {systemStats.cpu.usage_percent.toFixed(1)}%
                </span>
              </div>
              <div className="h-2 bg-white/10 rounded-full overflow-hidden">
                <motion.div
                  initial={{ width: 0 }}
                  animate={{ width: `${systemStats.cpu.usage_percent}%` }}
                  transition={{ duration: 0.8, ease: 'easeOut' }}
                  className="h-full bg-gradient-to-r from-primary-400 to-primary-500 rounded-full"
                />
              </div>
            </div>

            {/* Memory */}
            <div className="group">
              <div className="flex items-center justify-between mb-2">
                <span className="text-sm text-gray-400">Memory</span>
                <span className="text-sm font-medium text-white">
                  {systemStats.memory.usage_percent.toFixed(1)}%
                </span>
              </div>
              <div className="h-2 bg-white/10 rounded-full overflow-hidden">
                <motion.div
                  initial={{ width: 0 }}
                  animate={{ width: `${systemStats.memory.usage_percent}%` }}
                  transition={{ duration: 0.8, ease: 'easeOut', delay: 0.1 }}
                  className="h-full bg-gradient-to-r from-green-400 to-emerald-500 rounded-full"
                />
              </div>
            </div>

            {/* GPU (if available) */}
            {systemStats.gpus && systemStats.gpus.length > 0 && (
              <div className="group">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-sm text-gray-400">GPU</span>
                  <span className="text-sm font-medium text-white">
                    {systemStats.gpus[0].usage_percent.toFixed(1)}%
                  </span>
                </div>
                <div className="h-2 bg-white/10 rounded-full overflow-hidden">
                  <motion.div
                    initial={{ width: 0 }}
                    animate={{ width: `${systemStats.gpus[0].usage_percent}%` }}
                    transition={{ duration: 0.8, ease: 'easeOut', delay: 0.2 }}
                    className="h-full bg-gradient-to-r from-purple-400 to-pink-500 rounded-full"
                  />
                </div>
              </div>
            )}

            {/* Disk */}
            {systemStats.disks && systemStats.disks.length > 0 && (
              <div className="group">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-sm text-gray-400">Disk</span>
                  <span className="text-sm font-medium text-white">
                    {systemStats.disks[0].usage_percent.toFixed(1)}%
                  </span>
                </div>
                <div className="h-2 bg-white/10 rounded-full overflow-hidden">
                  <motion.div
                    initial={{ width: 0 }}
                    animate={{ width: `${systemStats.disks[0].usage_percent}%` }}
                    transition={{ duration: 0.8, ease: 'easeOut', delay: 0.3 }}
                    className="h-full bg-gradient-to-r from-yellow-400 to-orange-500 rounded-full"
                  />
                </div>
              </div>
            )}
          </div>
        </motion.div>
      )}
    </div>
  )
}
