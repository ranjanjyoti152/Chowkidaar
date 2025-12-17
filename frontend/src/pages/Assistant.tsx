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
    inputRef.current?.focus()
  }

  const selectSession = (session: ChatSession) => {
    setCurrentSessionId(session.id)
    refetchSession()
  }

  return (
    <div className="page-container h-[calc(100vh-8rem)]">
      <div className="flex gap-6 h-full">
        {/* Sidebar - Sessions */}
        <motion.div
          initial={{ opacity: 0, x: -20 }}
          animate={{ opacity: 1, x: 0 }}
          className="w-72 flex-shrink-0 flex flex-col gap-4"
        >
          <button onClick={startNewChat} className="btn-primary w-full group">
            <PlusIcon className="w-5 h-5 group-hover:rotate-90 transition-transform duration-300" />
            New Conversation
          </button>

          <div className="glass-card flex-1 overflow-hidden flex flex-col">
            <div className="p-4 border-b border-white/10">
              <div className="relative">
                <MagnifyingGlassIcon className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-gray-500" />
                <input
                  type="text"
                  placeholder="Search conversations..."
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                  className="w-full pl-9 pr-4 py-2 text-sm rounded-lg bg-dark-400/50 border border-white/10 focus:border-primary-500/50 focus:outline-none text-white placeholder-gray-500"
                />
              </div>
            </div>

            <div className="flex-1 overflow-y-auto p-3 space-y-2 scrollbar-hide">
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
                      className={`w-full text-left p-3 rounded-xl transition-all duration-200 ${currentSessionId === session.id
                          ? 'bg-gradient-to-r from-primary-500/20 to-primary-500/10 border border-primary-500/30'
                          : 'hover:bg-white/5 border border-transparent'
                        }`}
                    >
                      <div className="flex items-start gap-3">
                        <div className={`w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0 ${currentSessionId === session.id
                            ? 'bg-primary-500/30'
                            : 'bg-dark-400/50'
                          }`}>
                          <ChatBubbleLeftRightIcon className={`w-4 h-4 ${currentSessionId === session.id ? 'text-primary-300' : 'text-gray-500'
                            }`} />
                        </div>
                        <div className="flex-1 min-w-0">
                          <p className={`text-sm font-medium truncate ${currentSessionId === session.id ? 'text-primary-200' : 'text-gray-300'
                            }`}>
                            {session.title || 'New Chat'}
                          </p>
                          <p className="text-xs text-gray-500 mt-1 flex items-center gap-1">
                            <ClockIcon className="w-3 h-3" />
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
                <div className="text-center py-8">
                  <ChatBubbleLeftRightIcon className="w-10 h-10 text-gray-600 mx-auto mb-3" />
                  <p className="text-sm text-gray-500">
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
          className="flex-1 flex flex-col glass-card overflow-hidden relative"
        >
          {/* Ambient glow effects */}
          <div className="absolute top-0 left-1/4 w-96 h-96 bg-primary-500/10 rounded-full blur-3xl pointer-events-none" />
          <div className="absolute bottom-0 right-1/4 w-96 h-96 bg-blue-500/10 rounded-full blur-3xl pointer-events-none" />

          {/* Header */}
          <div className="relative flex items-center justify-between p-5 border-b border-white/10 bg-dark-300/50 backdrop-blur-xl z-10">
            <div className="flex items-center gap-4">
              <div className="relative">
                <div className="w-12 h-12 rounded-2xl bg-gradient-to-br from-primary-400 via-primary-500 to-blue-600 flex items-center justify-center shadow-lg shadow-primary-500/30">
                  <SparklesIcon className="w-6 h-6 text-white" />
                </div>
                <span className="absolute -bottom-1 -right-1 w-4 h-4 bg-green-500 rounded-full border-2 border-dark-300 animate-pulse" />
              </div>
              <div>
                <h1 className="text-lg font-semibold text-white flex items-center gap-2">
                  Chowkidaar AI
                  <span className="px-2 py-0.5 rounded-full text-[10px] font-medium bg-primary-500/20 text-primary-300 border border-primary-500/30">
                    Online
                  </span>
                </h1>
                <p className="text-sm text-gray-400">
                  Your intelligent security assistant
                </p>
              </div>
            </div>

            {currentSessionId && (
              <button
                onClick={() => setShowDeleteConfirm(currentSessionId)}
                className="p-2.5 rounded-xl text-gray-400 hover:text-red-400 hover:bg-red-500/10 transition-colors"
                title="Delete Chat"
              >
                <TrashIcon className="w-5 h-5" />
              </button>
            )}
          </div>

          {/* Messages */}
          <div className="flex-1 overflow-y-auto p-6 space-y-6 relative z-10">
            {messages.length === 0 ? (
              <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                className="h-full flex flex-col items-center justify-center text-center"
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
                  className="relative mb-6"
                >
                  <div className="w-24 h-24 rounded-3xl bg-gradient-to-br from-primary-400 via-primary-500 to-blue-600 flex items-center justify-center shadow-2xl shadow-primary-500/40">
                    <SparklesIcon className="w-12 h-12 text-white" />
                  </div>
                  <div className="absolute -inset-4 bg-primary-500/20 rounded-3xl blur-xl -z-10" />
                </motion.div>

                <h2 className="text-2xl font-bold text-white mb-3">
                  How can I help you today?
                </h2>
                <p className="text-gray-400 max-w-lg mb-8">
                  I'm your AI-powered security assistant. Ask me about events, alerts,
                  activity patterns, or anything related to your surveillance system.
                </p>

                {/* Quick Actions Grid */}
                <div className="w-full max-w-2xl">
                  <p className="text-sm text-gray-500 mb-4">Quick actions</p>
                  <div className="grid grid-cols-2 gap-3">
                    {quickActions.map((action, i) => (
                      <motion.button
                        key={i}
                        initial={{ opacity: 0, y: 10 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ delay: i * 0.1 }}
                        onClick={() => handleQuickAction(action.query)}
                        className="group p-4 rounded-2xl text-left transition-all duration-300 bg-dark-400/50 hover:bg-dark-400/80 border border-white/5 hover:border-primary-500/30 hover:shadow-lg hover:shadow-primary-500/10"
                      >
                        <div className="flex items-start gap-3">
                          <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-primary-500/20 to-blue-500/20 flex items-center justify-center group-hover:from-primary-500/30 group-hover:to-blue-500/30 transition-colors">
                            <action.icon className="w-5 h-5 text-primary-400" />
                          </div>
                          <div>
                            <p className="text-sm font-medium text-white group-hover:text-primary-200 transition-colors">
                              {action.title}
                            </p>
                            <p className="text-xs text-gray-500 mt-0.5">
                              {action.description}
                            </p>
                          </div>
                        </div>
                      </motion.button>
                    ))}
                  </div>
                </div>

                {/* Suggestions from API */}
                {suggestions?.suggestions && suggestions.suggestions.length > 0 && (
                  <div className="w-full max-w-2xl mt-6">
                    <p className="text-sm text-gray-500 mb-3">Or try asking:</p>
                    <div className="flex flex-wrap gap-2 justify-center">
                      {suggestions.suggestions.map((suggestion, i) => (
                        <motion.button
                          key={i}
                          initial={{ opacity: 0, scale: 0.9 }}
                          animate={{ opacity: 1, scale: 1 }}
                          transition={{ delay: 0.4 + i * 0.05 }}
                          onClick={() => handleQuickAction(suggestion)}
                          className="px-4 py-2 rounded-xl text-sm text-gray-300 bg-white/5 hover:bg-white/10 border border-white/10 hover:border-primary-500/30 transition-all"
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
                      className={`flex gap-4 ${message.role === 'user' ? 'flex-row-reverse' : 'flex-row'}`}
                    >
                      {/* Avatar */}
                      <div className="flex-shrink-0">
                        {message.role === 'assistant' ? (
                          <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-primary-400 to-blue-600 flex items-center justify-center shadow-lg shadow-primary-500/30">
                            <SparklesIcon className="w-5 h-5 text-white" />
                          </div>
                        ) : (
                          <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-cyan-400 to-blue-600 flex items-center justify-center shadow-lg shadow-blue-500/30">
                            <UserIcon className="w-5 h-5 text-white" />
                          </div>
                        )}
                      </div>

                      {/* Message Bubble */}
                      <div className={`group max-w-[75%] ${message.role === 'user' ? 'items-end' : 'items-start'}`}>
                        <div
                          className={`relative ${message.role === 'user'
                              ? 'bg-gradient-to-br from-primary-500 to-blue-600 text-white rounded-2xl rounded-tr-md px-5 py-3 shadow-lg shadow-primary-500/20'
                              : 'bg-dark-400/80 backdrop-blur-sm text-gray-100 rounded-2xl rounded-tl-md border border-white/10 px-5 py-3'
                            }`}
                        >
                          <p className="whitespace-pre-wrap text-sm leading-relaxed">
                            {message.role === 'assistant' ? cleanResponse(message.content) : message.content}
                          </p>

                          {/* Related event images */}
                          {message.role === 'assistant' && message.events_with_images && message.events_with_images.length > 0 && (
                            <div className="mt-4 pt-4 border-t border-white/10">
                              <div className="flex items-center gap-2 text-xs text-primary-400 font-medium mb-3">
                                <PhotoIcon className="w-4 h-4" />
                                <span>Related Events ({message.events_with_images.length})</span>
                              </div>
                              <div className="grid grid-cols-2 gap-2">
                                {message.events_with_images.map((event) => (
                                  <div key={event.id} className="group/event relative rounded-xl overflow-hidden border border-white/10 hover:border-primary-500/50 transition-all cursor-pointer">
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
                                          <PhotoIcon className="w-8 h-8 text-gray-600" />
                                        </div>
                                      )}
                                    </div>
                                    <div className="absolute inset-0 bg-gradient-to-t from-black/80 via-transparent to-transparent opacity-0 group-hover/event:opacity-100 transition-opacity" />
                                    <div className="absolute bottom-0 left-0 right-0 p-2 translate-y-full group-hover/event:translate-y-0 transition-transform">
                                      <div className="flex items-center justify-between">
                                        <p className="text-xs text-white font-medium">Event {event.id}</p>
                                        <span className={`px-1.5 py-0.5 rounded text-[9px] font-semibold ${event.severity === 'critical' ? 'bg-red-500' :
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
                              className="absolute -bottom-2 -right-2 p-1.5 rounded-lg bg-dark-400 border border-white/10 opacity-0 group-hover:opacity-100 transition-opacity hover:bg-dark-300"
                            >
                              {copiedId === message.id ? (
                                <CheckIcon className="w-3.5 h-3.5 text-green-400" />
                              ) : (
                                <ClipboardDocumentIcon className="w-3.5 h-3.5 text-gray-400" />
                              )}
                            </button>
                          )}
                        </div>

                        <p className={`text-[10px] mt-1.5 px-1 ${message.role === 'user' ? 'text-right text-gray-500' : 'text-gray-500'
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
                    className="flex gap-4"
                  >
                    <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-primary-400 to-blue-600 flex items-center justify-center shadow-lg shadow-primary-500/30">
                      <SparklesIcon className="w-5 h-5 text-white animate-pulse" />
                    </div>
                    <div className="bg-dark-400/80 backdrop-blur-sm border border-white/10 rounded-2xl rounded-tl-md px-5 py-4">
                      <div className="flex items-center gap-1.5">
                        <motion.span
                          animate={{ scale: [1, 1.2, 1], opacity: [0.5, 1, 0.5] }}
                          transition={{ duration: 1, repeat: Infinity, delay: 0 }}
                          className="w-2 h-2 bg-primary-400 rounded-full"
                        />
                        <motion.span
                          animate={{ scale: [1, 1.2, 1], opacity: [0.5, 1, 0.5] }}
                          transition={{ duration: 1, repeat: Infinity, delay: 0.2 }}
                          className="w-2 h-2 bg-primary-400 rounded-full"
                        />
                        <motion.span
                          animate={{ scale: [1, 1.2, 1], opacity: [0.5, 1, 0.5] }}
                          transition={{ duration: 1, repeat: Infinity, delay: 0.4 }}
                          className="w-2 h-2 bg-primary-400 rounded-full"
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
          <div className="relative p-5 border-t border-white/10 bg-dark-300/50 backdrop-blur-xl z-10">
            <form onSubmit={handleSubmit} className="relative">
              <div className="relative flex items-end gap-3">
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
                    className="w-full px-5 py-4 pr-12 rounded-2xl text-white placeholder-gray-500 bg-dark-400/50 border border-white/10 focus:border-primary-500/50 focus:outline-none focus:ring-2 focus:ring-primary-500/20 resize-none transition-all duration-200"
                    rows={1}
                    style={{ minHeight: '56px', maxHeight: '150px' }}
                  />
                  {input && (
                    <button
                      type="button"
                      onClick={() => setInput('')}
                      className="absolute right-4 top-1/2 -translate-y-1/2 p-1 rounded-full text-gray-500 hover:text-gray-300 hover:bg-white/10"
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
                  className={`flex-shrink-0 w-14 h-14 rounded-2xl flex items-center justify-center transition-all duration-200 ${input.trim() && !chatMutation.isPending
                      ? 'bg-gradient-to-br from-primary-500 to-blue-600 text-white shadow-lg shadow-primary-500/30 hover:shadow-xl hover:shadow-primary-500/40'
                      : 'bg-dark-400/50 text-gray-500 cursor-not-allowed'
                    }`}
                >
                  <PaperAirplaneIcon className="w-5 h-5" />
                </motion.button>
              </div>
              <div className="flex items-center justify-between mt-2 px-1">
                <p className="text-[11px] text-gray-500">
                  Press <kbd className="px-1.5 py-0.5 rounded bg-dark-400/50 text-gray-400 text-[10px]">Enter</kbd> to send, <kbd className="px-1.5 py-0.5 rounded bg-dark-400/50 text-gray-400 text-[10px]">Shift+Enter</kbd> for new line
                </p>
                <p className="text-[11px] text-gray-600">
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
