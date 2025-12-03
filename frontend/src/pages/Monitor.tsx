import { useQuery } from '@tanstack/react-query'
import { motion } from 'framer-motion'
import {
  CpuChipIcon,
  ServerIcon,
  WifiIcon,
  ExclamationTriangleIcon,
  CheckCircleIcon,
} from '@heroicons/react/24/outline'
import { systemApi } from '../services'
import { Line } from 'react-chartjs-2'
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Filler,
} from 'chart.js'

ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Filler
)

export default function Monitor() {
  const { data: stats } = useQuery({
    queryKey: ['systemStats'],
    queryFn: systemApi.getStats,
    refetchInterval: 2000,
  })

  const { data: health } = useQuery({
    queryKey: ['systemHealth'],
    queryFn: systemApi.getHealth,
    refetchInterval: 5000,
  })

  const { data: streams } = useQuery({
    queryKey: ['activeStreams'],
    queryFn: systemApi.getActiveStreams,
    refetchInterval: 3000,
  })

  const chartOptions = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: { display: false },
      tooltip: {
        backgroundColor: 'rgba(17, 24, 39, 0.9)',
        borderColor: 'rgba(6, 182, 212, 0.3)',
        borderWidth: 1,
      },
    },
    scales: {
      x: {
        display: false,
      },
      y: {
        min: 0,
        max: 100,
        grid: {
          color: 'rgba(255, 255, 255, 0.1)',
        },
        ticks: {
          color: 'rgba(255, 255, 255, 0.5)',
        },
      },
    },
  }

  const createChartData = (value: number, color: string) => ({
    labels: Array(20).fill(''),
    datasets: [
      {
        data: Array(19).fill(null).concat([value]),
        borderColor: color,
        backgroundColor: `${color}20`,
        fill: true,
        tension: 0.4,
        pointRadius: 0,
      },
    ],
  })

  return (
    <div className="page-container">
      {/* Header */}
      <div className="page-header">
        <div>
          <h1 className="page-title">System Monitor</h1>
          <p className="text-gray-400 mt-1">Real-time hardware and system statistics</p>
        </div>
      </div>

      {/* Health Status */}
      {health && (
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className={`glass-card p-6 border-l-4 ${
            health.status === 'healthy'
              ? 'border-green-500'
              : health.status === 'warning'
              ? 'border-yellow-500'
              : 'border-red-500'
          }`}
        >
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              {health.status === 'healthy' ? (
                <CheckCircleIcon className="w-8 h-8 text-green-500" />
              ) : (
                <ExclamationTriangleIcon className="w-8 h-8 text-yellow-500" />
              )}
              <div>
                <h2 className="text-lg font-semibold text-white capitalize">
                  System {health.status}
                </h2>
                {health.issues.length > 0 && (
                  <p className="text-sm text-gray-400">
                    {health.issues.join(', ')}
                  </p>
                )}
              </div>
            </div>
            <div className="flex gap-4 text-sm">
              <StatusBadge label="Database" status={health.database_status} />
              <StatusBadge label="Ollama" status={health.ollama_status} />
            </div>
          </div>
        </motion.div>
      )}

      {/* Stats Grid */}
      {stats && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
          {/* CPU */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.1 }}
            className="glass-card p-6"
          >
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-xl bg-primary-500/20 flex items-center justify-center">
                  <CpuChipIcon className="w-5 h-5 text-primary-400" />
                </div>
                <div>
                  <p className="text-sm text-gray-400">CPU Usage</p>
                  <p className="text-2xl font-bold text-white">
                    {stats.cpu.usage_percent.toFixed(1)}%
                  </p>
                </div>
              </div>
            </div>
            <div className="h-20">
              <Line
                data={createChartData(stats.cpu.usage_percent, '#06b6d4')}
                options={chartOptions}
              />
            </div>
            <div className="mt-3 pt-3 border-t border-white/10 flex justify-between text-xs text-gray-400">
              <span>{stats.cpu.cores} Cores</span>
              <span>{stats.cpu.frequency_mhz.toFixed(0)} MHz</span>
              {stats.cpu.temperature && <span>{stats.cpu.temperature}°C</span>}
            </div>
          </motion.div>

          {/* Memory */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.2 }}
            className="glass-card p-6"
          >
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-xl bg-green-500/20 flex items-center justify-center">
                  <ServerIcon className="w-5 h-5 text-green-400" />
                </div>
                <div>
                  <p className="text-sm text-gray-400">Memory</p>
                  <p className="text-2xl font-bold text-white">
                    {stats.memory.usage_percent.toFixed(1)}%
                  </p>
                </div>
              </div>
            </div>
            <div className="h-20">
              <Line
                data={createChartData(stats.memory.usage_percent, '#22c55e')}
                options={chartOptions}
              />
            </div>
            <div className="mt-3 pt-3 border-t border-white/10 flex justify-between text-xs text-gray-400">
              <span>{stats.memory.used_gb.toFixed(1)} GB Used</span>
              <span>{stats.memory.total_gb.toFixed(1)} GB Total</span>
            </div>
          </motion.div>

          {/* GPU (if available) */}
          {stats.gpus && stats.gpus.length > 0 && (
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.3 }}
              className="glass-card p-6"
            >
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-xl bg-purple-500/20 flex items-center justify-center">
                    <CpuChipIcon className="w-5 h-5 text-purple-400" />
                  </div>
                  <div>
                    <p className="text-sm text-gray-400">GPU</p>
                    <p className="text-2xl font-bold text-white">
                      {stats.gpus[0].usage_percent.toFixed(1)}%
                    </p>
                  </div>
                </div>
              </div>
              <div className="h-20">
                <Line
                  data={createChartData(stats.gpus[0].usage_percent, '#a855f7')}
                  options={chartOptions}
                />
              </div>
              <div className="mt-3 pt-3 border-t border-white/10 text-xs text-gray-400">
                <p className="truncate">{stats.gpus[0].name}</p>
                <p>{stats.gpus[0].memory_used_mb.toFixed(0)} / {stats.gpus[0].memory_total_mb.toFixed(0)} MB</p>
              </div>
            </motion.div>
          )}

          {/* Streams */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.4 }}
            className="glass-card p-6"
          >
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-xl bg-yellow-500/20 flex items-center justify-center">
                  <WifiIcon className="w-5 h-5 text-yellow-400" />
                </div>
                <div>
                  <p className="text-sm text-gray-400">Active Streams</p>
                  <p className="text-2xl font-bold text-white">
                    {streams?.active_count || 0} / {stats.total_cameras}
                  </p>
                </div>
              </div>
            </div>
            <div className="space-y-2">
              {streams?.streams?.map((stream: Record<string, unknown>, i: number) => (
                <div key={i} className="flex items-center justify-between text-sm">
                  <span className="text-gray-400">Camera {stream.camera_id as number}</span>
                  <span className={`${
                    stream.state === 'connected' ? 'text-green-400' : 'text-yellow-400'
                  }`}>
                    {stream.state as string}
                  </span>
                </div>
              ))}
            </div>
          </motion.div>
        </div>
      )}

      {/* Inference Stats */}
      {stats?.inference && (
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.5 }}
          className="glass-card p-6"
        >
          <h2 className="text-lg font-semibold text-white mb-4">Model Inference</h2>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-6">
            <div>
              <p className="text-sm text-gray-400">Model</p>
              <p className="text-lg font-medium text-white">{stats.inference.model_name}</p>
            </div>
            <div>
              <p className="text-sm text-gray-400">Inference Count</p>
              <p className="text-lg font-medium text-white">{stats.inference.inference_count}</p>
            </div>
            <div>
              <p className="text-sm text-gray-400">Avg Time</p>
              <p className="text-lg font-medium text-white">{stats.inference.average_inference_time_ms.toFixed(1)} ms</p>
            </div>
            <div>
              <p className="text-sm text-gray-400">FPS</p>
              <p className="text-lg font-medium text-white">{stats.inference.fps.toFixed(1)}</p>
            </div>
          </div>
        </motion.div>
      )}

      {/* Disk Usage */}
      {stats?.disks && stats.disks.length > 0 && (
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.6 }}
          className="glass-card p-6"
        >
          <h2 className="text-lg font-semibold text-white mb-4">Storage</h2>
          <div className="space-y-4">
            {stats.disks.map((disk, i) => (
              <div key={i}>
                <div className="flex items-center justify-between mb-2">
                  <span className="text-sm text-gray-400">{disk.mount_point}</span>
                  <span className="text-sm text-white">
                    {disk.used_gb.toFixed(1)} / {disk.total_gb.toFixed(1)} GB
                  </span>
                </div>
                <div className="h-2 bg-white/10 rounded-full overflow-hidden">
                  <div
                    className={`h-full transition-all ${
                      disk.usage_percent > 90 ? 'bg-red-500' :
                      disk.usage_percent > 75 ? 'bg-yellow-500' : 'bg-primary-500'
                    }`}
                    style={{ width: `${disk.usage_percent}%` }}
                  />
                </div>
              </div>
            ))}
          </div>
        </motion.div>
      )}
    </div>
  )
}

function StatusBadge({ label, status }: { label: string; status: string }) {
  const colors: Record<string, string> = {
    healthy: 'text-green-400',
    warning: 'text-yellow-400',
    error: 'text-red-400',
    unavailable: 'text-gray-400',
  }

  return (
    <div className="flex items-center gap-2">
      <span className={`w-2 h-2 rounded-full ${
        status === 'healthy' ? 'bg-green-500' :
        status === 'warning' ? 'bg-yellow-500' :
        status === 'error' ? 'bg-red-500' : 'bg-gray-500'
      }`} />
      <span className={`${colors[status] || 'text-gray-400'}`}>{label}</span>
    </div>
  )
}
