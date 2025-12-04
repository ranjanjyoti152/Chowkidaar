import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { motion, AnimatePresence } from 'framer-motion'
import {
  UserGroupIcon,
  PlusIcon,
  PencilIcon,
  TrashIcon,
  XMarkIcon,
  ShieldCheckIcon,
  KeyIcon,
  VideoCameraIcon,
  Cog6ToothIcon,
  ChatBubbleLeftRightIcon,
  ChartBarIcon,
  BellAlertIcon,
  ComputerDesktopIcon,
  CheckCircleIcon,
  XCircleIcon,
  ClockIcon,
} from '@heroicons/react/24/outline'
import { userApi, cameraApi } from '../services'
import type { User, UserRole, Camera } from '../types'
import toast from 'react-hot-toast'

// Permission interface
interface UserPermissions {
  can_view_dashboard: boolean
  can_view_events: boolean
  can_manage_events: boolean
  can_view_cameras: boolean
  can_add_cameras: boolean
  can_edit_cameras: boolean
  can_delete_cameras: boolean
  can_view_monitor: boolean
  can_view_settings: boolean
  can_manage_settings: boolean
  can_view_users: boolean
  can_manage_users: boolean
  can_view_assistant: boolean
  allowed_camera_ids: number[] | null
}

const roleColors: Record<UserRole, string> = {
  admin: 'bg-red-500/20 text-red-400 border-red-500/30',
  operator: 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30',
  viewer: 'bg-blue-500/20 text-blue-400 border-blue-500/30',
}

const roleDescriptions: Record<UserRole, string> = {
  admin: 'Full system access including user management',
  operator: 'Can manage cameras and acknowledge events',
  viewer: 'View-only access to cameras and events',
}

// Permission categories for better organization
const permissionCategories = [
  {
    name: 'Dashboard',
    icon: ChartBarIcon,
    permissions: [
      { key: 'can_view_dashboard', label: 'View Dashboard', description: 'Access the main dashboard' },
    ],
  },
  {
    name: 'Events',
    icon: BellAlertIcon,
    permissions: [
      { key: 'can_view_events', label: 'View Events', description: 'See all events and alerts' },
      { key: 'can_manage_events', label: 'Manage Events', description: 'Acknowledge, delete events' },
    ],
  },
  {
    name: 'Cameras',
    icon: VideoCameraIcon,
    permissions: [
      { key: 'can_view_cameras', label: 'View Cameras', description: 'See camera list and details' },
      { key: 'can_add_cameras', label: 'Add Cameras', description: 'Add new cameras to the system' },
      { key: 'can_edit_cameras', label: 'Edit Cameras', description: 'Modify camera settings' },
      { key: 'can_delete_cameras', label: 'Delete Cameras', description: 'Remove cameras from system' },
    ],
  },
  {
    name: 'Monitor',
    icon: ComputerDesktopIcon,
    permissions: [
      { key: 'can_view_monitor', label: 'View Monitor', description: 'Access live camera feeds' },
    ],
  },
  {
    name: 'Settings',
    icon: Cog6ToothIcon,
    permissions: [
      { key: 'can_view_settings', label: 'View Settings', description: 'See system settings' },
      { key: 'can_manage_settings', label: 'Manage Settings', description: 'Change detection, VLM, notifications' },
    ],
  },
  {
    name: 'Users',
    icon: UserGroupIcon,
    permissions: [
      { key: 'can_view_users', label: 'View Users', description: 'See user list' },
      { key: 'can_manage_users', label: 'Manage Users', description: 'Create, edit, delete users' },
    ],
  },
  {
    name: 'AI Assistant',
    icon: ChatBubbleLeftRightIcon,
    permissions: [
      { key: 'can_view_assistant', label: 'Use Assistant', description: 'Chat with AI assistant' },
    ],
  },
]

