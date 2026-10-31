import React, { useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import useAuthStore from '../../store/authStore'
import {
  LayoutDashboard, Upload, Files, BarChart2, CreditCard,
  User, LogOut, Menu, X, Zap, ChevronRight, Star, TrendingUp
} from 'lucide-react'

const NAV = [
  { icon: LayoutDashboard, label: 'Dashboard', path: '/dashboard' },
  { icon: Upload, label: 'Upload File', path: '/upload' },
  { icon: Files, label: 'My Files', path: '/files' },
]

const NAV_BOTTOM = [
  { icon: CreditCard, label: 'Pricing', path: '/pricing' },
  { icon: User, label: 'Profile', path: '/profile' },
]

export default function AppLayout({ children }) {
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const location = useLocation()
  const navigate = useNavigate()
  const { user, logout } = useAuthStore()

  const handleLogout = () => {
    logout()
    navigate('/login')
  }

  const planColors = {
    free: 'badge-gray',
    daily: 'badge-blue',
    weekly: 'badge-amber',
    monthly: 'badge-purple',
    yearly: 'badge-green',
  }

  const Sidebar = ({ mobile = false }) => (
    <div className={`flex flex-col h-full ${mobile ? 'w-full' : 'w-64'}`}>
      {/* Logo */}
      <div className="p-5 border-b border-[var(--border)]">
        <Link to="/dashboard" className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-[var(--accent)] to-[var(--cyan)] flex items-center justify-center">
            <TrendingUp size={18} className="text-white" />
          </div>
          <div>
            <div className="text-sm font-bold text-[var(--text)]">Raas</div>
            <div className="text-[10px] text-[var(--text3)] font-mono uppercase tracking-wider">VP Research Company</div>
          </div>
        </Link>
      </div>

      {/* User info */}
      <div className="mx-3 mt-3 p-3 rounded-xl bg-[var(--surface2)] border border-[var(--border)]">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-full bg-gradient-to-br from-[var(--accent)] to-purple-600 flex items-center justify-center text-white text-sm font-bold flex-shrink-0">
            {(user?.full_name || user?.username || 'U')[0].toUpperCase()}
          </div>
          <div className="min-w-0 flex-1">
            <div className="text-sm font-semibold text-[var(--text)] truncate">{user?.full_name || user?.username}</div>
            <div className="flex items-center gap-2 mt-0.5">
              <span className={`badge text-[10px] ${planColors[user?.plan] || 'badge-gray'}`}>
                {user?.plan?.toUpperCase()}
              </span>
              <span className="text-[10px] text-[var(--text3)] font-mono">{user?.download_credits} credits</span>
            </div>
          </div>
        </div>
      </div>

      {/* Nav */}
      <nav className="flex-1 px-3 py-4 space-y-1 overflow-y-auto">
        <div className="text-[10px] font-semibold text-[var(--text3)] uppercase tracking-wider px-3 mb-2">Menu</div>
        {NAV.map(({ icon: Icon, label, path }) => (
          <Link
            key={path}
            to={path}
            onClick={() => setSidebarOpen(false)}
            className={`nav-link ${location.pathname === path ? 'active' : ''}`}
          >
            <Icon size={16} />
            <span>{label}</span>
            {location.pathname === path && <ChevronRight size={14} className="ml-auto" />}
          </Link>
        ))}

        <div className="pt-4">
          <div className="text-[10px] font-semibold text-[var(--text3)] uppercase tracking-wider px-3 mb-2">Account</div>
          {NAV_BOTTOM.map(({ icon: Icon, label, path }) => (
            <Link
              key={path}
              to={path}
              onClick={() => setSidebarOpen(false)}
              className={`nav-link ${location.pathname === path ? 'active' : ''}`}
            >
              <Icon size={16} />
              <span>{label}</span>
            </Link>
          ))}
        </div>
      </nav>

      {/* Upgrade CTA */}
      {user?.plan === 'free' && (
        <div className="mx-3 mb-3 p-3.5 rounded-xl bg-gradient-to-br from-[var(--accent)]/10 to-[var(--cyan)]/10 border border-[var(--accent)]/20">
          <div className="flex items-center gap-2 mb-2">
            <Zap size={13} className="text-[var(--accent)]" />
            <span className="text-xs font-semibold text-[var(--text)]">Upgrade Plan</span>
          </div>
          <p className="text-[11px] text-[var(--text2)] mb-2.5">Unlock AI analysis, more files & downloads</p>
          <Link to="/pricing" onClick={() => setSidebarOpen(false)} className="btn btn-primary btn-sm w-full text-xs">
            <Star size={11} /> Upgrade Now
          </Link>
        </div>
      )}

      {/* Logout */}
      <div className="p-3 border-t border-[var(--border)]">
        <button onClick={handleLogout} className="nav-link w-full text-red-400 hover:text-red-300 hover:bg-red-500/10">
          <LogOut size={16} />
          <span>Sign Out</span>
        </button>
      </div>
    </div>
  )

  return (
    <div className="min-h-screen flex bg-[var(--bg)]">
      {/* Desktop Sidebar */}
      <aside className="hidden lg:flex flex-col w-64 border-r border-[var(--border)] bg-[var(--surface)] fixed h-full z-30">
        <Sidebar />
      </aside>

      {/* Mobile Sidebar Overlay */}
      {sidebarOpen && (
        <div className="lg:hidden fixed inset-0 z-50">
          <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={() => setSidebarOpen(false)} />
          <aside className="relative w-72 h-full bg-[var(--surface)] border-r border-[var(--border)] flex flex-col">
            <button
              onClick={() => setSidebarOpen(false)}
              className="absolute top-4 right-4 p-1.5 rounded-lg hover:bg-[var(--surface2)] text-[var(--text2)]"
            >
              <X size={18} />
            </button>
            <Sidebar mobile />
          </aside>
        </div>
      )}

      {/* Main Content */}
      <div className="flex-1 lg:ml-64 flex flex-col min-h-screen">
        {/* Top bar */}
        <header className="h-14 border-b border-[var(--border)] bg-[var(--surface)]/80 backdrop-blur-sm sticky top-0 z-20 flex items-center px-4 gap-4">
          <button
            className="lg:hidden p-2 rounded-lg hover:bg-[var(--surface2)] text-[var(--text2)]"
            onClick={() => setSidebarOpen(true)}
          >
            <Menu size={20} />
          </button>

          <div className="flex-1" />

          <div className="flex items-center gap-3">
            <div className="hidden sm:flex items-center gap-2 bg-[var(--surface2)] border border-[var(--border)] px-3 py-1.5 rounded-lg">
              <Zap size={13} className="text-[var(--accent)]" />
              <span className="text-xs font-semibold text-[var(--text)]">{user?.download_credits}</span>
              <span className="text-xs text-[var(--text3)]">credits</span>
            </div>
            <div className="w-8 h-8 rounded-full bg-gradient-to-br from-[var(--accent)] to-purple-600 flex items-center justify-center text-white text-xs font-bold">
              {(user?.full_name || user?.username || 'U')[0].toUpperCase()}
            </div>
          </div>
        </header>

        {/* Page content */}
        <main className="flex-1 p-4 md:p-6 overflow-auto">
          {children}
        </main>
      </div>
    </div>
  )
}