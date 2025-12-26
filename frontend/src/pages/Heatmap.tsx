import { useState, useMemo, useEffect, useRef } from 'react'
import { useQuery } from '@tanstack/react-query'
import { motion } from 'framer-motion'
import {
    ChartBarSquareIcon,
    FunnelIcon,
    CalendarDaysIcon,
    VideoCameraIcon,
    FireIcon,
} from '@heroicons/react/24/outline'
import { cameraApi, systemApi, settingsApi } from '../services'
import api from '../services/api'
import { useAuthStore } from '../store/authStore'
import type { CameraWithStats } from '../types'

interface SpatialHeatPoint {
    x: number
    y: number
    class_name: string
    weight: number
}

interface SpatialHeatmapData {
    camera_id: number
    points: SpatialHeatPoint[]
    total_detections: number
    class_counts: Record<string, number>
}

interface HeatmapDataPoint {
    hour: number
    day: string
    day_name: string
    count: number
    class_name: string
}

interface HeatmapResponse {
    data: HeatmapDataPoint[]
    available_classes: string[]
    date_range: {
        start: string
        end: string
        days: number
    }
}

// Heat color gradient (cold to hot)
const getHeatColor = (intensity: number): string => {
    // intensity is 0-1
    const colors = [
        [0, 0, 255, 0],       // transparent blue
        [0, 255, 255, 0.3],   // cyan
        [0, 255, 0, 0.5],     // green
        [255, 255, 0, 0.6],   // yellow
        [255, 128, 0, 0.7],   // orange
        [255, 0, 0, 0.85],    // red
    ]

    const idx = Math.min(Math.floor(intensity * (colors.length - 1)), colors.length - 2)
    const t = (intensity * (colors.length - 1)) - idx

    const c1 = colors[idx]
    const c2 = colors[idx + 1]

    const r = Math.round(c1[0] + (c2[0] - c1[0]) * t)
    const g = Math.round(c1[1] + (c2[1] - c1[1]) * t)
    const b = Math.round(c1[2] + (c2[2] - c1[2]) * t)
    const a = c1[3] + (c2[3] - c1[3]) * t

    return `rgba(${r}, ${g}, ${b}, ${a})`
}

// Draw heatmap on canvas
const drawHeatmap = (
    canvas: HTMLCanvasElement,
    points: SpatialHeatPoint[],
    selectedClasses: Set<string>
) => {
    const ctx = canvas.getContext('2d')
    if (!ctx) return

    const width = canvas.width
    const height = canvas.height

    // Clear canvas
    ctx.clearRect(0, 0, width, height)

    // Filter points by selected classes
    const filteredPoints = points.filter(p => selectedClasses.has(p.class_name))
    if (filteredPoints.length === 0) return

    // Create density grid
    const gridSize = 20 // pixels
    const gridW = Math.ceil(width / gridSize)
    const gridH = Math.ceil(height / gridSize)
    const grid = new Float32Array(gridW * gridH)

    // Accumulate point densities
    filteredPoints.forEach(point => {
        const px = point.x * width
        const py = point.y * height
        const radius = 40 // influence radius in pixels

        // Add Gaussian influence to nearby grid cells
        for (let gy = 0; gy < gridH; gy++) {
            for (let gx = 0; gx < gridW; gx++) {
                const gcx = (gx + 0.5) * gridSize
                const gcy = (gy + 0.5) * gridSize
                const dist = Math.sqrt((gcx - px) ** 2 + (gcy - py) ** 2)

                if (dist < radius * 2) {
                    const influence = Math.exp(-(dist * dist) / (2 * radius * radius)) * point.weight
                    grid[gy * gridW + gx] += influence
                }
            }
        }
    })

    // Find max for normalization
    let maxDensity = 0
    for (let i = 0; i < grid.length; i++) {
        if (grid[i] > maxDensity) maxDensity = grid[i]
    }

    if (maxDensity === 0) return

    // Draw heat cells
    for (let gy = 0; gy < gridH; gy++) {
        for (let gx = 0; gx < gridW; gx++) {
            const density = grid[gy * gridW + gx]
            if (density > 0.01) {
                const intensity = density / maxDensity
                ctx.fillStyle = getHeatColor(intensity)
                ctx.fillRect(gx * gridSize, gy * gridSize, gridSize, gridSize)
            }
        }
    }
}

// Class color badges
const classColorMap: Record<string, string> = {
    person: 'bg-blue-500',
    car: 'bg-green-500',
    truck: 'bg-emerald-500',
    motorcycle: 'bg-cyan-500',
    dog: 'bg-orange-500',
    cat: 'bg-amber-500',
    fire: 'bg-red-500',
}

