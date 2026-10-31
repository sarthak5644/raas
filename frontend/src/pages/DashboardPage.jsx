import React, { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import api from '../utils/api'
import useAuthStore from '../store/authStore'
import {
  FileSpreadsheet, BarChart2, CreditCard, TrendingUp,
  Upload, ArrowRight, Zap, Clock, Star
} from 'lucide-react'
import { formatDistanceToNow } from 'date-fns'

function StatCard({ icon: Icon, label, value, sub, color = 'accent' }) {
  const colors = {
    accent: 'from-[var(--accent)]/20 to-[var(--accent)]/5 border-[var(--accent)]/20',
    green: 'from-green-500/20 to-green-500/5 border-green-500/20',
    amber: 'from-amber-500/20 to-amber-500/5 border-amber-500/20',
    cyan: 'from-cyan-500/20 to-cyan-500/5 border-cyan-500/20',
  }
  const iconColors = { accent: 'text-[var(--accent)]', green: 'text-green-400', amber: 'text-amber-400', cyan: 'text-cyan-400' }
  return (
    <div className={`card p-5 bg-gradient-to-br ${colors[color]}`}>
      <div className="flex items-start justify-between mb-4">
        <div className={`w-10 h-10 rounded-xl bg-[var(--surface)] flex items-center justify-center ${iconColors[color]}`}>
          <Icon size={20} />
        </div>
      </div>
      <div className="text-2xl font-bold text-[var(--text)] mb-0.5">{value}</div>
      <div className="text-sm font-medium text-[var(--text2)]">{label}</div>
      {sub && <div className="text-xs text-[var(--text3)] mt-1">{sub}</div>}
    </div>
  )
}

function QualityBadge({ score }) {
  if (score >= 80) return <span className="badge-green badge">{score}</span>
  if (score >= 50) return <span className="badge-amber badge">{score}</span>
  return <span className="badge-red badge">{score}</span>
}

export default function DashboardPage() {
  const { user } = useAuthStore()
  const [stats, setStats] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    api.get('/user/dashboard-stats').then(r => {
      setStats(r.data)
      setLoading(false)
    }).catch(() => setLoading(false))
  }, [])

  const planLimits = { free: 5, daily: 10, weekly: 40, monthly: 150, yearly: 999 }
  const fileLimit = planLimits[user?.plan] || 5
  const fileUsed = stats?.stats?.total_files || 0

  if (loading) return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {[...Array(4)].map((_, i) => <div key={i} className="skeleton h-28 rounded-2xl" />)}
      </div>
      <div className="grid lg:grid-cols-2 gap-4">
        {[...Array(2)].map((_, i) => <div key={i} className="skeleton h-64 rounded-2xl" />)}
      </div>
    </div>
  )

  return (
    <div className="space-y-6 stagger">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-[var(--text)]">
            Good {new Date().getHours() < 12 ? 'morning' : new Date().getHours() < 18 ? 'afternoon' : 'evening'},
            {' '}<span className="gradient-text">{user?.full_name?.split(' ')[0] || user?.username}</span> 👋
          </h1>
          <p className="text-sm text-[var(--text2)] mt-0.5">Here's your analytics overview</p>
        </div>
        <Link to="/upload" className="btn btn-primary btn-md">
          <Upload size={16} /> Upload File
        </Link>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard icon={FileSpreadsheet} label="Files Uploaded" value={stats?.stats?.total_files || 0}
          sub={`of ${fileLimit === 999 ? '∞' : fileLimit} allowed`} color="accent" />
        <StatCard icon={BarChart2} label="Analyses Run" value={stats?.stats?.total_analyses || 0} color="green" />
        <StatCard icon={CreditCard} label="Download Credits" value={user?.download_credits || 0}
          sub="Credits remaining" color="amber" />
        <StatCard icon={Star} label="Current Plan" value={(user?.plan || 'Free').toUpperCase()}
          sub={user?.plan_expiry ? `Expires ${new Date(user.plan_expiry).toLocaleDateString()}` : 'No expiry'} color="cyan" />
      </div>

      {/* File Usage Bar */}
      {user?.plan !== 'yearly' && (
        <div className="card p-4 flex items-center gap-4">
          <div className="flex-1">
            <div className="flex justify-between text-xs mb-2">
              <span className="text-[var(--text2)] font-medium">File Storage Usage</span>
              <span className="text-[var(--text3)]">{fileUsed} / {fileLimit} files</span>
            </div>
            <div className="progress-bar">
              <div className="progress-fill" style={{
                width: `${Math.min((fileUsed / fileLimit) * 100, 100)}%`,
                background: fileUsed / fileLimit > 0.8 ? '#DC2626' : fileUsed / fileLimit > 0.5 ? '#D97706' : 'var(--accent)'
              }} />
            </div>
          </div>
          {user?.plan === 'free' && (
            <Link to="/pricing" className="btn btn-secondary btn-sm flex-shrink-0">
              <Zap size={13} /> Upgrade
            </Link>
          )}
        </div>
      )}

      {/* Upgrade Banner for free users */}
      {user?.plan === 'free' && (
        <div className="card p-5 bg-gradient-to-r from-[var(--accent)]/10 via-[var(--surface)] to-cyan-500/10 border-[var(--accent)]/20">
          <div className="flex flex-col sm:flex-row items-start sm:items-center gap-4">
            <div className="flex-1">
              <h3 className="font-semibold text-[var(--text)] flex items-center gap-2">
                <Zap size={16} className="text-[var(--accent)]" /> Unlock the full platform
              </h3>
              <p className="text-sm text-[var(--text2)] mt-1">Get AI Insights, the Advanced Analytics Engine, unlimited downloads and more with a paid plan.</p>
            </div>
            <Link to="/pricing" className="btn btn-primary btn-md flex-shrink-0">
              See Plans <ArrowRight size={16} />
            </Link>
          </div>
        </div>
      )}

      {/* Recent Files + Analyses */}
      <div className="grid lg:grid-cols-2 gap-4">
        {/* Recent Files */}
        <div className="card p-5">
          <div className="flex items-center justify-between mb-4">
            <h2 className="section-title">Recent Files</h2>
            <Link to="/files" className="text-xs text-[var(--accent)] hover:underline flex items-center gap-1">
              View all <ArrowRight size={12} />
            </Link>
          </div>
          {!stats?.recent_files?.length ? (
            <div className="text-center py-8">
              <FileSpreadsheet size={32} className="text-[var(--text3)] mx-auto mb-2" />
              <p className="text-sm text-[var(--text2)]">No files yet</p>
              <Link to="/upload" className="btn btn-primary btn-sm mt-3 inline-flex">Upload your first file</Link>
            </div>
          ) : (
            <div className="space-y-2">
              {stats.recent_files.map(file => (
                <Link key={file.id} to={`/analysis/${file.id}`}
                  className="flex items-center gap-3 p-3 rounded-xl hover:bg-[var(--surface2)] transition-colors group">
                  <div className="w-9 h-9 rounded-lg bg-green-500/10 flex items-center justify-center flex-shrink-0">
                    <FileSpreadsheet size={16} className="text-green-400" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-[var(--text)] truncate group-hover:text-[var(--accent)]">
                      {file.original_name}
                    </p>
                    <p className="text-xs text-[var(--text3)]">{file.total_rows} rows · {file.total_cols} cols</p>
                  </div>
                  {file.data_quality_score && <QualityBadge score={Math.round(file.data_quality_score)} />}
                </Link>
              ))}
            </div>
          )}
        </div>

        {/* Recent Analyses */}
        <div className="card p-5">
          <div className="flex items-center justify-between mb-4">
            <h2 className="section-title">Recent Analyses</h2>
          </div>
          {!stats?.recent_analyses?.length ? (
            <div className="text-center py-8">
              <BarChart2 size={32} className="text-[var(--text3)] mx-auto mb-2" />
              <p className="text-sm text-[var(--text2)]">No analyses yet</p>
              <p className="text-xs text-[var(--text3)] mt-1">Upload a file to get started</p>
            </div>
          ) : (
            <div className="space-y-2">
              {stats.recent_analyses.map(a => (
                <div key={a.id} className="flex items-center gap-3 p-3 rounded-xl">
                  <div className="w-9 h-9 rounded-lg bg-[var(--accent)]/10 flex items-center justify-center flex-shrink-0">
                    <TrendingUp size={16} className="text-[var(--accent)]" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-[var(--text)] truncate">{a.title}</p>
                    <p className="text-xs text-[var(--text3)] flex items-center gap-1">
                      <Clock size={11} />
                      {formatDistanceToNow(new Date(a.created_at), { addSuffix: true })}
                    </p>
                  </div>
                  <span className={`badge ${a.status === 'done' ? 'badge-green' : 'badge-amber'}`}>{a.status}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
