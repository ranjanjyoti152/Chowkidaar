import { useState, useEffect, useRef, useCallback } from 'react'
import { useQuery } from '@tanstack/react-query'
import { motion, AnimatePresence } from 'framer-motion'
import {
    SparklesIcon,

    ArrowPathIcon,
    XMarkIcon,
    ChartBarIcon,
    CameraIcon,
    ClockIcon,
    MagnifyingGlassIcon,
} from '@heroicons/react/24/outline'
import { embeddingsApi, cameraApi, eventApi, EmbeddingNode } from '../services'
import { useAuthStore } from '../store/authStore'

// Severity colors
const severityColors: Record<string, string> = {
    critical: '#ef4444',
    high: '#f59e0b',
    medium: '#3b82f6',
    low: '#22c55e',
}

// Event type colors
const eventTypeColors: Record<string, string> = {
    person_detected: '#3b82f6',
    vehicle_detected: '#8b5cf6',
    animal_detected: '#ec4899',
    intrusion: '#ef4444',
    suspicious: '#f59e0b',
    fire_detected: '#dc2626',
    smoke_detected: '#9ca3af',
    delivery: '#22c55e',
    visitor: '#06b6d4',
    loitering: '#eab308',
    default: '#64748b',
}

// Cluster colors
const clusterColors = ['#3b82f6', '#8b5cf6', '#ec4899', '#f59e0b', '#22c55e', '#06b6d4']

