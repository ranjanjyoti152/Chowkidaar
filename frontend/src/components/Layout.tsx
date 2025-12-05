import { Outlet, NavLink, useNavigate, useLocation } from 'react-router-dom'
import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  HomeIcon,
  VideoCameraIcon,
  BellAlertIcon,
  CpuChipIcon,
  ChatBubbleLeftRightIcon,
  Cog6ToothIcon,
  UserGroupIcon,
  ArrowRightOnRectangleIcon,
  Bars3Icon,
  XMarkIcon,
} from '@heroicons/react/24/outline'
import { useAuthStore } from '../store/authStore'
import clsx from 'clsx'

const navigation = [
  { name: 'Dashboard', href: '/', icon: HomeIcon },
  { name: 'Cameras', href: '/cameras', icon: VideoCameraIcon },
  { name: 'Events', href: '/events', icon: BellAlertIcon },
  { name: 'Monitor', href: '/monitor', icon: CpuChipIcon },
  { name: 'Assistant', href: '/assistant', icon: ChatBubbleLeftRightIcon },
  { name: 'Settings', href: '/settings', icon: Cog6ToothIcon },
  { name: 'Admin', href: '/admin', icon: UserGroupIcon },
]

// Animation variants
const sidebarVariants = {
  hidden: { x: -280, opacity: 0 },
  visible: { 
    x: 0, 
    opacity: 1,
    transition: { type: 'spring', damping: 25, stiffness: 300 }
  },
  exit: { 
    x: -280, 
    opacity: 0,
    transition: { duration: 0.2 }
  }
}

const navItemVariants = {
  hidden: { opacity: 0, x: -20 },
  visible: (i: number) => ({
    opacity: 1,
    x: 0,
    transition: { delay: i * 0.05, duration: 0.2 }
  })
}

const pageTransition = {
  initial: { opacity: 0, y: 10 },
  animate: { opacity: 1, y: 0 },
  exit: { opacity: 0, y: -10 },
  transition: { duration: 0.2 }
}

