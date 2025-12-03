import { useState, useRef, useEffect } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { motion, AnimatePresence } from 'framer-motion'
import { format } from 'date-fns'
import {
  ChatBubbleLeftRightIcon,
  PaperAirplaneIcon,
  TrashIcon,
  SparklesIcon,
  ArrowPathIcon,
  PlusIcon,
  ClockIcon,
} from '@heroicons/react/24/outline'
import { assistantApi } from '../services'
import type { ChatSession, ChatMessage } from '../types'
import toast from 'react-hot-toast'

export default function Assistant() {
  const [input, setInput] = useState('')
  const [currentSessionId, setCurrentSessionId] = useState<number | null>(null)
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLTextAreaElement>(null)
  const queryClient = useQueryClient()

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

  const chatMutation = useMutation({
    mutationFn: assistantApi.chat,
    onMutate: (data) => {
      // Add user message immediately
      const userMessage: ChatMessage = {
        id: Date.now(),
        role: 'user',
        content: data.message,
        created_at: new Date().toISOString(),
      }
      setMessages((prev) => [...prev, userMessage])
    },
    onSuccess: (response) => {
      // Add assistant response
      const assistantMessage: ChatMessage = {
        id: Date.now() + 1,
        role: 'assistant',
        content: response.response,
        created_at: new Date().toISOString(),
      }
      setMessages((prev) => [...prev, assistantMessage])
      
      // Update session ID if new
      if (response.session_id && !currentSessionId) {
        setCurrentSessionId(response.session_id)
      }
      
      queryClient.invalidateQueries({ queryKey: ['chatSessions'] })
    },
    onError: () => {
      toast.error('Failed to get response')
      // Remove the last user message on error
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

  const handleSuggestionClick = (suggestion: string) => {
    setInput(suggestion)
    inputRef.current?.focus()
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
        <div className="w-64 flex-shrink-0 flex flex-col gap-4">
          <button onClick={startNewChat} className="btn-primary w-full">
            <PlusIcon className="w-5 h-5" />
            New Chat
          </button>

          <div className="glass-card flex-1 overflow-hidden flex flex-col">
            <div className="p-4 border-b border-white/10">
              <h2 className="text-sm font-medium text-gray-400">Recent Chats</h2>
            </div>
            <div className="flex-1 overflow-y-auto p-2 space-y-1">
              {sessions?.map((session) => (
                <motion.button
                  key={session.id}
                  onClick={() => selectSession(session)}
                  className={`w-full text-left p-3 rounded-xl transition-all ${
                    currentSessionId === session.id
                      ? 'bg-primary-500/20 text-primary-400'
                      : 'text-gray-400 hover:text-white hover:bg-white/5'
                  }`}
                >
                  <p className="text-sm font-medium truncate">
                    {session.title || 'New Chat'}
                  </p>
                  <p className="text-xs text-gray-500 mt-1 flex items-center gap-1">
                    <ClockIcon className="w-3 h-3" />
                    {format(new Date(session.created_at), 'MMM d, HH:mm')}
                  </p>
                </motion.button>
              ))}
              {(!sessions || sessions.length === 0) && (
                <p className="text-center text-sm text-gray-500 py-4">
                  No chat history
                </p>
              )}
            </div>
          </div>
        </div>

        {/* Main Chat Area */}
        <div className="flex-1 flex flex-col glass-card overflow-hidden">
          {/* Header */}
          <div className="flex items-center justify-between p-4 border-b border-white/10">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-primary-400 to-primary-600 flex items-center justify-center">
                <SparklesIcon className="w-5 h-5 text-white" />
              </div>
              <div>
                <h1 className="text-lg font-semibold text-white">AI Assistant</h1>
                <p className="text-sm text-gray-400">
                  Ask questions about your security events
                </p>
              </div>
            </div>
            {currentSessionId && (
              <button
                onClick={() => deleteSessionMutation.mutate(currentSessionId)}
                className="p-2 rounded-lg text-gray-400 hover:text-red-400 hover:bg-red-500/10"
                title="Delete Chat"
              >
                <TrashIcon className="w-5 h-5" />
              </button>
            )}
          </div>

          {/* Messages */}
          <div className="flex-1 overflow-y-auto p-4 space-y-4">
            {messages.length === 0 ? (
              <div className="h-full flex flex-col items-center justify-center text-center">
                <div className="w-16 h-16 rounded-2xl bg-primary-500/20 flex items-center justify-center mb-4">
                  <ChatBubbleLeftRightIcon className="w-8 h-8 text-primary-400" />
                </div>
                <h2 className="text-xl font-semibold text-white mb-2">
                  How can I help you?
                </h2>
                <p className="text-gray-400 max-w-md mb-6">
                  I can help you understand your security events, search through
                  recordings, and provide insights about activity patterns.
                </p>

                {/* Suggestions */}
                {suggestions?.suggestions && suggestions.suggestions.length > 0 && (
                  <div className="w-full max-w-2xl">
                    <p className="text-sm text-gray-500 mb-3">Try asking:</p>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                      {suggestions.suggestions.map((suggestion, i) => (
                        <button
                          key={i}
                          onClick={() => handleSuggestionClick(suggestion)}
                          className="text-left p-4 rounded-xl bg-white/5 hover:bg-white/10 text-gray-300 text-sm transition-colors"
                        >
                          {suggestion}
                        </button>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            ) : (
              <>
                <AnimatePresence>
                  {messages.map((message) => (
                    <motion.div
                      key={message.id}
                      initial={{ opacity: 0, y: 10 }}
                      animate={{ opacity: 1, y: 0 }}
                      className={`flex gap-3 ${
                        message.role === 'user' ? 'justify-end' : ''
                      }`}
                    >
                      {message.role === 'assistant' && (
                        <div className="w-8 h-8 rounded-lg bg-primary-500/20 flex items-center justify-center flex-shrink-0">
                          <SparklesIcon className="w-4 h-4 text-primary-400" />
                        </div>
                      )}
                      <div
                        className={`max-w-[70%] p-4 rounded-2xl ${
                          message.role === 'user'
                            ? 'bg-primary-500 text-white rounded-br-md'
                            : 'bg-white/10 text-gray-200 rounded-bl-md'
                        }`}
                      >
                        <p className="whitespace-pre-wrap">{message.content}</p>
                        <p
                          className={`text-xs mt-2 ${
                            message.role === 'user'
                              ? 'text-primary-200'
                              : 'text-gray-500'
                          }`}
                        >
                          {format(new Date(message.created_at), 'HH:mm')}
                        </p>
                      </div>
                      {message.role === 'user' && (
                        <div className="w-8 h-8 rounded-lg bg-primary-500 flex items-center justify-center flex-shrink-0">
                          <span className="text-sm text-white font-medium">Y</span>
                        </div>
                      )}
                    </motion.div>
                  ))}
                </AnimatePresence>

                {chatMutation.isPending && (
                  <motion.div
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    className="flex gap-3"
                  >
                    <div className="w-8 h-8 rounded-lg bg-primary-500/20 flex items-center justify-center flex-shrink-0">
                      <ArrowPathIcon className="w-4 h-4 text-primary-400 animate-spin" />
                    </div>
                    <div className="bg-white/10 rounded-2xl rounded-bl-md p-4">
                      <div className="flex gap-1">
                        <span className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" />
                        <span
                          className="w-2 h-2 bg-gray-400 rounded-full animate-bounce"
                          style={{ animationDelay: '0.1s' }}
                        />
                        <span
                          className="w-2 h-2 bg-gray-400 rounded-full animate-bounce"
                          style={{ animationDelay: '0.2s' }}
                        />
                      </div>
                    </div>
                  </motion.div>
                )}

                <div ref={messagesEndRef} />
              </>
            )}
          </div>

          {/* Input */}
          <form onSubmit={handleSubmit} className="p-4 border-t border-white/10">
            <div className="flex gap-3">
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
                className="input flex-1 resize-none"
                rows={1}
                style={{ minHeight: '44px', maxHeight: '120px' }}
              />
              <button
                type="submit"
                disabled={!input.trim() || chatMutation.isPending}
                className="btn-primary px-4"
              >
                <PaperAirplaneIcon className="w-5 h-5" />
              </button>
            </div>
            <p className="text-xs text-gray-500 mt-2">
              Press Enter to send, Shift+Enter for new line
            </p>
          </form>
        </div>
      </div>
    </div>
  )
}