// Camera Heatmap Overlay Component with Canvas
function CameraHeatmapOverlay({
    camera,
    selectedClasses,
    days
}: {
    camera: CameraWithStats
    selectedClasses: Set<string>
    days: number
}) {
    const canvasRef = useRef<HTMLCanvasElement>(null)
    const containerRef = useRef<HTMLDivElement>(null)
    const { token } = useAuthStore()

    // Fetch spatial heatmap data for this camera
    const { data: spatialData } = useQuery<SpatialHeatmapData>({
        queryKey: ['spatialHeatmap', camera.id, days, Array.from(selectedClasses).join(',')],
        queryFn: async () => {
            const classesParam = selectedClasses.size > 0 ? Array.from(selectedClasses).join(',') : undefined
            const params = new URLSearchParams({ camera_id: String(camera.id), days: String(days) })
            if (classesParam) params.append('classes', classesParam)
            const response = await api.get(`/events/heatmap/spatial?${params}`)
            return response.data
        },
        refetchInterval: 30000,
        enabled: selectedClasses.size > 0,
    })

    // Draw heatmap when data or canvas changes
    useEffect(() => {
        if (!canvasRef.current || !spatialData?.points) return

        const canvas = canvasRef.current
        const container = containerRef.current
        if (!container) return

        // Set canvas size to match container
        const rect = container.getBoundingClientRect()
        canvas.width = rect.width
        canvas.height = rect.height

        drawHeatmap(canvas, spatialData.points, selectedClasses)
    }, [spatialData, selectedClasses])

    // Resize handler
    useEffect(() => {
        const handleResize = () => {
            if (!canvasRef.current || !containerRef.current || !spatialData) return
            const rect = containerRef.current.getBoundingClientRect()
            canvasRef.current.width = rect.width
            canvasRef.current.height = rect.height
            drawHeatmap(canvasRef.current, spatialData.points, selectedClasses)
        }

        window.addEventListener('resize', handleResize)
        return () => window.removeEventListener('resize', handleResize)
    }, [spatialData, selectedClasses])

    const totalCount = spatialData?.total_detections || 0
    const classCounts = spatialData?.class_counts || {}

    return (
        <div ref={containerRef} className="relative w-full h-full overflow-hidden rounded-xl">
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

            {/* Canvas heatmap overlay */}
            <canvas
                ref={canvasRef}
                className="absolute inset-0 pointer-events-none"
                style={{ mixBlendMode: 'screen' }}
            />

            {/* Stats overlay */}
            <div className="absolute bottom-0 left-0 right-0 bg-gradient-to-t from-black/80 to-transparent p-3">
                <div className="flex items-center justify-between">
                    <span className="text-white font-medium text-sm">{camera.name}</span>
                    {totalCount > 0 && (
                        <div className="flex items-center gap-1 text-xs">
                            <FireIcon className="w-4 h-4 text-orange-400" />
                            <span className="text-orange-400 font-bold">{totalCount}</span>
                        </div>
                    )}
                </div>
                {/* Class breakdown */}
                <div className="flex flex-wrap gap-1 mt-1">
                    {Object.entries(classCounts).slice(0, 4).map(([cls, count]) => (
                        <span key={cls} className={`px-1.5 py-0.5 rounded text-[10px] text-white ${classColorMap[cls] || 'bg-purple-500'}`}>
                            {cls}: {count}
                        </span>
                    ))}
                </div>
            </div>

            {/* Status badge */}
            <div className="absolute top-2 left-2">
                <span className={`px-2 py-1 rounded-full text-xs font-medium ${camera.status === 'online' ? 'bg-green-500' : 'bg-gray-500'
                    } text-white`}>
                    {camera.status}
                </span>
            </div>
        </div>
    )
}

const hours = Array.from({ length: 24 }, (_, i) => i)