export default function Insights() {
    const canvasRef = useRef<HTMLCanvasElement>(null)
    const containerRef = useRef<HTMLDivElement>(null)
    const [selectedNode, setSelectedNode] = useState<EmbeddingNode | null>(null)
    const [hoveredNode, setHoveredNode] = useState<EmbeddingNode | null>(null)
    const [days, setDays] = useState(7)
    const [limit] = useState(100)
    const [colorBy, setColorBy] = useState<'severity' | 'event_type' | 'cluster'>('severity')
    const [showLinks, setShowLinks] = useState(true)
    const [zoom, setZoom] = useState(1)
    const [pan, setPan] = useState({ x: 0, y: 0 })
    const [isDragging, setIsDragging] = useState(false)
    const [dragStart, setDragStart] = useState({ x: 0, y: 0 })
    const { token } = useAuthStore()

    // Fetch graph data
    const { data: graphData, isLoading, refetch } = useQuery({
        queryKey: ['embeddings-graph', days, limit],
        queryFn: () => embeddingsApi.getGraph({ days, limit }),
    })

    // Fetch stats
    const { data: stats } = useQuery({
        queryKey: ['embeddings-stats'],
        queryFn: () => embeddingsApi.getStats(),
    })

    // Fetch cameras (stored for future camera filter feature)
    useQuery({
        queryKey: ['cameras'],
        queryFn: () => cameraApi.listCameras(),
    })

    // Get node color based on coloring mode
    const getNodeColor = useCallback((node: EmbeddingNode) => {
        if (colorBy === 'severity') {
            return severityColors[node.severity] || severityColors.low
        } else if (colorBy === 'event_type') {
            return eventTypeColors[node.event_type] || eventTypeColors.default
        } else {
            return clusterColors[node.cluster % clusterColors.length]
        }
    }, [colorBy])

    // Draw the visualization
    useEffect(() => {
        if (!canvasRef.current || !graphData) return

        const canvas = canvasRef.current
        const ctx = canvas.getContext('2d')
        if (!ctx) return

        // Set canvas size
        const container = containerRef.current
        if (container) {
            canvas.width = container.clientWidth
            canvas.height = container.clientHeight
        }

        // Clear canvas
        ctx.fillStyle = 'rgba(0, 0, 0, 0)'
        ctx.clearRect(0, 0, canvas.width, canvas.height)

        // Apply zoom and pan
        ctx.save()
        ctx.translate(pan.x, pan.y)
        ctx.scale(zoom, zoom)

        // Draw links
        if (showLinks) {
            ctx.strokeStyle = 'rgba(100, 116, 139, 0.2)'
            ctx.lineWidth = 1 / zoom

            graphData.links.forEach(link => {
                const sourceNode = graphData.nodes.find(n => n.id === link.source)
                const targetNode = graphData.nodes.find(n => n.id === link.target)

                if (sourceNode && targetNode) {
                    ctx.beginPath()
                    ctx.moveTo(sourceNode.x, sourceNode.y)
                    ctx.lineTo(targetNode.x, targetNode.y)
                    ctx.globalAlpha = link.value * 0.5
                    ctx.stroke()
                    ctx.globalAlpha = 1
                }
            })
        }

        // Draw nodes
        graphData.nodes.forEach(node => {
            const isSelected = selectedNode?.id === node.id
            const isHovered = hoveredNode?.id === node.id
            const radius = isSelected ? 12 : isHovered ? 10 : 8

            // Node circle
            ctx.beginPath()
            ctx.arc(node.x, node.y, radius / zoom, 0, Math.PI * 2)
            ctx.fillStyle = getNodeColor(node)
            ctx.fill()

            // Border
            if (isSelected || isHovered) {
                ctx.strokeStyle = '#ffffff'
                ctx.lineWidth = 2 / zoom
                ctx.stroke()
            }

            // Glow effect for selected
            if (isSelected) {
                ctx.shadowColor = getNodeColor(node)
                ctx.shadowBlur = 15
                ctx.beginPath()
                ctx.arc(node.x, node.y, radius / zoom, 0, Math.PI * 2)
                ctx.fill()
                ctx.shadowBlur = 0
            }
        })

        ctx.restore()
    }, [graphData, selectedNode, hoveredNode, zoom, pan, colorBy, showLinks, getNodeColor])

    // Handle canvas mouse events
    const handleCanvasMouseMove = useCallback((e: React.MouseEvent<HTMLCanvasElement>) => {
        if (!graphData || !canvasRef.current) return

        const rect = canvasRef.current.getBoundingClientRect()
        const x = (e.clientX - rect.left - pan.x) / zoom
        const y = (e.clientY - rect.top - pan.y) / zoom

        if (isDragging) {
            setPan({
                x: pan.x + (e.clientX - dragStart.x),
                y: pan.y + (e.clientY - dragStart.y)
            })
            setDragStart({ x: e.clientX, y: e.clientY })
            return
        }

        // Find hovered node
        let found: EmbeddingNode | null = null
        for (const node of graphData.nodes) {
            const dist = Math.sqrt((node.x - x) ** 2 + (node.y - y) ** 2)
            if (dist < 15 / zoom) {
                found = node
                break
            }
        }
        setHoveredNode(found)
        canvasRef.current.style.cursor = found ? 'pointer' : isDragging ? 'grabbing' : 'grab'
    }, [graphData, zoom, pan, isDragging, dragStart])

    const handleCanvasClick = useCallback(() => {
        if (hoveredNode) {
            setSelectedNode(hoveredNode)
        } else {
            setSelectedNode(null)
        }
    }, [hoveredNode])

    const handleMouseDown = useCallback((e: React.MouseEvent) => {
        setIsDragging(true)
        setDragStart({ x: e.clientX, y: e.clientY })
    }, [])

    const handleMouseUp = useCallback(() => {
        setIsDragging(false)
    }, [])

    const handleWheel = useCallback((e: React.WheelEvent) => {
        e.preventDefault()
        const delta = e.deltaY > 0 ? 0.9 : 1.1
        setZoom(z => Math.min(Math.max(z * delta, 0.3), 3))
    }, [])

    return (
        <div className="page-container">
            {/* Header */}
            <div className="page-header">
                <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-purple-500/30 to-pink-500/30 flex items-center justify-center">
                        <SparklesIcon className="w-5 h-5 text-purple-300" />
                    </div>
                    <div>
                        <h1 className="page-title">Event Insights</h1>
                        <p className="text-gray-300 mt-1">Visualize event relationships and patterns</p>
                    </div>
                </div>

                {/* Controls */}
                <div className="flex items-center gap-3">
                    <select
                        value={days}
                        onChange={(e) => setDays(Number(e.target.value))}
                        className="input py-2 px-3"
                    >
                        <option value={1}>Last 24 hours</option>
                        <option value={3}>Last 3 days</option>
                        <option value={7}>Last 7 days</option>
                        <option value={14}>Last 14 days</option>
                        <option value={30}>Last 30 days</option>
                    </select>

                    <select
                        value={colorBy}
                        onChange={(e) => setColorBy(e.target.value as 'severity' | 'event_type' | 'cluster')}
                        className="input py-2 px-3"
                    >
                        <option value="severity">Color by Severity</option>
                        <option value="event_type">Color by Event Type</option>
                        <option value="cluster">Color by Cluster</option>
                    </select>

                    <button
                        onClick={() => setShowLinks(!showLinks)}
                        className={`btn-secondary px-3 py-2 ${showLinks ? 'bg-primary-500/20' : ''}`}
                    >
                        Links {showLinks ? 'On' : 'Off'}
                    </button>

                    <button
                        onClick={() => refetch()}
                        disabled={isLoading}
                        className="btn-secondary px-3 py-2"
                    >
                        <ArrowPathIcon className={`w-4 h-4 ${isLoading ? 'animate-spin' : ''}`} />
                    </button>
                </div>
            </div>

            <div className="flex gap-6 h-[calc(100vh-200px)]">
                {/* Main Canvas */}
                <div
                    ref={containerRef}
                    className="flex-1 glass-card rounded-xl overflow-hidden relative"
                >
                    {isLoading ? (
                        <div className="absolute inset-0 flex items-center justify-center">
                            <ArrowPathIcon className="w-8 h-8 text-primary-400 animate-spin" />
                        </div>
                    ) : graphData?.nodes.length === 0 ? (
                        <div className="absolute inset-0 flex flex-col items-center justify-center text-gray-400">
                            <MagnifyingGlassIcon className="w-12 h-12 mb-4" />
                            <p className="text-lg">No events with summaries found</p>
                            <p className="text-sm mt-2">Events need VLM summaries to appear here</p>
                        </div>
                    ) : (
                        <canvas
                            ref={canvasRef}
                            className="w-full h-full"
                            onMouseMove={handleCanvasMouseMove}
                            onClick={handleCanvasClick}
                            onMouseDown={handleMouseDown}
                            onMouseUp={handleMouseUp}
                            onMouseLeave={handleMouseUp}
                            onWheel={handleWheel}
                        />
                    )}

                    {/* Zoom controls */}
                    <div className="absolute bottom-4 left-4 flex gap-2">
                        <button
                            onClick={() => setZoom(z => Math.min(z * 1.2, 3))}
                            className="btn-secondary px-3 py-2 text-sm"
                        >
                            +
                        </button>
                        <button
                            onClick={() => setZoom(z => Math.max(z / 1.2, 0.3))}
                            className="btn-secondary px-3 py-2 text-sm"
                        >
                            −
                        </button>
                        <button
                            onClick={() => { setZoom(1); setPan({ x: 0, y: 0 }) }}
                            className="btn-secondary px-3 py-2 text-sm"
                        >
                            Reset
                        </button>
                    </div>

                    {/* Hover tooltip */}
                    <AnimatePresence>
                        {hoveredNode && !selectedNode && (
                            <motion.div
                                initial={{ opacity: 0, y: 10 }}
                                animate={{ opacity: 1, y: 0 }}
                                exit={{ opacity: 0 }}
                                className="absolute bottom-4 right-4 glass-card p-4 max-w-sm"
                            >
                                <div className="flex items-center gap-2 mb-2">
                                    <span
                                        className="w-3 h-3 rounded-full"
                                        style={{ backgroundColor: getNodeColor(hoveredNode) }}
                                    />
                                    <span className="text-sm font-medium text-white capitalize">
                                        {hoveredNode.event_type.replace('_', ' ')}
                                    </span>
                                    <span className={`text-xs px-2 py-0.5 rounded-full ${hoveredNode.severity === 'critical' ? 'bg-red-500/20 text-red-400' :
                                        hoveredNode.severity === 'high' ? 'bg-orange-500/20 text-orange-400' :
                                            'bg-blue-500/20 text-blue-400'
                                        }`}>
                                        {hoveredNode.severity}
                                    </span>
                                </div>
                                <p className="text-sm text-gray-300 line-clamp-2">{hoveredNode.summary}</p>
                                <p className="text-xs text-gray-500 mt-2">
                                    {hoveredNode.camera_name} • {new Date(hoveredNode.timestamp).toLocaleString()}
                                </p>
                            </motion.div>
                        )}
                    </AnimatePresence>

                    {/* Legend */}
                    <div className="absolute top-4 left-4 glass-card p-3">
                        <p className="text-xs text-gray-400 mb-2 font-medium">
                            {colorBy === 'severity' ? 'Severity' : colorBy === 'event_type' ? 'Event Type' : 'Clusters'}
                        </p>
                        <div className="flex flex-wrap gap-2">
                            {colorBy === 'severity' && Object.entries(severityColors).map(([key, color]) => (
                                <div key={key} className="flex items-center gap-1">
                                    <span className="w-2 h-2 rounded-full" style={{ backgroundColor: color }} />
                                    <span className="text-xs text-gray-400 capitalize">{key}</span>
                                </div>
                            ))}
                            {colorBy === 'cluster' && graphData?.clusters.map((cluster, i) => (
                                <div key={cluster.id} className="flex items-center gap-1">
                                    <span className="w-2 h-2 rounded-full" style={{ backgroundColor: clusterColors[i % clusterColors.length] }} />
                                    <span className="text-xs text-gray-400">{cluster.dominant_type.replace('_', ' ')} ({cluster.size})</span>
                                </div>
                            ))}
                        </div>
                    </div>
                </div>

                {/* Sidebar - Selected Event Details */}
                <AnimatePresence>
                    {selectedNode && (
                        <motion.div
                            initial={{ width: 0, opacity: 0 }}
                            animate={{ width: 350, opacity: 1 }}
                            exit={{ width: 0, opacity: 0 }}
                            className="glass-card rounded-xl overflow-hidden"
                        >
                            <div className="p-4 h-full overflow-y-auto">
                                {/* Close button */}
                                <button
                                    onClick={() => setSelectedNode(null)}
                                    className="absolute top-4 right-4 p-1 rounded-lg hover:bg-white/10"
                                >
                                    <XMarkIcon className="w-5 h-5 text-gray-400" />
                                </button>

                                {/* Thumbnail */}
                                {selectedNode.thumbnail_path && (
                                    <div className="mb-4 rounded-xl overflow-hidden">
                                        <img
                                            src={`${eventApi.getThumbnailUrl(selectedNode.id)}?token=${token}`}
                                            alt="Event thumbnail"
                                            className="w-full h-48 object-cover bg-white/5"
                                            onError={(e) => {
                                                (e.target as HTMLImageElement).style.display = 'none'
                                            }}
                                        />
                                    </div>
                                )}

                                {/* Event type and severity */}
                                <div className="flex items-center gap-2 mb-3">
                                    <span
                                        className="w-3 h-3 rounded-full"
                                        style={{ backgroundColor: getNodeColor(selectedNode) }}
                                    />
                                    <span className="text-lg font-semibold text-white capitalize">
                                        {selectedNode.event_type.replace('_', ' ')}
                                    </span>
                                </div>

                                <div className="flex gap-2 mb-4">
                                    <span className={`text-xs px-2 py-1 rounded-full ${selectedNode.severity === 'critical' ? 'bg-red-500/20 text-red-400' :
                                        selectedNode.severity === 'high' ? 'bg-orange-500/20 text-orange-400' :
                                            selectedNode.severity === 'medium' ? 'bg-blue-500/20 text-blue-400' :
                                                'bg-green-500/20 text-green-400'
                                        }`}>
                                        {selectedNode.severity}
                                    </span>
                                    <span className="text-xs px-2 py-1 rounded-full bg-purple-500/20 text-purple-400">
                                        Cluster {selectedNode.cluster + 1}
                                    </span>
                                </div>

                                {/* Summary */}
                                <div className="mb-4">
                                    <p className="text-sm text-gray-400 mb-1">Summary</p>
                                    <p className="text-sm text-gray-200">{selectedNode.summary}</p>
                                </div>

                                {/* Details */}
                                <div className="space-y-2 text-sm">
                                    <div className="flex items-center gap-2 text-gray-400">
                                        <CameraIcon className="w-4 h-4" />
                                        <span>{selectedNode.camera_name}</span>
                                    </div>
                                    <div className="flex items-center gap-2 text-gray-400">
                                        <ClockIcon className="w-4 h-4" />
                                        <span>{new Date(selectedNode.timestamp).toLocaleString()}</span>
                                    </div>
                                </div>

                                {/* Detected objects */}
                                {selectedNode.detected_objects && selectedNode.detected_objects.length > 0 && (
                                    <div className="mt-4">
                                        <p className="text-sm text-gray-400 mb-2">Detected Objects</p>
                                        <div className="flex flex-wrap gap-1">
                                            {(selectedNode.detected_objects as Array<{ class_name?: string }>).slice(0, 10).map((obj, i) => (
                                                <span key={i} className="text-xs px-2 py-1 rounded-full bg-white/10 text-gray-300">
                                                    {obj.class_name || 'object'}
                                                </span>
                                            ))}
                                        </div>
                                    </div>
                                )}

                                {/* View full event button */}
                                <button
                                    onClick={() => window.open(`/events?id=${selectedNode.id}`, '_blank')}
                                    className="w-full mt-6 btn-primary py-2"
                                >
                                    View Full Event
                                </button>
                            </div>
                        </motion.div>
                    )}
                </AnimatePresence>

                {/* Stats sidebar when no node selected */}
                {!selectedNode && stats && (
                    <div className="w-64 glass-card rounded-xl p-4">
                        <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
                            <ChartBarIcon className="w-5 h-5 text-primary-400" />
                            Statistics
                        </h3>

                        <div className="space-y-4">
                            <div>
                                <p className="text-sm text-gray-400">Total Indexed Events</p>
                                <p className="text-2xl font-bold text-white">{stats.total_indexed}</p>
                            </div>

                            <div>
                                <p className="text-sm text-gray-400">Displayed Events</p>
                                <p className="text-2xl font-bold text-primary-400">{graphData?.nodes.length || 0}</p>
                            </div>

                            <div>
                                <p className="text-sm text-gray-400">Clusters Found</p>
                                <p className="text-2xl font-bold text-purple-400">{graphData?.clusters.length || 0}</p>
                            </div>

                            <div>
                                <p className="text-sm text-gray-400 mb-2">Event Types</p>
                                <div className="space-y-1">
                                    {Object.entries(stats.event_type_distribution).slice(0, 5).map(([type, count]) => (
                                        <div key={type} className="flex justify-between text-sm">
                                            <span className="text-gray-400 capitalize">{type.replace('_', ' ')}</span>
                                            <span className="text-white">{count}</span>
                                        </div>
                                    ))}
                                </div>
                            </div>

                            <div>
                                <p className="text-sm text-gray-400 mb-2">Cameras</p>
                                <div className="space-y-1">
                                    {Object.entries(stats.camera_distribution).slice(0, 5).map(([name, count]) => (
                                        <div key={name} className="flex justify-between text-sm">
                                            <span className="text-gray-400 truncate max-w-[120px]">{name}</span>
                                            <span className="text-white">{count}</span>
                                        </div>
                                    ))}
                                </div>
                            </div>

                            <div className="pt-4 border-t border-white/10">
                                <p className="text-xs text-gray-500">
                                    Model: {stats.model}
                                </p>
                                <p className="text-xs text-gray-500">
                                    Dimensions: {stats.embedding_dimension}
                                </p>
                            </div>
                        </div>
                    </div>
                )}
            </div>
        </div>
    )
}
