import { useState, useRef, useEffect } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { motion, AnimatePresence } from 'framer-motion'
import { format } from 'date-fns'
import {
  ChatBubbleLeftRightIcon,
  PaperAirplaneIcon,
  TrashIcon,
  SparklesIcon,
  PlusIcon,
  ClockIcon,
  PhotoIcon,
  UserIcon,
  MagnifyingGlassIcon,
  ClipboardDocumentIcon,
  CheckIcon,
  ShieldCheckIcon,
  CameraIcon,
  BellAlertIcon,
  ChartBarIcon,
  XMarkIcon,
  Bars3Icon,
} from '@heroicons/react/24/outline'
import { assistantApi } from '../services'
import { useAuthStore } from '../store/authStore'
import type { ChatSession, ChatMessage, RelatedEventInfo } from '../types'
import toast from 'react-hot-toast'

// Clean markdown and extra LLM formatting from response
const cleanResponse = (text: string): string => {
  if (!text) return ''
  return text
    .replace(/\*\*/g, '')
    .replace(/\*/g, '')
    .replace(/^#+\s*/gm, '')
    .replace(/^[-•]\s*/gm, '• ')
    .replace(/^\d+\.\s*/gm, (match) => match)
    .replace(/\n{3,}/g, '\n\n')
    .replace(/`([^`]+)`/g, '$1')
    .trim()
}

// Extended message type to include events with images
interface ExtendedChatMessage extends ChatMessage {
  events_with_images?: RelatedEventInfo[]
}

// Quick action cards
const quickActions = [
  {
    icon: ShieldCheckIcon,
    title: 'Security Summary',
    description: "What happened today?",
    query: "Give me a summary of today's security events"
  },
  {
    icon: BellAlertIcon,
    title: 'Recent Alerts',
    description: 'Check latest alerts',
    query: "Show me the most recent high-priority alerts"
  },
  {
    icon: CameraIcon,
    title: 'Camera Status',
    description: 'Check all cameras',
    query: "What's the status of all cameras?"
  },
  {
    icon: ChartBarIcon,
    title: 'Activity Patterns',
    description: 'Analyze trends',
    query: "What are the activity patterns this week?"
  }
]

export default function Assistant() {
  const [input, setInput] = useState('')
  const [currentSessionId, setCurrentSessionId] = useState<number | null>(null)
  const [messages, setMessages] = useState<ExtendedChatMessage[]>([])
  const [searchTerm, setSearchTerm] = useState('')
  const [copiedId, setCopiedId] = useState<number | null>(null)
  const [showDeleteConfirm, setShowDeleteConfirm] = useState<number | null>(null)
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLTextAreaElement>(null)
  const queryClient = useQueryClient()
  const { token } = useAuthStore()

  const { data: sessions } = useQuery({
    queryKey: ['chatSessions'],
    queryFn: assistantApi.listSessions,
  })

  const { data: suggestions } = useQuery({
    queryKey: ['chatSuggestions'],
    queryFn: assistantApi.getSuggestions,
  })

  const { data: sessionDetail, refetch: refetchSession } = useQuery({
    queryKey: ['chatSession', currentSessionId],
    queryFn: () => currentSessionId ? assistantApi.getSession(currentSessionId) : null,
    enabled: !!currentSessionId,
  })

  useEffect(() => {
    if (sessionDetail?.messages) {
      setMessages(sessionDetail.messages)
    }
  }, [sessionDetail])

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  // Close sidebar when selecting session on mobile
  useEffect(() => {
    if (currentSessionId && window.innerWidth < 1024) {
      setSidebarOpen(false)
    }
  }, [currentSessionId])

  // Filter sessions based on search
  const filteredSessions = sessions?.filter(session =>
    session.title?.toLowerCase().includes(searchTerm.toLowerCase())
  ) || []

  const chatMutation = useMutation({
    mutationFn: assistantApi.chat,
    onMutate: (data) => {
      const userMessage: ExtendedChatMessage = {
        id: Date.now(),
        role: 'user',
        content: data.message,
        created_at: new Date().toISOString(),
      }
      setMessages((prev) => [...prev, userMessage])
    },
    onSuccess: (response) => {
      const relevantImages = response.events_with_images?.slice(0, 4) || []
      const assistantMessage: ExtendedChatMessage = {
        id: Date.now() + 1,
        role: 'assistant',
        content: response.message,
        created_at: new Date().toISOString(),
        events_with_images: relevantImages.length > 0 ? relevantImages : undefined,
      }
      setMessages((prev) => [...prev, assistantMessage])

      if (response.session_id && !currentSessionId) {
        setCurrentSessionId(response.session_id)
      }
      queryClient.invalidateQueries({ queryKey: ['chatSessions'] })
    },
    onError: () => {
      toast.error('Failed to get response')
      setMessages((prev) => prev.slice(0, -1))
    },
  })

  const deleteSessionMutation = useMutation({
    mutationFn: assistantApi.deleteSession,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['chatSessions'] })
      if (currentSessionId) {
        setCurrentSessionId(null)
        setMessages([])
      }
      setShowDeleteConfirm(null)
      toast.success('Session deleted')
    },
  })

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!input.trim() || chatMutation.isPending) return

    chatMutation.mutate({
      message: input.trim(),
      session_id: currentSessionId || undefined,
    })
    setInput('')
  }

  const handleQuickAction = (query: string) => {
    setInput(query)
    inputRef.current?.focus()
  }

  const handleCopyMessage = async (message: ExtendedChatMessage) => {
    try {
      await navigator.clipboard.writeText(message.content)
      setCopiedId(message.id)
      setTimeout(() => setCopiedId(null), 2000)
      toast.success('Copied to clipboard')
    } catch {
      toast.error('Failed to copy')
    }
  }

  const startNewChat = () => {
    setCurrentSessionId(null)
    setMessages([])
    setSidebarOpen(false)
    inputRef.current?.focus()
  }

  const selectSession = (session: ChatSession) => {
    setCurrentSessionId(session.id)
    refetchSession()
  }

  return (
    <div className="page-container h-[calc(100vh-4rem)] sm:h-[calc(100vh-6rem)] lg:h-[calc(100vh-8rem)] p-2 sm:p-4 lg:p-6">
      <div className="flex gap-2 sm:gap-4 lg:gap-6 h-full relative">

        {/* Mobile Sidebar Overlay */}
        <AnimatePresence>
          {sidebarOpen && (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="fixed inset-0 bg-black/60 backdrop-blur-sm z-40 lg:hidden"
              onClick={() => setSidebarOpen(false)}
            />
          )}
        </AnimatePresence>

        {/* Sidebar - Sessions */}
        <motion.div
          initial={{ opacity: 0, x: -20 }}
          animate={{ opacity: 1, x: 0 }}
          className={`
            fixed lg:relative inset-y-0 left-0 z-50 lg:z-auto
            w-72 sm:w-80 lg:w-72 xl:w-80
            flex-shrink-0 flex flex-col gap-3 lg:gap-4
            bg-dark-500 lg:bg-transparent p-3 lg:p-0
            transform transition-transform duration-300 ease-in-out
            ${sidebarOpen ? 'translate-x-0' : '-translate-x-full lg:translate-x-0'}
          `}
        >
          {/* Mobile close button */}
          <button
            onClick={() => setSidebarOpen(false)}
            className="lg:hidden absolute top-3 right-3 p-2 rounded-lg text-gray-400 hover:text-white hover:bg-white/10"
          >
            <XMarkIcon className="w-5 h-5" />
          </button>

          <button onClick={startNewChat} className="btn-primary w-full group mt-8 lg:mt-0">
            <PlusIcon className="w-5 h-5 group-hover:rotate-90 transition-transform duration-300" />
            <span className="hidden sm:inline">New Conversation</span>
            <span className="sm:hidden">New Chat</span>
          </button>

          <div className="glass-card flex-1 overflow-hidden flex flex-col">
            <div className="p-3 lg:p-4 border-b border-white/10">
              <div className="relative">
                <MagnifyingGlassIcon className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-gray-500" />
                <input
                  type="text"
                  placeholder="Search..."
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                  className="w-full pl-9 pr-4 py-2 text-sm rounded-lg bg-dark-400/50 border border-white/10 focus:border-primary-500/50 focus:outline-none text-white placeholder-gray-500"
                />
              </div>
            </div>

            <div className="flex-1 overflow-y-auto p-2 lg:p-3 space-y-2 scrollbar-hide">
              <AnimatePresence>
                {filteredSessions?.map((session, index) => (
                  <motion.div
                    key={session.id}
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, x: -20 }}
                    transition={{ delay: index * 0.05 }}
                    className="relative group"
                  >
                    <button
                      onClick={() => selectSession(session)}
                      className={`w-full text-left p-2.5 lg:p-3 rounded-xl transition-all duration-200 ${currentSessionId === session.id
                          ? 'bg-gradient-to-r from-primary-500/20 to-primary-500/10 border border-primary-500/30'
                          : 'hover:bg-white/5 border border-transparent'
                        }`}
                    >
                      <div className="flex items-start gap-2 lg:gap-3">
                        <div className={`w-7 h-7 lg:w-8 lg:h-8 rounded-lg flex items-center justify-center flex-shrink-0 ${currentSessionId === session.id
                            ? 'bg-primary-500/30'
                            : 'bg-dark-400/50'
                          }`}>
                          <ChatBubbleLeftRightIcon className={`w-3.5 h-3.5 lg:w-4 lg:h-4 ${currentSessionId === session.id ? 'text-primary-300' : 'text-gray-500'
                            }`} />
                        </div>
                        <div className="flex-1 min-w-0">
                          <p className={`text-sm font-medium truncate ${currentSessionId === session.id ? 'text-primary-200' : 'text-gray-300'
                            }`}>
                            {session.title || 'New Chat'}
                          </p>
                          <p className="text-[10px] lg:text-xs text-gray-500 mt-0.5 lg:mt-1 flex items-center gap-1">
                            <ClockIcon className="w-2.5 h-2.5 lg:w-3 lg:h-3" />
                            {format(new Date(session.created_at), 'MMM d, HH:mm')}
                          </p>
                        </div>
                      </div>
                    </button>

                    {/* Delete button */}
                    <button
                      onClick={(e) => {
                        e.stopPropagation()
                        setShowDeleteConfirm(session.id)
                      }}
                      className="absolute right-2 top-1/2 -translate-y-1/2 p-1.5 rounded-lg opacity-0 group-hover:opacity-100 transition-opacity text-gray-500 hover:text-red-400 hover:bg-red-500/10"
                    >
                      <TrashIcon className="w-4 h-4" />
                    </button>

                    {/* Delete confirmation */}
                    <AnimatePresence>
                      {showDeleteConfirm === session.id && (
                        <motion.div
                          initial={{ opacity: 0, scale: 0.9 }}
                          animate={{ opacity: 1, scale: 1 }}
                          exit={{ opacity: 0, scale: 0.9 }}
                          className="absolute inset-0 bg-dark-300/95 backdrop-blur-sm rounded-xl flex items-center justify-center gap-2 z-10"
                        >
                          <button
                            onClick={() => deleteSessionMutation.mutate(session.id)}
                            className="px-3 py-1.5 rounded-lg bg-red-500/20 text-red-400 text-xs font-medium hover:bg-red-500/30"
                          >
                            Delete
                          </button>
                          <button
                            onClick={() => setShowDeleteConfirm(null)}
                            className="px-3 py-1.5 rounded-lg bg-white/10 text-gray-400 text-xs font-medium hover:bg-white/20"
                          >
                            Cancel
                          </button>
                        </motion.div>
                      )}
                    </AnimatePresence>
                  </motion.div>
                ))}
              </AnimatePresence>

              {(!filteredSessions || filteredSessions.length === 0) && (
                <div className="text-center py-6 lg:py-8">
                  <ChatBubbleLeftRightIcon className="w-8 h-8 lg:w-10 lg:h-10 text-gray-600 mx-auto mb-2 lg:mb-3" />
                  <p className="text-xs lg:text-sm text-gray-500">
                    {searchTerm ? 'No matching chats' : 'No chat history'}
                  </p>
                </div>
              )}
            </div>
          </div>
        </motion.div>

        {/* Main Chat Area */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="flex-1 flex flex-col glass-card overflow-hidden relative min-w-0"
        >
          {/* Ambient glow effects - hidden on mobile for performance */}
          <div className="hidden lg:block absolute top-0 left-1/4 w-96 h-96 bg-primary-500/10 rounded-full blur-3xl pointer-events-none" />
          <div className="hidden lg:block absolute bottom-0 right-1/4 w-96 h-96 bg-blue-500/10 rounded-full blur-3xl pointer-events-none" />

          {/* Header */}
          <div className="relative flex items-center justify-between p-3 sm:p-4 lg:p-5 border-b border-white/10 bg-dark-300/50 backdrop-blur-xl z-10">
            <div className="flex items-center gap-2 sm:gap-3 lg:gap-4">
              {/* Mobile menu button */}
              <button
                onClick={() => setSidebarOpen(true)}
                className="lg:hidden p-2 rounded-xl text-gray-400 hover:text-white hover:bg-white/10"
              >
                <Bars3Icon className="w-5 h-5" />
              </button>

              <div className="relative">
                <div className="w-10 h-10 sm:w-11 sm:h-11 lg:w-12 lg:h-12 rounded-xl lg:rounded-2xl bg-gradient-to-br from-primary-400 via-primary-500 to-blue-600 flex items-center justify-center shadow-lg shadow-primary-500/30">
                  <SparklesIcon className="w-5 h-5 sm:w-5 sm:h-5 lg:w-6 lg:h-6 text-white" />
                </div>
                <span className="absolute -bottom-0.5 -right-0.5 lg:-bottom-1 lg:-right-1 w-3 h-3 lg:w-4 lg:h-4 bg-green-500 rounded-full border-2 border-dark-300 animate-pulse" />
              </div>
              <div>
                <h1 className="text-base sm:text-lg font-semibold text-white flex items-center gap-2">
                  <span className="hidden xs:inline">Chowkidaar</span> AI
                  <span className="hidden sm:inline px-2 py-0.5 rounded-full text-[10px] font-medium bg-primary-500/20 text-primary-300 border border-primary-500/30">
                    Online
                  </span>
                </h1>
                <p className="hidden sm:block text-xs lg:text-sm text-gray-400">
                  Your intelligent security assistant
                </p>
              </div>
            </div>

            {currentSessionId && (
              <button
                onClick={() => setShowDeleteConfirm(currentSessionId)}
                className="p-2 lg:p-2.5 rounded-xl text-gray-400 hover:text-red-400 hover:bg-red-500/10 transition-colors"
                title="Delete Chat"
              >
                <TrashIcon className="w-5 h-5" />
              </button>
            )}
          </div>

          {/* Messages */}
          <div className="flex-1 overflow-y-auto p-3 sm:p-4 lg:p-6 space-y-4 lg:space-y-6 relative z-10">
            {messages.length === 0 ? (
              <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                className="h-full flex flex-col items-center justify-center text-center px-2"
              >
                {/* Animated Icon */}
                <motion.div
                  animate={{
                    y: [0, -10, 0],
                    rotate: [0, 5, -5, 0]
                  }}
                  transition={{
                    duration: 4,
                    repeat: Infinity,
                    ease: "easeInOut"
                  }}
                  className="relative mb-4 lg:mb-6"
                >
                  <div className="w-16 h-16 sm:w-20 sm:h-20 lg:w-24 lg:h-24 rounded-2xl lg:rounded-3xl bg-gradient-to-br from-primary-400 via-primary-500 to-blue-600 flex items-center justify-center shadow-2xl shadow-primary-500/40">
                    <SparklesIcon className="w-8 h-8 sm:w-10 sm:h-10 lg:w-12 lg:h-12 text-white" />
                  </div>
                  <div className="absolute -inset-4 bg-primary-500/20 rounded-3xl blur-xl -z-10" />
                </motion.div>

                <h2 className="text-lg sm:text-xl lg:text-2xl font-bold text-white mb-2 lg:mb-3">
                  How can I help you today?
                </h2>
                <p className="text-xs sm:text-sm lg:text-base text-gray-400 max-w-lg mb-6 lg:mb-8 px-4">
                  I'm your AI-powered security assistant. Ask me about events, alerts,
                  activity patterns, or anything related to your surveillance system.
                </p>

                {/* Quick Actions Grid */}
                <div className="w-full max-w-2xl px-2">
                  <p className="text-xs lg:text-sm text-gray-500 mb-3 lg:mb-4">Quick actions</p>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 lg:gap-3">
                    {quickActions.map((action, i) => (
                      <motion.button
                        key={i}
                        initial={{ opacity: 0, y: 10 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ delay: i * 0.1 }}
                        onClick={() => handleQuickAction(action.query)}
                        className="group p-3 lg:p-4 rounded-xl lg:rounded-2xl text-left transition-all duration-300 bg-dark-400/50 hover:bg-dark-400/80 border border-white/5 hover:border-primary-500/30 hover:shadow-lg hover:shadow-primary-500/10"
                      >
                        <div className="flex items-start gap-2 lg:gap-3">
                          <div className="w-8 h-8 lg:w-10 lg:h-10 rounded-lg lg:rounded-xl bg-gradient-to-br from-primary-500/20 to-blue-500/20 flex items-center justify-center group-hover:from-primary-500/30 group-hover:to-blue-500/30 transition-colors">
                            <action.icon className="w-4 h-4 lg:w-5 lg:h-5 text-primary-400" />
                          </div>
                          <div className="min-w-0 flex-1">
                            <p className="text-xs sm:text-sm font-medium text-white group-hover:text-primary-200 transition-colors truncate">
                              {action.title}
                            </p>
                            <p className="text-[10px] lg:text-xs text-gray-500 mt-0.5 truncate">
                              {action.description}
                            </p>
                          </div>
                        </div>
                      </motion.button>
                    ))}
                  </div>
                </div>

                {/* Suggestions from API - Hidden on mobile */}
                {suggestions?.suggestions && suggestions.suggestions.length > 0 && (
                  <div className="hidden sm:block w-full max-w-2xl mt-4 lg:mt-6 px-2">
                    <p className="text-xs lg:text-sm text-gray-500 mb-2 lg:mb-3">Or try asking:</p>
                    <div className="flex flex-wrap gap-2 justify-center">
                      {suggestions.suggestions.slice(0, 4).map((suggestion, i) => (
                        <motion.button
                          key={i}
                          initial={{ opacity: 0, scale: 0.9 }}
                          animate={{ opacity: 1, scale: 1 }}
                          transition={{ delay: 0.4 + i * 0.05 }}
                          onClick={() => handleQuickAction(suggestion)}
                          className="px-3 lg:px-4 py-1.5 lg:py-2 rounded-lg lg:rounded-xl text-xs lg:text-sm text-gray-300 bg-white/5 hover:bg-white/10 border border-white/10 hover:border-primary-500/30 transition-all truncate max-w-[200px]"
                        >
                          {suggestion}
                        </motion.button>
                      ))}
                    </div>
                  </div>
                )}
              </motion.div>
            ) : (
              <>
                <AnimatePresence>
                  {messages.map((message, index) => (
                    <motion.div
                      key={message.id}
                      initial={{ opacity: 0, y: 20, scale: 0.95 }}
                      animate={{ opacity: 1, y: 0, scale: 1 }}
                      transition={{ duration: 0.3, delay: index === messages.length - 1 ? 0.1 : 0 }}
                      className={`flex gap-2 sm:gap-3 lg:gap-4 ${message.role === 'user' ? 'flex-row-reverse' : 'flex-row'}`}
                    >
                      {/* Avatar */}
                      <div className="flex-shrink-0">
                        {message.role === 'assistant' ? (
                          <div className="w-8 h-8 sm:w-9 sm:h-9 lg:w-10 lg:h-10 rounded-lg lg:rounded-xl bg-gradient-to-br from-primary-400 to-blue-600 flex items-center justify-center shadow-lg shadow-primary-500/30">
                            <SparklesIcon className="w-4 h-4 sm:w-4 sm:h-4 lg:w-5 lg:h-5 text-white" />
                          </div>
                        ) : (
                          <div className="w-8 h-8 sm:w-9 sm:h-9 lg:w-10 lg:h-10 rounded-lg lg:rounded-xl bg-gradient-to-br from-cyan-400 to-blue-600 flex items-center justify-center shadow-lg shadow-blue-500/30">
                            <UserIcon className="w-4 h-4 sm:w-4 sm:h-4 lg:w-5 lg:h-5 text-white" />
                          </div>
                        )}
                      </div>

                      {/* Message Bubble */}
                      <div className={`group max-w-[85%] sm:max-w-[80%] lg:max-w-[75%] ${message.role === 'user' ? 'items-end' : 'items-start'}`}>
                        <div
                          className={`relative ${message.role === 'user'
                              ? 'bg-gradient-to-br from-primary-500 to-blue-600 text-white rounded-2xl rounded-tr-md px-3 sm:px-4 lg:px-5 py-2 sm:py-2.5 lg:py-3 shadow-lg shadow-primary-500/20'
                              : 'bg-dark-400/80 backdrop-blur-sm text-gray-100 rounded-2xl rounded-tl-md border border-white/10 px-3 sm:px-4 lg:px-5 py-2 sm:py-2.5 lg:py-3'
                            }`}
                        >
                          <p className="whitespace-pre-wrap text-xs sm:text-sm leading-relaxed">
                            {message.role === 'assistant' ? cleanResponse(message.content) : message.content}
                          </p>

                          {/* Related event images */}
                          {message.role === 'assistant' && message.events_with_images && message.events_with_images.length > 0 && (
                            <div className="mt-3 lg:mt-4 pt-3 lg:pt-4 border-t border-white/10">
                              <div className="flex items-center gap-2 text-[10px] lg:text-xs text-primary-400 font-medium mb-2 lg:mb-3">
                                <PhotoIcon className="w-3 h-3 lg:w-4 lg:h-4" />
                                <span>Related Events ({message.events_with_images.length})</span>
                              </div>
                              <div className="grid grid-cols-2 gap-1.5 lg:gap-2">
                                {message.events_with_images.map((event) => (
                                  <div key={event.id} className="group/event relative rounded-lg lg:rounded-xl overflow-hidden border border-white/10 hover:border-primary-500/50 transition-all cursor-pointer">
                                    <div className="aspect-video bg-dark-500">
                                      {event.frame_path ? (
                                        <img
                                          src={`/api/v1/events/${event.id}/frame?token=${token}`}
                                          alt={`Event ${event.id}`}
                                          className="w-full h-full object-cover group-hover/event:scale-105 transition-transform duration-300"
                                          onError={(e) => {
                                            (e.target as HTMLImageElement).style.display = 'none';
                                          }}
                                        />
                                      ) : (
                                        <div className="w-full h-full flex items-center justify-center">
                                          <PhotoIcon className="w-6 h-6 lg:w-8 lg:h-8 text-gray-600" />
                                        </div>
                                      )}
                                    </div>
                                    <div className="absolute inset-0 bg-gradient-to-t from-black/80 via-transparent to-transparent opacity-0 group-hover/event:opacity-100 transition-opacity" />
                                    <div className="absolute bottom-0 left-0 right-0 p-1.5 lg:p-2 translate-y-full group-hover/event:translate-y-0 transition-transform">
                                      <div className="flex items-center justify-between">
                                        <p className="text-[9px] lg:text-xs text-white font-medium">Event {event.id}</p>
                                        <span className={`px-1 lg:px-1.5 py-0.5 rounded text-[8px] lg:text-[9px] font-semibold ${event.severity === 'critical' ? 'bg-red-500' :
                                            event.severity === 'high' ? 'bg-orange-500' :
                                              event.severity === 'medium' ? 'bg-yellow-500' :
                                                'bg-primary-500'
                                          } text-white`}>
                                          {event.event_type.replace('_', ' ')}
                                        </span>
                                      </div>
                                    </div>
                                  </div>
                                ))}
                              </div>
                            </div>
                          )}

                          {/* Copy button for assistant messages */}
                          {message.role === 'assistant' && (
                            <button
                              onClick={() => handleCopyMessage(message)}
                              className="absolute -bottom-2 -right-2 p-1 lg:p-1.5 rounded-lg bg-dark-400 border border-white/10 opacity-0 group-hover:opacity-100 transition-opacity hover:bg-dark-300"
                            >
                              {copiedId === message.id ? (
                                <CheckIcon className="w-3 h-3 lg:w-3.5 lg:h-3.5 text-green-400" />
                              ) : (
                                <ClipboardDocumentIcon className="w-3 h-3 lg:w-3.5 lg:h-3.5 text-gray-400" />
                              )}
                            </button>
                          )}
                        </div>

                        <p className={`text-[9px] lg:text-[10px] mt-1 lg:mt-1.5 px-1 ${message.role === 'user' ? 'text-right text-gray-500' : 'text-gray-500'
                          }`}>
                          {format(new Date(message.created_at), 'HH:mm')}
                        </p>
                      </div>
                    </motion.div>
                  ))}
                </AnimatePresence>

                {/* Typing indicator */}
                {chatMutation.isPending && (
                  <motion.div
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    className="flex gap-2 sm:gap-3 lg:gap-4"
                  >
                    <div className="w-8 h-8 sm:w-9 sm:h-9 lg:w-10 lg:h-10 rounded-lg lg:rounded-xl bg-gradient-to-br from-primary-400 to-blue-600 flex items-center justify-center shadow-lg shadow-primary-500/30">
                      <SparklesIcon className="w-4 h-4 lg:w-5 lg:h-5 text-white animate-pulse" />
                    </div>
                    <div className="bg-dark-400/80 backdrop-blur-sm border border-white/10 rounded-2xl rounded-tl-md px-4 lg:px-5 py-3 lg:py-4">
                      <div className="flex items-center gap-1 lg:gap-1.5">
                        <motion.span
                          animate={{ scale: [1, 1.2, 1], opacity: [0.5, 1, 0.5] }}
                          transition={{ duration: 1, repeat: Infinity, delay: 0 }}
                          className="w-1.5 h-1.5 lg:w-2 lg:h-2 bg-primary-400 rounded-full"
                        />
                        <motion.span
                          animate={{ scale: [1, 1.2, 1], opacity: [0.5, 1, 0.5] }}
                          transition={{ duration: 1, repeat: Infinity, delay: 0.2 }}
                          className="w-1.5 h-1.5 lg:w-2 lg:h-2 bg-primary-400 rounded-full"
                        />
                        <motion.span
                          animate={{ scale: [1, 1.2, 1], opacity: [0.5, 1, 0.5] }}
                          transition={{ duration: 1, repeat: Infinity, delay: 0.4 }}
                          className="w-1.5 h-1.5 lg:w-2 lg:h-2 bg-primary-400 rounded-full"
                        />
                      </div>
                    </div>
                  </motion.div>
                )}

                <div ref={messagesEndRef} />
              </>
            )}
          </div>

          {/* Input Area */}
          <div className="relative p-3 sm:p-4 lg:p-5 border-t border-white/10 bg-dark-300/50 backdrop-blur-xl z-10">
            <form onSubmit={handleSubmit} className="relative">
              <div className="relative flex items-end gap-2 lg:gap-3">
                <div className="flex-1 relative">
                  <textarea
                    ref={inputRef}
                    value={input}
                    onChange={(e) => setInput(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter' && !e.shiftKey) {
                        e.preventDefault()
                        handleSubmit(e)
                      }
                    }}
                    placeholder="Ask about your security events..."
                    className="w-full px-3 sm:px-4 lg:px-5 py-3 lg:py-4 pr-10 lg:pr-12 rounded-xl lg:rounded-2xl text-sm lg:text-base text-white placeholder-gray-500 bg-dark-400/50 border border-white/10 focus:border-primary-500/50 focus:outline-none focus:ring-2 focus:ring-primary-500/20 resize-none transition-all duration-200"
                    rows={1}
                    style={{ minHeight: '48px', maxHeight: '120px' }}
                  />
                  {input && (
                    <button
                      type="button"
                      onClick={() => setInput('')}
                      className="absolute right-3 lg:right-4 top-1/2 -translate-y-1/2 p-1 rounded-full text-gray-500 hover:text-gray-300 hover:bg-white/10"
                    >
                      <XMarkIcon className="w-4 h-4" />
                    </button>
                  )}
                </div>
                <motion.button
                  type="submit"
                  disabled={!input.trim() || chatMutation.isPending}
                  whileHover={{ scale: 1.05 }}
                  whileTap={{ scale: 0.95 }}
                  className={`flex-shrink-0 w-11 h-11 sm:w-12 sm:h-12 lg:w-14 lg:h-14 rounded-xl lg:rounded-2xl flex items-center justify-center transition-all duration-200 ${input.trim() && !chatMutation.isPending
                      ? 'bg-gradient-to-br from-primary-500 to-blue-600 text-white shadow-lg shadow-primary-500/30 hover:shadow-xl hover:shadow-primary-500/40'
                      : 'bg-dark-400/50 text-gray-500 cursor-not-allowed'
                    }`}
                >
                  <PaperAirplaneIcon className="w-4 h-4 lg:w-5 lg:h-5" />
                </motion.button>
              </div>
              <div className="hidden sm:flex items-center justify-between mt-2 px-1">
                <p className="text-[10px] lg:text-[11px] text-gray-500">
                  Press <kbd className="px-1 lg:px-1.5 py-0.5 rounded bg-dark-400/50 text-gray-400 text-[9px] lg:text-[10px]">Enter</kbd> to send, <kbd className="px-1 lg:px-1.5 py-0.5 rounded bg-dark-400/50 text-gray-400 text-[9px] lg:text-[10px]">Shift+Enter</kbd> for new line
                </p>
                <p className="text-[10px] lg:text-[11px] text-gray-600">
                  Powered by AI
                </p>
              </div>
            </form>
          </div>
        </motion.div>
      </div>
    </div>
  )
}