export default function Admin() {
  const [showModal, setShowModal] = useState(false)
  const [showPermissionModal, setShowPermissionModal] = useState(false)
  const [editingUser, setEditingUser] = useState<User | null>(null)
  const [permissionUser, setPermissionUser] = useState<User | null>(null)
  const [permissions, setPermissions] = useState<UserPermissions>({
    can_view_dashboard: true,
    can_view_events: true,
    can_manage_events: false,
    can_view_cameras: true,
    can_add_cameras: false,
    can_edit_cameras: false,
    can_delete_cameras: false,
    can_view_monitor: true,
    can_view_settings: false,
    can_manage_settings: false,
    can_view_users: false,
    can_manage_users: false,
    can_view_assistant: true,
    allowed_camera_ids: null,
  })
  const [formData, setFormData] = useState({
    username: '',
    email: '',
    password: '',
    full_name: '',
    role: 'viewer' as UserRole,
    is_active: true,
  })
  const queryClient = useQueryClient()

  const { data: users, isLoading } = useQuery({
    queryKey: ['users'],
    queryFn: userApi.listUsers,
  })

  const { data: cameras } = useQuery({
    queryKey: ['cameras'],
    queryFn: cameraApi.listCameras,
  })

  const createMutation = useMutation({
    mutationFn: userApi.createUser,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['users'] })
      setShowModal(false)
      resetForm()
      toast.success('User created successfully')
    },
    onError: () => {
      toast.error('Failed to create user')
    },
  })

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: number; data: Partial<User> }) =>
      userApi.updateUser(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['users'] })
      setShowModal(false)
      setEditingUser(null)
      resetForm()
      toast.success('User updated successfully')
    },
    onError: () => {
      toast.error('Failed to update user')
    },
  })

  const deleteMutation = useMutation({
    mutationFn: userApi.deleteUser,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['users'] })
      toast.success('User deleted successfully')
    },
    onError: () => {
      toast.error('Failed to delete user')
    },
  })

  const updatePermissionsMutation = useMutation({
    mutationFn: ({ userId, permissions }: { userId: number; permissions: UserPermissions }) =>
      userApi.updateUserPermissions(userId, permissions),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['users'] })
      setShowPermissionModal(false)
      setPermissionUser(null)
      toast.success('Permissions updated successfully')
    },
    onError: () => {
      toast.error('Failed to update permissions')
    },
  })

  // Pending users query
  const { data: pendingUsers } = useQuery({
    queryKey: ['pendingUsers'],
    queryFn: userApi.getPendingUsers,
  })

  // Approve user mutation
  const approveMutation = useMutation({
    mutationFn: userApi.approveUser,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['users'] })
      queryClient.invalidateQueries({ queryKey: ['pendingUsers'] })
      toast.success('User approved successfully')
    },
    onError: () => {
      toast.error('Failed to approve user')
    },
  })

  // Reject user mutation
  const rejectMutation = useMutation({
    mutationFn: userApi.rejectUser,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['pendingUsers'] })
      toast.success('User rejected')
    },
    onError: () => {
      toast.error('Failed to reject user')
    },
  })

  const resetForm = () => {
    setFormData({
      username: '',
      email: '',
      password: '',
      full_name: '',
      role: 'viewer',
      is_active: true,
    })
  }

  const openEditModal = (user: User) => {
    setEditingUser(user)
    setFormData({
      username: user.username,
      email: user.email,
      password: '',
      full_name: user.full_name || '',
      role: user.role,
      is_active: user.is_active,
    })
    setShowModal(true)
  }

  const openPermissionModal = async (user: User) => {
    setPermissionUser(user)
    try {
      const userPermissions = await userApi.getUserPermissions(user.id)
      setPermissions(userPermissions)
    } catch {
      // Set defaults for new permission setup
      const isAdmin = user.is_superuser || user.role === 'admin'
      setPermissions({
        can_view_dashboard: true,
        can_view_events: true,
        can_manage_events: isAdmin,
        can_view_cameras: true,
        can_add_cameras: isAdmin,
        can_edit_cameras: isAdmin,
        can_delete_cameras: isAdmin,
        can_view_monitor: true,
        can_view_settings: isAdmin,
        can_manage_settings: isAdmin,
        can_view_users: isAdmin,
        can_manage_users: isAdmin,
        can_view_assistant: true,
        allowed_camera_ids: null,
      })
    }
    setShowPermissionModal(true)
  }

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (editingUser) {
      const updateData: Partial<User> = {
        email: formData.email,
        full_name: formData.full_name,
        role: formData.role,
        is_active: formData.is_active,
      }
      updateMutation.mutate({ id: editingUser.id, data: updateData })
    } else {
      createMutation.mutate(formData)
    }
  }

  const handlePermissionSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (permissionUser) {
      updatePermissionsMutation.mutate({ userId: permissionUser.id, permissions })
    }
  }

  const togglePermission = (key: string) => {
    setPermissions((prev) => ({
      ...prev,
      [key]: !prev[key as keyof UserPermissions],
    }))
  }

  const toggleCameraAccess = (cameraId: number) => {
    setPermissions((prev) => {
      const currentIds = prev.allowed_camera_ids || []
      const newIds = currentIds.includes(cameraId)
        ? currentIds.filter((id) => id !== cameraId)
        : [...currentIds, cameraId]
      return {
        ...prev,
        allowed_camera_ids: newIds.length > 0 ? newIds : null,
      }
    })
  }

  const setAllCamerasAccess = () => {
    setPermissions((prev) => ({
      ...prev,
      allowed_camera_ids: null,
    }))
  }

  return (
    <div className="page-container">
      {/* Header */}
      <div className="page-header">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-primary-500/20 flex items-center justify-center">
            <UserGroupIcon className="w-5 h-5 text-primary-400" />
          </div>
          <div>
            <h1 className="page-title">User Management</h1>
            <p className="text-gray-400 mt-1">
              {users?.length || 0} users registered
            </p>
          </div>
        </div>
        <button
          onClick={() => {
            resetForm()
            setEditingUser(null)
            setShowModal(true)
          }}
          className="btn-primary"
        >
          <PlusIcon className="w-5 h-5" />
          Add User
        </button>
      </div>

      {/* Role Legend */}
      <div className="glass-card p-4 flex flex-wrap gap-4">
        <span className="text-sm text-gray-400">Roles:</span>
        {(['admin', 'operator', 'viewer'] as UserRole[]).map((role) => (
          <div key={role} className="flex items-center gap-2">
            <span className={`badge border ${roleColors[role]}`}>{role}</span>
            <span className="text-xs text-gray-500">{roleDescriptions[role]}</span>
          </div>
        ))}
      </div>

      {/* Pending Users Section */}
      {pendingUsers && pendingUsers.length > 0 && (
        <div className="glass-card overflow-hidden border-2 border-yellow-500/30">
          <div className="p-4 bg-yellow-500/10 border-b border-yellow-500/20">
            <div className="flex items-center gap-2">
              <ClockIcon className="w-5 h-5 text-yellow-400" />
              <h2 className="text-lg font-semibold text-yellow-400">
                Pending Approvals ({pendingUsers.length})
              </h2>
            </div>
            <p className="text-sm text-gray-400 mt-1">
              These users have registered and are waiting for your approval
            </p>
          </div>
          <div className="divide-y divide-white/10">
            {pendingUsers.map((user: User) => (
              <motion.div
                key={user.id}
                initial={{ opacity: 0, y: -10 }}
                animate={{ opacity: 1, y: 0 }}
                className="p-4 flex items-center justify-between hover:bg-white/5"
              >
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-full bg-gradient-to-br from-yellow-400 to-yellow-600 flex items-center justify-center">
                    <span className="text-white font-semibold text-sm">
                      {user.username.charAt(0).toUpperCase()}
                    </span>
                  </div>
                  <div>
                    <p className="text-white font-medium">{user.username}</p>
                    <p className="text-sm text-gray-400">{user.email}</p>
                    {user.full_name && (
                      <p className="text-xs text-gray-500">{user.full_name}</p>
                    )}
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-xs text-gray-500">
                    Registered: {new Date(user.created_at).toLocaleDateString()}
                  </span>
                  <button
                    onClick={() => {
                      if (confirm(`Approve user ${user.username}?`)) {
                        approveMutation.mutate(user.id)
                      }
                    }}
                    disabled={approveMutation.isPending}
                    className="p-2 rounded-lg text-green-400 hover:bg-green-500/20 transition-colors"
                    title="Approve User"
                  >
                    <CheckCircleIcon className="w-6 h-6" />
                  </button>
                  <button
                    onClick={() => {
                      if (confirm(`Reject and delete user ${user.username}?`)) {
                        rejectMutation.mutate(user.id)
                      }
                    }}
                    disabled={rejectMutation.isPending}
                    className="p-2 rounded-lg text-red-400 hover:bg-red-500/20 transition-colors"
                    title="Reject User"
                  >
                    <XCircleIcon className="w-6 h-6" />
                  </button>
                </div>
              </motion.div>
            ))}
          </div>
        </div>
      )}

      {/* Users Table */}
      <div className="glass-card overflow-hidden">
        {isLoading ? (
          <div className="p-6 space-y-4">
            {[1, 2, 3, 4].map((i) => (
              <div key={i} className="h-16 skeleton" />
            ))}
          </div>
        ) : users && users.length > 0 ? (
          <table className="w-full">
            <thead className="bg-white/5">
              <tr>
                <th className="px-6 py-4 text-left text-sm font-medium text-gray-400">
                  User
                </th>
                <th className="px-6 py-4 text-left text-sm font-medium text-gray-400">
                  Email
                </th>
                <th className="px-6 py-4 text-left text-sm font-medium text-gray-400">
                  Role
                </th>
                <th className="px-6 py-4 text-left text-sm font-medium text-gray-400">
                  Status
                </th>
                <th className="px-6 py-4 text-right text-sm font-medium text-gray-400">
                  Actions
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-white/10">
              {users.map((user) => (
                <motion.tr
                  key={user.id}
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  className="hover:bg-white/5 transition-colors"
                >
                  <td className="px-6 py-4">
                    <div className="flex items-center gap-3">
                      <div className="w-10 h-10 rounded-full bg-gradient-to-br from-primary-400 to-primary-600 flex items-center justify-center relative">
                        <span className="text-white font-semibold text-sm">
                          {user.username.charAt(0).toUpperCase()}
                        </span>
                        {user.is_superuser && (
                          <div className="absolute -top-1 -right-1 w-4 h-4 bg-yellow-500 rounded-full flex items-center justify-center">
                            <ShieldCheckIcon className="w-3 h-3 text-black" />
                          </div>
                        )}
                      </div>
                      <div>
                        <p className="text-white font-medium flex items-center gap-2">
                          {user.username}
                          {user.is_superuser && (
                            <span className="text-xs px-1.5 py-0.5 bg-yellow-500/20 text-yellow-400 rounded">
                              Superuser
                            </span>
                          )}
                        </p>
                        {user.full_name && (
                          <p className="text-sm text-gray-400">{user.full_name}</p>
                        )}
                      </div>
                    </div>
                  </td>
                  <td className="px-6 py-4">
                    <span className="text-gray-300">{user.email}</span>
                  </td>
                  <td className="px-6 py-4">
                    <span className={`badge border ${roleColors[user.role]}`}>
                      {user.role}
                    </span>
                  </td>
                  <td className="px-6 py-4">
                    <div className="flex flex-col gap-1">
                      <span
                        className={`badge ${
                          user.is_active ? 'badge-success' : 'badge-danger'
                        }`}
                      >
                        {user.is_active ? 'Active' : 'Inactive'}
                      </span>
                      {!user.is_approved && (
                        <span className="badge bg-yellow-500/20 text-yellow-400 border border-yellow-500/30">
                          Pending
                        </span>
                      )}
                    </div>
                  </td>
                  <td className="px-6 py-4">
                    <div className="flex items-center justify-end gap-2">
                      <button
                        onClick={() => openPermissionModal(user)}
                        className="p-2 rounded-lg text-gray-400 hover:text-primary-400 hover:bg-primary-500/10 transition-colors"
                        title="Manage Permissions"
                      >
                        <KeyIcon className="w-5 h-5" />
                      </button>
                      <button
                        onClick={() => openEditModal(user)}
                        className="p-2 rounded-lg text-gray-400 hover:text-white hover:bg-white/10 transition-colors"
                        title="Edit User"
                      >
                        <PencilIcon className="w-5 h-5" />
                      </button>
                      <button
                        onClick={() => {
                          if (user.is_superuser) {
                            toast.error('Cannot delete superuser')
                            return
                          }
                          if (confirm(`Delete user ${user.username}?`)) {
                            deleteMutation.mutate(user.id)
                          }
                        }}
                        className="p-2 rounded-lg text-gray-400 hover:text-red-400 hover:bg-red-500/10 transition-colors"
                        title="Delete User"
                        disabled={user.is_superuser}
                      >
                        <TrashIcon className="w-5 h-5" />
                      </button>
                    </div>
                  </td>
                </motion.tr>
              ))}
            </tbody>
          </table>
        ) : (
          <div className="p-12 text-center">
            <UserGroupIcon className="w-12 h-12 text-gray-600 mx-auto mb-4" />
            <p className="text-gray-400">No users found</p>
          </div>
        )}
      </div>

      {/* Create/Edit Modal */}
      <AnimatePresence>
        {showModal && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm"
            onClick={() => setShowModal(false)}
          >
            <motion.div
              initial={{ scale: 0.95, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0.95, opacity: 0 }}
              onClick={(e) => e.stopPropagation()}
              className="glass-card w-full max-w-md"
            >
              {/* Header */}
              <div className="flex items-center justify-between p-4 border-b border-white/10">
                <h2 className="text-xl font-semibold text-white">
                  {editingUser ? 'Edit User' : 'Add User'}
                </h2>
                <button
                  onClick={() => setShowModal(false)}
                  className="text-gray-400 hover:text-white"
                >
                  <XMarkIcon className="w-6 h-6" />
                </button>
              </div>

              {/* Form */}
              <form onSubmit={handleSubmit} className="p-4 space-y-4">
                {!editingUser && (
                  <div>
                    <label className="block text-sm font-medium text-gray-400 mb-2">
                      Username
                    </label>
                    <input
                      type="text"
                      value={formData.username}
                      onChange={(e) =>
                        setFormData({ ...formData, username: e.target.value })
                      }
                      className="input"
                      required
                    />
                  </div>
                )}

                <div>
                  <label className="block text-sm font-medium text-gray-400 mb-2">
                    Email
                  </label>
                  <input
                    type="email"
                    value={formData.email}
                    onChange={(e) =>
                      setFormData({ ...formData, email: e.target.value })
                    }
                    className="input"
                    required
                  />
                </div>

                {!editingUser && (
                  <div>
                    <label className="block text-sm font-medium text-gray-400 mb-2">
                      Password
                    </label>
                    <input
                      type="password"
                      value={formData.password}
                      onChange={(e) =>
                        setFormData({ ...formData, password: e.target.value })
                      }
                      className="input"
                      required
                    />
                  </div>
                )}

                <div>
                  <label className="block text-sm font-medium text-gray-400 mb-2">
                    Full Name
                  </label>
                  <input
                    type="text"
                    value={formData.full_name}
                    onChange={(e) =>
                      setFormData({ ...formData, full_name: e.target.value })
                    }
                    className="input"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-400 mb-2">
                    Role
                  </label>
                  <select
                    value={formData.role}
                    onChange={(e) =>
                      setFormData({ ...formData, role: e.target.value as UserRole })
                    }
                    className="input"
                  >
                    <option value="viewer">Viewer</option>
                    <option value="operator">Operator</option>
                    <option value="admin">Admin</option>
                  </select>
                </div>

                {editingUser && (
                  <div className="flex items-center justify-between p-4 rounded-xl bg-white/5">
                    <div>
                      <p className="text-white font-medium">Active Status</p>
                      <p className="text-sm text-gray-400">
                        Inactive users cannot log in
                      </p>
                    </div>
                    <button
                      type="button"
                      onClick={() =>
                        setFormData({ ...formData, is_active: !formData.is_active })
                      }
                      className={`relative w-12 h-6 rounded-full transition-colors ${
                        formData.is_active ? 'bg-primary-500' : 'bg-white/20'
                      }`}
                    >
                      <div
                        className={`absolute top-1 w-4 h-4 rounded-full bg-white transition-transform ${
                          formData.is_active ? 'translate-x-7' : 'translate-x-1'
                        }`}
                      />
                    </button>
                  </div>
                )}

                {/* Actions */}
                <div className="flex gap-3 pt-4">
                  <button
                    type="button"
                    onClick={() => setShowModal(false)}
                    className="btn-secondary flex-1"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    disabled={createMutation.isPending || updateMutation.isPending}
                    className="btn-primary flex-1"
                  >
                    {createMutation.isPending || updateMutation.isPending
                      ? 'Saving...'
                      : editingUser
                      ? 'Update User'
                      : 'Create User'}
                  </button>
                </div>
              </form>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Permission Management Modal */}
      <AnimatePresence>
        {showPermissionModal && permissionUser && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm"
            onClick={() => setShowPermissionModal(false)}
          >
            <motion.div
              initial={{ scale: 0.95, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0.95, opacity: 0 }}
              onClick={(e) => e.stopPropagation()}
              className="glass-card w-full max-w-2xl max-h-[90vh] overflow-y-auto"
            >
              {/* Header */}
              <div className="flex items-center justify-between p-4 border-b border-white/10 sticky top-0 bg-gray-900/95 backdrop-blur z-10">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-xl bg-primary-500/20 flex items-center justify-center">
                    <KeyIcon className="w-5 h-5 text-primary-400" />
                  </div>
                  <div>
                    <h2 className="text-xl font-semibold text-white">
                      Manage Permissions
                    </h2>
                    <p className="text-sm text-gray-400">
                      {permissionUser.username} ({permissionUser.email})
                    </p>
                  </div>
                </div>
                <button
                  onClick={() => setShowPermissionModal(false)}
                  className="text-gray-400 hover:text-white"
                >
                  <XMarkIcon className="w-6 h-6" />
                </button>
              </div>

              {/* Superuser Notice */}
              {permissionUser.is_superuser && (
                <div className="mx-4 mt-4 p-4 bg-yellow-500/10 border border-yellow-500/30 rounded-xl">
                  <div className="flex items-center gap-2 text-yellow-400">
                    <ShieldCheckIcon className="w-5 h-5" />
                    <span className="font-medium">Superuser Account</span>
                  </div>
                  <p className="text-sm text-gray-400 mt-1">
                    This user has superuser privileges and bypasses all permission checks.
                  </p>
                </div>
              )}

              {/* Permission Form */}
              <form onSubmit={handlePermissionSubmit} className="p-4 space-y-6">
                {/* Permission Categories */}
                {permissionCategories.map((category) => (
                  <div key={category.name} className="space-y-3">
                    <div className="flex items-center gap-2 text-white font-medium">
                      <category.icon className="w-5 h-5 text-primary-400" />
                      {category.name}
                    </div>
                    <div className="grid gap-2">
                      {category.permissions.map((perm) => (
                        <div
                          key={perm.key}
                          className="flex items-center justify-between p-3 rounded-xl bg-white/5 hover:bg-white/10 transition-colors"
                        >
                          <div>
                            <p className="text-white font-medium">{perm.label}</p>
                            <p className="text-sm text-gray-400">{perm.description}</p>
                          </div>
                          <button
                            type="button"
                            onClick={() => togglePermission(perm.key)}
                            disabled={permissionUser.is_superuser}
                            className={`relative w-12 h-6 rounded-full transition-colors ${
                              permissions[perm.key as keyof UserPermissions]
                                ? 'bg-primary-500'
                                : 'bg-white/20'
                            } ${permissionUser.is_superuser ? 'opacity-50 cursor-not-allowed' : ''}`}
                          >
                            <div
                              className={`absolute top-1 w-4 h-4 rounded-full bg-white transition-transform ${
                                permissions[perm.key as keyof UserPermissions]
                                  ? 'translate-x-7'
                                  : 'translate-x-1'
                              }`}
                            />
                          </button>
                        </div>
                      ))}
                    </div>
                  </div>
                ))}

                {/* Camera Access */}
                {cameras && cameras.length > 0 && (
                  <div className="space-y-3">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2 text-white font-medium">
                        <VideoCameraIcon className="w-5 h-5 text-primary-400" />
                        Camera Access
                      </div>
                      <button
                        type="button"
                        onClick={setAllCamerasAccess}
                        className="text-sm text-primary-400 hover:text-primary-300"
                      >
                        {permissions.allowed_camera_ids === null
                          ? 'All cameras'
                          : 'Grant all access'}
                      </button>
                    </div>
                    <p className="text-sm text-gray-400">
                      {permissions.allowed_camera_ids === null
                        ? 'User has access to all cameras'
                        : `User has access to ${permissions.allowed_camera_ids.length} camera(s)`}
                    </p>
                    <div className="grid grid-cols-2 gap-2">
                      {cameras.map((camera: Camera) => (
                        <div
                          key={camera.id}
                          onClick={() => toggleCameraAccess(camera.id)}
                          className={`p-3 rounded-xl cursor-pointer transition-all ${
                            permissions.allowed_camera_ids === null ||
                            permissions.allowed_camera_ids.includes(camera.id)
                              ? 'bg-primary-500/20 border border-primary-500/50'
                              : 'bg-white/5 border border-transparent hover:border-white/20'
                          }`}
                        >
                          <div className="flex items-center gap-2">
                            <VideoCameraIcon className="w-4 h-4 text-gray-400" />
                            <span className="text-white text-sm">{camera.name}</span>
                          </div>
                          {camera.location && (
                            <p className="text-xs text-gray-500 mt-1">{camera.location}</p>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Actions */}
                <div className="flex gap-3 pt-4 sticky bottom-0 bg-gray-900/95 backdrop-blur py-4 -mx-4 px-4 border-t border-white/10">
                  <button
                    type="button"
                    onClick={() => setShowPermissionModal(false)}
                    className="btn-secondary flex-1"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    disabled={updatePermissionsMutation.isPending || permissionUser.is_superuser}
                    className="btn-primary flex-1"
                  >
                    {updatePermissionsMutation.isPending
                      ? 'Saving...'
                      : 'Save Permissions'}
                  </button>
                </div>
              </form>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}
