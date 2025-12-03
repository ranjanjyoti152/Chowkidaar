import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { motion } from 'framer-motion'
import { format } from 'date-fns'
import {
  FunnelIcon,
  CheckIcon,
  EyeIcon,
  TrashIcon,
  ArrowPathIcon,
  XMarkIcon,
} from '@heroicons/react/24/outline'
import { eventApi } from '../services'
import type { EventWithCamera, EventSeverity, EventType } from '../types'
import toast from 'react-hot-toast'

const severityColors: Record<EventSeverity, string> = {
  low: 'bg-blue-500/20 text-blue-400 border-blue-500/30',
  medium: 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30',
  high: 'bg-orange-500/20 text-orange-400 border-orange-500/30',
  critical: 'bg-red-500/20 text-red-400 border-red-500/30',
}

const eventTypeLabels: Record<EventType, string> = {
  person_detected: 'Person Detected',
  vehicle_detected: 'Vehicle Detected',
  fire_detected: 'Fire Detected',
  smoke_detected: 'Smoke Detected',
  animal_detected: 'Animal Detected',
  motion_detected: 'Motion Detected',
  intrusion: 'Intrusion',
  loitering: 'Loitering',
  custom: 'Custom',
}

export default function Events() {
  const [filters, setFilters] = useState({
    severity: '',
    event_type: '',
    is_acknowledged: '',
  })
  const [selectedEvent, setSelectedEvent] = useState<EventWithCamera | null>(null)
  const queryClient = useQueryClient()

  const { data: events, isLoading } = useQuery({
    queryKey: ['events', filters],
    queryFn: () =>
      eventApi.listEvents({
        severity: filters.severity || undefined,
        event_type: filters.event_type || undefined,
        is_acknowledged: filters.is_acknowledged ? filters.is_acknowledged === 'true' : undefined,
        limit: 50,
      }),
  })

  const { data: stats } = useQuery({
    queryKey: ['eventStats'],
    queryFn: eventApi.getStats,
  })

  const acknowledgeMutation = useMutation({
    mutationFn: (id: number) => eventApi.updateEvent(id, { is_acknowledged: true }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['events'] })
      toast.success('Event acknowledged')
    },
  })

  const acknowledgeAllMutation = useMutation({
    mutationFn: () => eventApi.acknowledgeAll(),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['events'] })
      toast.success('All events acknowledged')
    },
  })

  const deleteMutation = useMutation({
    mutationFn: eventApi.deleteEvent,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['events'] })
      setSelectedEvent(null)
      toast.success('Event deleted')
    },
  })

  const regenerateMutation = useMutation({
    mutationFn: eventApi.regenerateSummary,
    onSuccess: (event) => {
      queryClient.invalidateQueries({ queryKey: ['events'] })
      setSelectedEvent({ ...selectedEvent!, summary: event.summary })
      toast.success('Summary regenerated')
    },
  })

  return (
    <div className="page-container">
      {/* Header */}
      <div className="page-header">
        <div>
          <h1 className="page-title">Events</h1>
          <p className="text-gray-400 mt-1">
            {stats?.total_events || 0} total events • {stats?.events_today || 0} today
          </p>
        </div>
        <div className="flex gap-3">
          <button
            onClick={() => acknowledgeAllMutation.mutate()}
            className="btn-secondary"
          >
            <CheckIcon className="w-5 h-5" />
            Acknowledge All
          </button>
        </div>
      </div>

      {/* Filters */}
      <div className="glass-card p-4 flex flex-wrap gap-4">
        <div className="flex items-center gap-2">
          <FunnelIcon className="w-5 h-5 text-gray-400" />
          <span className="text-sm text-gray-400">Filters:</span>
        </div>
        
        <select
          value={filters.severity}
          onChange={(e) => setFilters({ ...filters, severity: e.target.value })}
          className="input py-2 w-auto"
        >
          <option value="">All Severities</option>
          <option value="critical">Critical</option>
          <option value="high">High</option>
          <option value="medium">Medium</option>
          <option value="low">Low</option>
        </select>

        <select
          value={filters.event_type}
          onChange={(e) => setFilters({ ...filters, event_type: e.target.value })}
          className="input py-2 w-auto"
        >
          <option value="">All Types</option>
          <option value="person_detected">Person</option>
          <option value="vehicle_detected">Vehicle</option>
          <option value="fire_detected">Fire</option>
          <option value="smoke_detected">Smoke</option>
          <option value="animal_detected">Animal</option>
        </select>

        <select
          value={filters.is_acknowledged}
          onChange={(e) => setFilters({ ...filters, is_acknowledged: e.target.value })}
          className="input py-2 w-auto"
        >
          <option value="">All Status</option>
          <option value="false">Unacknowledged</option>
          <option value="true">Acknowledged</option>
        </select>
      </div>

      {/* Events List */}
      <div className="glass-card overflow-hidden">
        {isLoading ? (
          <div className="p-6 space-y-4">
            {[1, 2, 3, 4, 5].map((i) => (
              <div key={i} className="h-20 skeleton" />
            ))}
          </div>
        ) : events && events.length > 0 ? (
          <div className="divide-y divide-white/10">
            {events.map((event) => (
              <motion.div
                key={event.id}
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                className={`p-4 hover:bg-white/5 cursor-pointer transition-colors ${
                  !event.is_acknowledged ? 'border-l-2 border-primary-500' : ''
                }`}
                onClick={() => setSelectedEvent(event)}
              >
                <div className="flex items-center gap-4">
                  {/* Thumbnail */}
                  <div className="w-24 h-16 rounded-lg bg-dark-400 overflow-hidden flex-shrink-0">
                    {event.thumbnail_path && (
                      <img
                        src={`/api/v1/events/${event.id}/thumbnail`}
                        alt="Event thumbnail"
                        className="w-full h-full object-cover"
                      />
                    )}
                  </div>

                  {/* Info */}
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1">
                      <h3 className="text-white font-medium">
                        {eventTypeLabels[event.event_type] || event.event_type}
                      </h3>
                      <span className={`badge border ${severityColors[event.severity]}`}>
                        {event.severity}
                      </span>
                      {!event.is_acknowledged && (
                        <span className="badge-warning">New</span>
                      )}
                    </div>
                    <p className="text-sm text-gray-400 truncate">
                      {event.camera_name} • {format(new Date(event.timestamp), 'MMM d, yyyy HH:mm:ss')}
                    </p>
                    {event.summary && (
                      <p className="text-sm text-gray-500 truncate mt-1">{event.summary}</p>
                    )}
                  </div>

                  {/* Actions */}
                  <div className="flex items-center gap-2">
                    {!event.is_acknowledged && (
                      <button
                        onClick={(e) => {
                          e.stopPropagation()
                          acknowledgeMutation.mutate(event.id)
                        }}
                        className="p-2 rounded-lg text-gray-400 hover:text-green-400 hover:bg-green-500/10"
                        title="Acknowledge"
                      >
                        <CheckIcon className="w-5 h-5" />
                      </button>
                    )}
                    <button
                      onClick={(e) => {
                        e.stopPropagation()
                        setSelectedEvent(event)
                      }}
                      className="p-2 rounded-lg text-gray-400 hover:text-white hover:bg-white/10"
                      title="View Details"
                    >
                      <EyeIcon className="w-5 h-5" />
                    </button>
                  </div>
                </div>
              </motion.div>
            ))}
          </div>
        ) : (
          <div className="p-12 text-center">
            <p className="text-gray-400">No events found</p>
          </div>
        )}
      </div>

      {/* Event Detail Modal */}
      {selectedEvent && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm"
          onClick={() => setSelectedEvent(null)}
        >
          <motion.div
            initial={{ scale: 0.95, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            onClick={(e) => e.stopPropagation()}
            className="glass-card w-full max-w-2xl max-h-[90vh] overflow-y-auto"
          >
            {/* Header */}
            <div className="flex items-center justify-between p-4 border-b border-white/10">
              <div>
                <h2 className="text-xl font-semibold text-white">
                  {eventTypeLabels[selectedEvent.event_type]}
                </h2>
                <p className="text-sm text-gray-400">
                  {selectedEvent.camera_name} • {format(new Date(selectedEvent.timestamp), 'PPpp')}
                </p>
              </div>
              <button
                onClick={() => setSelectedEvent(null)}
                className="text-gray-400 hover:text-white"
              >
                <XMarkIcon className="w-6 h-6" />
              </button>
            </div>

            {/* Content */}
            <div className="p-4 space-y-4">
              {/* Frame */}
              {selectedEvent.frame_path && (
                <div className="aspect-video rounded-xl overflow-hidden bg-dark-400">
                  <img
                    src={`/api/v1/events/${selectedEvent.id}/frame`}
                    alt="Event frame"
                    className="w-full h-full object-contain"
                  />
                </div>
              )}

              {/* Badges */}
              <div className="flex flex-wrap gap-2">
                <span className={`badge border ${severityColors[selectedEvent.severity]}`}>
                  {selectedEvent.severity} severity
                </span>
                <span className="badge-primary">
                  {(selectedEvent.confidence_score * 100).toFixed(0)}% confidence
                </span>
                {selectedEvent.is_acknowledged ? (
                  <span className="badge-success">Acknowledged</span>
                ) : (
                  <span className="badge-warning">Unacknowledged</span>
                )}
              </div>

              {/* Summary */}
              {selectedEvent.summary && (
                <div className="glass-card p-4">
                  <div className="flex items-center justify-between mb-2">
                    <h3 className="text-sm font-medium text-gray-400">AI Summary</h3>
                    <button
                      onClick={() => regenerateMutation.mutate(selectedEvent.id)}
                      disabled={regenerateMutation.isPending}
                      className="text-xs text-primary-400 hover:text-primary-300 flex items-center gap-1"
                    >
                      <ArrowPathIcon className={`w-4 h-4 ${regenerateMutation.isPending ? 'animate-spin' : ''}`} />
                      Regenerate
                    </button>
                  </div>
                  <p className="text-white">{selectedEvent.summary}</p>
                </div>
              )}

              {/* Detected Objects */}
              {selectedEvent.detected_objects.objects?.length > 0 && (
                <div>
                  <h3 className="text-sm font-medium text-gray-400 mb-2">Detected Objects</h3>
                  <div className="flex flex-wrap gap-2">
                    {selectedEvent.detected_objects.objects.map((obj, i) => (
                      <span key={i} className="badge-primary">
                        {obj.class_name} ({(obj.confidence * 100).toFixed(0)}%)
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>

            {/* Actions */}
            <div className="flex gap-3 p-4 border-t border-white/10">
              {!selectedEvent.is_acknowledged && (
                <button
                  onClick={() => {
                    acknowledgeMutation.mutate(selectedEvent.id)
                    setSelectedEvent({ ...selectedEvent, is_acknowledged: true })
                  }}
                  className="btn-primary flex-1"
                >
                  <CheckIcon className="w-5 h-5" />
                  Acknowledge
                </button>
              )}
              <button
                onClick={() => {
                  if (confirm('Delete this event?')) {
                    deleteMutation.mutate(selectedEvent.id)
                  }
                }}
                className="btn-danger"
              >
                <TrashIcon className="w-5 h-5" />
                Delete
              </button>
            </div>
          </motion.div>
        </motion.div>
      )}
    </div>
  )
}