export default function Layout() {
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const { user, logout } = useAuthStore()
  const navigate = useNavigate()
  const location = useLocation()

  const handleLogout = () => {
    logout()
    navigate('/login')
  }

  return (
    <div className="min-h-screen bg-dark-500 bg-mesh">
      {/* Mobile sidebar backdrop */}
      <AnimatePresence>
        {sidebarOpen && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={() => setSidebarOpen(false)}
            className="fixed inset-0 z-40 bg-black/60 backdrop-blur-sm lg:hidden"
          />
        )}
      </AnimatePresence>

      {/* Sidebar */}
      <aside
        className={clsx(
          'fixed top-0 left-0 z-50 h-full w-64 transition-transform duration-300 lg:translate-x-0',
          sidebarOpen ? 'translate-x-0' : '-translate-x-full'
        )}
      >
        <div className="flex h-full flex-col glass-card rounded-none lg:rounded-r-2xl border-r border-white/10">
          {/* Logo */}
          <div className="flex items-center gap-3 px-6 py-5 border-b border-white/10">
            <motion.div 
              whileHover={{ scale: 1.05, rotate: 5 }}
              whileTap={{ scale: 0.95 }}
              className="w-10 h-10 rounded-xl bg-gradient-to-br from-primary-400 to-primary-600 flex items-center justify-center shadow-lg shadow-primary-500/40"
            >
              <VideoCameraIcon className="w-6 h-6 text-white" />
            </motion.div>
            <div>
              <h1 className="text-xl font-bold text-gradient">Chowkidaar</h1>
              <p className="text-xs text-gray-500">AI Security System</p>
            </div>
          </div>

          {/* Navigation */}
          <nav className="flex-1 px-3 py-6 space-y-1 overflow-y-auto scrollbar-hide">
            {navigation.map((item, i) => (
              <NavLink
                key={item.name}
                to={item.href}
                onClick={() => setSidebarOpen(false)}
                className={({ isActive }) =>
                  clsx(
                    'group relative flex items-center gap-3 px-4 py-3 rounded-xl text-sm font-medium transition-all duration-200',
                    isActive
                      ? 'text-white'
                      : 'text-gray-400 hover:text-white'
                  )
                }
              >
                {({ isActive }) => (
                  <>
                    {/* Active background */}
                    {isActive && (
                      <motion.div
                        layoutId="activeNav"
                        className="absolute inset-0 rounded-xl bg-gradient-to-r from-primary-500/25 to-primary-500/5"
                        style={{ borderLeft: '3px solid rgb(6, 182, 212)' }}
                        transition={{ type: 'spring', damping: 25, stiffness: 300 }}
                      />
                    )}
                    
                    {/* Hover background */}
                    {!isActive && (
                      <div className="absolute inset-0 rounded-xl bg-white/0 group-hover:bg-white/8 transition-colors duration-200" />
                    )}
                    
                    {/* Icon */}
                    <motion.div
                      whileHover={{ scale: 1.1 }}
                      whileTap={{ scale: 0.9 }}
                      className="relative z-10"
                    >
                      <item.icon className={clsx(
                        'w-5 h-5 transition-colors duration-200',
                        isActive ? 'text-primary-400' : 'group-hover:text-primary-400'
                      )} />
                    </motion.div>
                    
                    {/* Label */}
                    <span className="relative z-10">{item.name}</span>
                  </>
                )}
              </NavLink>
            ))}
          </nav>

          {/* User section */}
          <div className="px-3 py-4 border-t border-white/10">
            <div className="flex items-center gap-3 px-3 py-3 rounded-xl bg-white/5">
              <motion.div 
                whileHover={{ scale: 1.1 }}
                className="w-10 h-10 rounded-full bg-gradient-to-br from-primary-400 to-primary-600 flex items-center justify-center shadow-lg shadow-primary-500/30"
              >
                <span className="text-white font-semibold">
                  {user?.username?.charAt(0).toUpperCase() || 'U'}
                </span>
              </motion.div>
              <div className="flex-1 min-w-0">
                <p className="text-sm font-semibold text-white truncate">
                  {user?.full_name || user?.username}
                </p>
                <p className="text-xs text-gray-500 capitalize">{user?.role}</p>
              </div>
              <motion.button
                whileHover={{ scale: 1.1 }}
                whileTap={{ scale: 0.9 }}
                onClick={handleLogout}
                className="p-2 rounded-lg text-gray-400 hover:text-red-400 hover:bg-red-500/10 transition-all duration-200"
                title="Logout"
              >
                <ArrowRightOnRectangleIcon className="w-5 h-5" />
              </motion.button>
            </div>
          </div>
        </div>
      </aside>

      {/* Main content */}
      <div className="lg:pl-64">
        {/* Top bar */}
        <header className="sticky top-0 z-30 glass-card rounded-none border-b border-white/10">
          <div className="flex items-center justify-between px-4 py-3">
            <motion.button
              whileHover={{ scale: 1.05 }}
              whileTap={{ scale: 0.95 }}
              onClick={() => setSidebarOpen(true)}
              className="p-2 rounded-xl text-gray-400 hover:text-white hover:bg-white/10 transition-all duration-200 lg:hidden"
            >
              <Bars3Icon className="w-6 h-6" />
            </motion.button>
            
            <div className="flex items-center gap-4">
              {/* Status indicator */}
              <motion.div 
                initial={{ opacity: 0, scale: 0.9 }}
                animate={{ opacity: 1, scale: 1 }}
                className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-green-500/15 border border-green-500/30"
              >
                <span className="status-online" />
                <span className="text-xs text-green-400 font-semibold">System Online</span>
              </motion.div>
            </div>
          </div>
        </header>

        {/* Page content with animation */}
        <main className="min-h-[calc(100vh-64px)]">
          <motion.div
            key={location.pathname}
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.2, ease: 'easeOut' }}
          >
            <Outlet />
          </motion.div>
        </main>
      </div>

      {/* Mobile close button */}
      <AnimatePresence>
        {sidebarOpen && (
          <motion.button
            initial={{ opacity: 0, scale: 0.9 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 0.9 }}
            onClick={() => setSidebarOpen(false)}
            className="fixed top-4 right-4 z-50 p-2 rounded-full bg-white/10 text-white lg:hidden"
          >
            <XMarkIcon className="w-6 h-6" />
          </motion.button>
        )}
      </AnimatePresence>
    </div>
  )
}
