import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import { EyeIcon, EyeSlashIcon, VideoCameraIcon, ShieldCheckIcon } from '@heroicons/react/24/outline'
import { useAuthStore } from '../store/authStore'
import { authApi, userApi } from '../services'
import toast from 'react-hot-toast'

export default function Login() {
  const [isLogin, setIsLogin] = useState(true)
  const [showPassword, setShowPassword] = useState(false)
  const [loading, setLoading] = useState(false)
  const [formData, setFormData] = useState({
    username: '',
    email: '',
    password: '',
    full_name: '',
  })
  
  const { login } = useAuthStore()
  const navigate = useNavigate()

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true)

    try {
      if (isLogin) {
        const tokens = await authApi.login({
          username: formData.username,
          password: formData.password,
        })
        // First set tokens so the next API call has auth
        useAuthStore.getState().setTokens(tokens.access_token, tokens.refresh_token)
        const user = await userApi.getCurrentUser()
        login(user, tokens.access_token, tokens.refresh_token)
        toast.success('Welcome back!')
        navigate('/')
      } else {
        await authApi.register({
          email: formData.email,
          username: formData.username,
          password: formData.password,
          full_name: formData.full_name,
        })
        toast.success('Account created! Please login.')
        setIsLogin(true)
      }
    } catch (error: unknown) {
      const err = error as { response?: { data?: { detail?: string } } }
      toast.error(err.response?.data?.detail || 'An error occurred')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-dark-500 bg-mesh flex items-center justify-center p-4 relative overflow-hidden">
      {/* Animated background elements */}
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        <motion.div
          animate={{ 
            scale: [1, 1.2, 1],
            opacity: [0.1, 0.15, 0.1]
          }}
          transition={{ duration: 8, repeat: Infinity }}
          className="absolute -top-40 -right-40 w-96 h-96 rounded-full bg-primary-500/20 blur-3xl"
        />
        <motion.div
          animate={{ 
            scale: [1.2, 1, 1.2],
            opacity: [0.1, 0.15, 0.1]
          }}
          transition={{ duration: 10, repeat: Infinity }}
          className="absolute -bottom-40 -left-40 w-96 h-96 rounded-full bg-blue-500/20 blur-3xl"
        />
      </div>

      <motion.div
        initial={{ opacity: 0, y: 30 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5, ease: 'easeOut' }}
        className="w-full max-w-md relative z-10"
      >
        {/* Logo */}
        <div className="text-center mb-8">
          <motion.div
            initial={{ scale: 0, rotate: -180 }}
            animate={{ scale: 1, rotate: 0 }}
            transition={{ type: 'spring', duration: 0.8, bounce: 0.4 }}
            whileHover={{ scale: 1.05, rotate: 5 }}
            className="w-20 h-20 mx-auto rounded-2xl bg-gradient-to-br from-primary-400 to-primary-600 flex items-center justify-center mb-4 shadow-xl shadow-primary-500/40"
          >
            <VideoCameraIcon className="w-10 h-10 text-white" />
          </motion.div>
          <motion.h1 
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.3 }}
            className="text-3xl font-bold text-gradient"
          >
            Chowkidaar
          </motion.h1>
          <motion.p 
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.4 }}
            className="text-gray-400 mt-2"
          >
            AI-Powered Security System
          </motion.p>
        </div>

        {/* Form Card */}
        <motion.div 
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.2 }}
          className="glass-card p-8"
        >
          {/* Tab Switcher */}
          <div className="flex gap-2 mb-6 p-1 rounded-xl bg-white/5">
            <motion.button
              whileTap={{ scale: 0.98 }}
              onClick={() => setIsLogin(true)}
              className={`relative flex-1 py-2.5 rounded-lg text-sm font-semibold transition-colors duration-200 ${
                isLogin ? 'text-white' : 'text-gray-400 hover:text-white'
              }`}
            >
              {isLogin && (
                <motion.div
                  layoutId="activeTab"
                  className="absolute inset-0 bg-primary-500/20 rounded-lg border border-primary-500/30"
                  transition={{ type: 'spring', duration: 0.4 }}
                />
              )}
              <span className="relative z-10">Login</span>
            </motion.button>
            <motion.button
              whileTap={{ scale: 0.98 }}
              onClick={() => setIsLogin(false)}
              className={`relative flex-1 py-2.5 rounded-lg text-sm font-semibold transition-colors duration-200 ${
                !isLogin ? 'text-white' : 'text-gray-400 hover:text-white'
              }`}
            >
              {!isLogin && (
                <motion.div
                  layoutId="activeTab"
                  className="absolute inset-0 bg-primary-500/20 rounded-lg border border-primary-500/30"
                  transition={{ type: 'spring', duration: 0.4 }}
                />
              )}
              <span className="relative z-10">Register</span>
            </motion.button>
          </div>

          <form onSubmit={handleSubmit} className="space-y-4">
            <AnimatePresence mode="wait">
              {!isLogin && (
                <motion.div
                  key="fullname"
                  initial={{ opacity: 0, height: 0, marginBottom: 0 }}
                  animate={{ opacity: 1, height: 'auto', marginBottom: 16 }}
                  exit={{ opacity: 0, height: 0, marginBottom: 0 }}
                  transition={{ duration: 0.2 }}
                >
                  <label className="label">Full Name</label>
                  <input
                    type="text"
                    className="input"
                    placeholder="John Doe"
                    value={formData.full_name}
                    onChange={(e) =>
                      setFormData({ ...formData, full_name: e.target.value })
                    }
                  />
                </motion.div>
              )}
            </AnimatePresence>

            <AnimatePresence mode="wait">
              {!isLogin && (
                <motion.div
                  key="email"
                  initial={{ opacity: 0, height: 0, marginBottom: 0 }}
                  animate={{ opacity: 1, height: 'auto', marginBottom: 16 }}
                  exit={{ opacity: 0, height: 0, marginBottom: 0 }}
                  transition={{ duration: 0.2, delay: 0.05 }}
                >
                  <label className="label">Email</label>
                  <input
                    type="email"
                    className="input"
                    placeholder="john@example.com"
                    value={formData.email}
                    onChange={(e) =>
                      setFormData({ ...formData, email: e.target.value })
                    }
                    required={!isLogin}
                  />
                </motion.div>
              )}
            </AnimatePresence>

            <div>
              <label className="label">Username</label>
              <motion.input
                whileFocus={{ scale: 1.01 }}
                type="text"
                className="input"
                placeholder="username"
                value={formData.username}
                onChange={(e) =>
                  setFormData({ ...formData, username: e.target.value })
                }
                required
              />
            </div>

            <div>
              <label className="label">Password</label>
              <div className="relative">
                <motion.input
                  whileFocus={{ scale: 1.01 }}
                  type={showPassword ? 'text' : 'password'}
                  className="input pr-12"
                  placeholder="••••••••"
                  value={formData.password}
                  onChange={(e) =>
                    setFormData({ ...formData, password: e.target.value })
                  }
                  required
                />
                <motion.button
                  whileHover={{ scale: 1.1 }}
                  whileTap={{ scale: 0.9 }}
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-4 top-1/2 -translate-y-1/2 text-gray-500 hover:text-white transition-colors"
                >
                  {showPassword ? (
                    <EyeSlashIcon className="w-5 h-5" />
                  ) : (
                    <EyeIcon className="w-5 h-5" />
                  )}
                </motion.button>
              </div>
            </div>

            <motion.button
              whileHover={{ scale: 1.02 }}
              whileTap={{ scale: 0.98 }}
              type="submit"
              disabled={loading}
              className="btn-primary w-full py-3 mt-6"
            >
              {loading ? (
                <span className="flex items-center justify-center gap-2">
                  <svg className="animate-spin w-5 h-5" viewBox="0 0 24 24">
                    <circle
                      className="opacity-25"
                      cx="12"
                      cy="12"
                      r="10"
                      stroke="currentColor"
                      strokeWidth="4"
                      fill="none"
                    />
                    <path
                      className="opacity-75"
                      fill="currentColor"
                      d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                    />
                  </svg>
                  Processing...
                </span>
              ) : isLogin ? (
                'Sign In'
              ) : (
                'Create Account'
              )}
            </motion.button>
          </form>
        </motion.div>

        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.5 }}
          className="flex items-center justify-center gap-2 mt-6"
        >
          <ShieldCheckIcon className="w-4 h-4 text-gray-500" />
          <p className="text-gray-500 text-sm">
            Powered by YOLOv8+ & Ollama VLM
          </p>
        </motion.div>
      </motion.div>
    </div>
  )
}