export default function Heatmap() {
    const [selectedClasses, setSelectedClasses] = useState<Set<string>>(new Set())
    const [selectedCamera, setSelectedCamera] = useState<number | null>(null)
    const [days, setDays] = useState(7)

    // Fetch user settings to get current detection model
    const { data: settings } = useQuery({
        queryKey: ['settings'],
        queryFn: settingsApi.get,
    })

    // Fetch classes for the current model
    const currentModel = settings?.detection?.model || 'yolov8n'
    const { data: modelClasses } = useQuery({
        queryKey: ['modelClasses', currentModel],
        queryFn: () => systemApi.getModelClasses(currentModel),
        enabled: !!currentModel,
    })

    // Fetch cameras
    const { data: cameras } = useQuery({
        queryKey: ['cameras'],
        queryFn: cameraApi.listCameras,
    })

    // Fetch heatmap data for grid
    const { data: heatmapData, isLoading } = useQuery<HeatmapResponse>({
        queryKey: ['heatmap', days, selectedCamera],
        queryFn: async () => {
            const params = new URLSearchParams({ days: String(days) })
            if (selectedCamera) params.append('camera_id', String(selectedCamera))
            const response = await api.get(`/events/heatmap?${params}`)
            return response.data
        },
        refetchInterval: 30000,
    })

    // Initialize selected classes from model
    useEffect(() => {
        if (modelClasses?.classes && selectedClasses.size === 0) {
            const defaultClasses = ['person', 'car', 'dog', 'cat'].filter(c =>
                modelClasses.classes.includes(c)
            )
            if (defaultClasses.length > 0) {
                setSelectedClasses(new Set(defaultClasses))
            } else if (modelClasses.classes.length > 0) {
                setSelectedClasses(new Set([modelClasses.classes[0]]))
            }
        }
    }, [modelClasses])

    const toggleClass = (className: string) => {
        setSelectedClasses(prev => {
            const newSet = new Set(prev)
            if (newSet.has(className)) newSet.delete(className)
            else newSet.add(className)
            return newSet
        })
    }

    const selectAll = () => {
        if (modelClasses?.classes) setSelectedClasses(new Set(modelClasses.classes))
    }
    const deselectAll = () => setSelectedClasses(new Set())

    // Process grid data
    const { gridData, uniqueDays, maxCount } = useMemo(() => {
        if (!heatmapData?.data) return { gridData: new Map(), uniqueDays: [], maxCount: 0 }
        const filteredData = heatmapData.data.filter(d => selectedClasses.has(d.class_name))
        const aggregated = new Map<string, number>()
        let max = 0
        filteredData.forEach(d => {
            const key = `${d.day}-${d.hour}`
            const current = aggregated.get(key) || 0
            const newCount = current + d.count
            aggregated.set(key, newCount)
            if (newCount > max) max = newCount
        })
        const days = [...new Set(heatmapData.data.map(d => d.day))].sort()
        return { gridData: aggregated, uniqueDays: days, maxCount: max }
    }, [heatmapData, selectedClasses])

    const getIntensity = (count: number) => {
        if (count === 0 || maxCount === 0) return 'bg-white/5'
        const ratio = count / maxCount
        if (ratio < 0.2) return 'bg-cyan-500/30'
        if (ratio < 0.4) return 'bg-green-500/40'
        if (ratio < 0.6) return 'bg-yellow-500/50'
        if (ratio < 0.8) return 'bg-orange-500/60'
        return 'bg-red-500/70'
    }

    const formatHour = (hour: number) => {
        if (hour === 0) return '12am'
        if (hour === 12) return '12pm'
        return hour < 12 ? `${hour}am` : `${hour - 12}pm`
    }

    const getDayDisplay = (day: string) => {
        const date = new Date(day)
        return date.toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric' })
    }

    const availableClasses = modelClasses?.classes || heatmapData?.available_classes || []

    return (
        <div className="p-6 space-y-6">
            {/* Header */}
            <motion.div
                initial={{ opacity: 0, y: -20 }}
                animate={{ opacity: 1, y: 0 }}
                className="flex flex-col sm:flex-row sm:items-center justify-between gap-4"
            >
                <div className="flex items-center gap-3">
                    <div className="p-3 rounded-xl bg-gradient-to-br from-orange-500 to-red-600 shadow-lg shadow-orange-500/30">
                        <FireIcon className="w-6 h-6 text-white" />
                    </div>
                    <div>
                        <h1 className="text-2xl font-bold text-white">Spatial Heatmap</h1>
                        <p className="text-gray-400 text-sm">
                            Model: <span className="text-primary-400">{currentModel}</span>
                        </p>
                    </div>
                </div>

                <div className="flex items-center gap-3">
                    <select
                        value={selectedCamera || ''}
                        onChange={(e) => setSelectedCamera(e.target.value ? Number(e.target.value) : null)}
                        className="px-3 py-2 rounded-xl bg-white/10 border border-white/10 text-white text-sm"
                    >
                        <option value="">All Cameras</option>
                        {cameras?.map(cam => (
                            <option key={cam.id} value={cam.id}>{cam.name}</option>
                        ))}
                    </select>

                    <div className="flex items-center gap-2">
                        <CalendarDaysIcon className="w-5 h-5 text-gray-400" />
                        <select
                            value={days}
                            onChange={(e) => setDays(Number(e.target.value))}
                            className="px-3 py-2 rounded-xl bg-white/10 border border-white/10 text-white text-sm"
                        >
                            <option value={7}>7 days</option>
                            <option value={14}>14 days</option>
                            <option value={30}>30 days</option>
                        </select>
                    </div>
                </div>
            </motion.div>

            {/* Class Selection */}
            <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.1 }}
                className="glass-card p-4 rounded-2xl"
            >
                <div className="flex items-center justify-between mb-3">
                    <div className="flex items-center gap-2">
                        <FunnelIcon className="w-5 h-5 text-primary-400" />
                        <h2 className="text-lg font-semibold text-white">Filter Classes</h2>
                    </div>
                    <div className="flex gap-2">
                        <button onClick={selectAll} className="px-3 py-1.5 text-xs font-medium rounded-lg bg-primary-500/20 text-primary-400 hover:bg-primary-500/30">Select All</button>
                        <button onClick={deselectAll} className="px-3 py-1.5 text-xs font-medium rounded-lg bg-white/10 text-gray-400 hover:bg-white/20">Clear</button>
                    </div>
                </div>
                <div className="flex gap-2 flex-wrap max-h-24 overflow-y-auto">
                    {availableClasses.map((className: string) => (
                        <button
                            key={className}
                            onClick={() => toggleClass(className)}
                            className={`px-3 py-1.5 rounded-lg font-medium text-xs transition-all ${selectedClasses.has(className)
                                ? `${classColorMap[className] || 'bg-purple-500'} text-white`
                                : 'bg-white/10 text-gray-400 hover:bg-white/20'
                                }`}
                        >
                            {className}
                        </button>
                    ))}
                </div>
            </motion.div>

            {/* Camera Grid with Spatial Heatmaps */}
            <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.2 }}
                className="glass-card p-4 rounded-2xl"
            >
                <h2 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
                    <VideoCameraIcon className="w-5 h-5 text-primary-400" />
                    Camera Heatmaps
                    <span className="text-xs text-gray-500 font-normal">(detection intensity by position)</span>
                </h2>

                {cameras && cameras.length > 0 ? (
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                        {cameras.map(camera => (
                            <div key={camera.id} className="aspect-video rounded-xl overflow-hidden border border-white/10">
                                <CameraHeatmapOverlay
                                    camera={camera}
                                    selectedClasses={selectedClasses}
                                    days={days}
                                />
                            </div>
                        ))}
                    </div>
                ) : (
                    <div className="text-center py-12 text-gray-500">
                        <VideoCameraIcon className="w-12 h-12 mx-auto mb-3 opacity-30" />
                        <p>No cameras configured</p>
                    </div>
                )}
            </motion.div>

            {/* Hourly Grid */}
            <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.3 }}
                className="glass-card p-6 rounded-2xl overflow-x-auto"
            >
                <h2 className="text-lg font-semibold text-white mb-4">Hourly Activity</h2>

                {isLoading ? (
                    <div className="h-40 flex items-center justify-center">
                        <div className="w-8 h-8 border-2 border-primary-500 border-t-transparent rounded-full animate-spin" />
                    </div>
                ) : uniqueDays.length === 0 ? (
                    <div className="h-40 flex flex-col items-center justify-center text-gray-500">
                        <ChartBarSquareIcon className="w-12 h-12 mb-3 opacity-30" />
                        <p>No data for selected filters</p>
                    </div>
                ) : (
                    <div className="min-w-[600px]">
                        <div className="flex gap-1 mb-2 ml-20">
                            {hours.map(hour => (
                                <div key={hour} className="w-5 text-[9px] text-gray-500 text-center">
                                    {hour % 6 === 0 ? formatHour(hour) : ''}
                                </div>
                            ))}
                        </div>
                        <div className="space-y-1">
                            {uniqueDays.map(day => (
                                <div key={day} className="flex items-center gap-1">
                                    <div className="w-20 text-xs text-gray-400 text-right pr-2 truncate">
                                        {getDayDisplay(day)}
                                    </div>
                                    {hours.map(hour => {
                                        const count = gridData.get(`${day}-${hour}`) || 0
                                        return (
                                            <div
                                                key={`${day}-${hour}`}
                                                className={`w-5 h-4 rounded-sm ${getIntensity(count)} cursor-pointer relative group`}
                                                title={`${count} detections`}
                                            >
                                                <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-1 px-1.5 py-0.5 rounded bg-dark-400 text-white text-[10px] whitespace-nowrap opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none z-20">
                                                    {count}
                                                </div>
                                            </div>
                                        )
                                    })}
                                </div>
                            ))}
                        </div>
                        <div className="flex items-center justify-end gap-2 mt-3 text-xs text-gray-500">
                            <span>Less</span>
                            {['bg-white/5', 'bg-cyan-500/30', 'bg-green-500/40', 'bg-yellow-500/50', 'bg-orange-500/60', 'bg-red-500/70'].map((c, i) => (
                                <div key={i} className={`w-3 h-3 rounded-sm ${c}`} />
                            ))}
                            <span>More</span>
                        </div>
                    </div>
                )}
            </motion.div>
        </div>
    )
}
