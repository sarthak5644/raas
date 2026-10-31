import React, { useEffect, useState, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import axios from 'axios'
import toast from 'react-hot-toast'
import {
  Users, FileSpreadsheet, BarChart3, CreditCard, ShieldCheck, ShieldAlert,
  ShieldQuestion, LogOut, RefreshCw, Search, ChevronLeft, ChevronRight,
  CheckCircle2, XCircle, Clock, Sparkles, Cpu, Edit3, Trash2, X,
} from 'lucide-react'

const PURPLE  = '#6B2D8B'
const PURPLE2 = '#8B4DB0'
const GOLD    = '#C8860B'
const GREEN   = '#16A34A'
const RED     = '#DC2626'
const AMBER   = '#D97706'
const TEXT    = '#241B33'
const TEXT2   = '#6B6280'
const TEXT3   = '#A89FBC'
const BORDER  = 'rgba(107,45,139,0.10)'
const SURFACE = '#F7F2FB'

// ── Admin API client (separate token from normal user) ────────────────────
const adminApi = axios.create({ baseURL: '/api/admin', timeout: 30000 })
adminApi.interceptors.request.use(config => {
  const token = localStorage.getItem('admin_token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

function StatCard({ icon: Icon, label, value, color, sub }) {
  return (
    <div className="card" style={{ padding: '18px', display: 'flex', alignItems: 'center', gap: '14px' }}>
      <div style={{ width: 44, height: 44, borderRadius: 12, background: `${color}15`, display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
        <Icon size={20} style={{ color }} />
      </div>
      <div>
        <p style={{ fontSize: 11, color: TEXT3, textTransform: 'uppercase', letterSpacing: '0.06em', margin: 0 }}>{label}</p>
        <p style={{ fontSize: 22, fontWeight: 700, color: TEXT, margin: '4px 0 0' }}>{value}</p>
        {sub && <p style={{ fontSize: 11, color: TEXT3, margin: '2px 0 0' }}>{sub}</p>}
      </div>
    </div>
  )
}

function VerifyBadge({ verified, method }) {
  if (verified === null || verified === undefined) {
    return <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4, fontSize: 11, fontWeight: 600, color: TEXT3, background: SURFACE, padding: '3px 9px', borderRadius: 999 }}>
      <Clock size={11} /> Pending
    </span>
  }
  if (verified) {
    const isAI = method === 'ai'
    return <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4, fontSize: 11, fontWeight: 600, color: GREEN, background: 'rgba(22,163,74,0.08)', padding: '3px 9px', borderRadius: 999 }}>
      {isAI ? <Sparkles size={11} /> : <Cpu size={11} />} Verified {isAI ? '(AI)' : method === 'manual' ? '(Manual)' : '(Local)'}
    </span>
  }
  return <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4, fontSize: 11, fontWeight: 600, color: RED, background: 'rgba(220,38,38,0.08)', padding: '3px 9px', borderRadius: 999 }}>
    <XCircle size={11} /> Needs Review
  </span>
}

function Pagination({ page, totalPages, onChange }) {
  if (totalPages <= 1) return null
  return (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 10, padding: '14px 0' }}>
      <button onClick={() => onChange(page - 1)} disabled={page <= 1}
        style={{ background: 'none', border: `1px solid ${BORDER}`, borderRadius: 8, padding: '6px 8px', cursor: page <= 1 ? 'not-allowed' : 'pointer', opacity: page <= 1 ? 0.4 : 1 }}>
        <ChevronLeft size={14} />
      </button>
      <span style={{ fontSize: 12, color: TEXT2 }}>Page {page} of {totalPages}</span>
      <button onClick={() => onChange(page + 1)} disabled={page >= totalPages}
        style={{ background: 'none', border: `1px solid ${BORDER}`, borderRadius: 8, padding: '6px 8px', cursor: page >= totalPages ? 'not-allowed' : 'pointer', opacity: page >= totalPages ? 0.4 : 1 }}>
        <ChevronRight size={14} />
      </button>
    </div>
  )
}

// ── Users Tab ────────────────────────────────────────────────────────────
function UsersTab() {
  const [users, setUsers] = useState([])
  const [loading, setLoading] = useState(true)
  const [page, setPage] = useState(1)
  const [totalPages, setTotalPages] = useState(1)
  const [search, setSearch] = useState('')
  const [editingUser, setEditingUser] = useState(null)

  const load = useCallback(() => {
    setLoading(true)
    adminApi.get('/users', { params: { page, per_page: 15, search } })
      .then(r => { setUsers(r.data.users); setTotalPages(r.data.total_pages); setLoading(false) })
      .catch(() => { toast.error('Failed to load users'); setLoading(false) })
  }, [page, search])

  useEffect(() => { load() }, [load])

  const saveUser = async (userId, updates) => {
    try {
      await adminApi.patch(`/users/${userId}`, updates)
      toast.success('User updated')
      setEditingUser(null)
      load()
    } catch (e) {
      toast.error(e.response?.data?.error || 'Update failed')
    }
  }

  const deleteUser = async (userId) => {
    if (!window.confirm('Delete this user permanently? This cannot be undone.')) return
    try {
      await adminApi.delete(`/users/${userId}`)
      toast.success('User deleted')
      load()
    } catch (e) {
      toast.error(e.response?.data?.error || 'Delete failed')
    }
  }

  return (
    <div>
      <div style={{ display: 'flex', gap: 10, marginBottom: 16 }}>
        <div style={{ position: 'relative', flex: 1, maxWidth: 320 }}>
          <Search size={14} style={{ position: 'absolute', left: 12, top: '50%', transform: 'translateY(-50%)', color: TEXT3 }} />
          <input
            value={search}
            onChange={e => { setSearch(e.target.value); setPage(1) }}
            placeholder="Search by email, username, name…"
            style={{ width: '100%', boxSizing: 'border-box', padding: '9px 12px 9px 34px', fontSize: 13, border: `1px solid ${BORDER}`, borderRadius: 10, outline: 'none' }}
          />
        </div>
      </div>

      <div className="card" style={{ overflow: 'auto' }}>
        <table className="table">
          <thead>
            <tr>
              <th>User</th><th>Plan</th><th>Credits</th><th>Files</th><th>Analyses</th><th>Status</th><th>Joined</th><th></th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr><td colSpan={8} style={{ textAlign: 'center', padding: 30, color: TEXT3 }}>Loading…</td></tr>
            ) : users.length === 0 ? (
              <tr><td colSpan={8} style={{ textAlign: 'center', padding: 30, color: TEXT3 }}>No users found.</td></tr>
            ) : users.map(u => (
              <tr key={u.id}>
                <td>
                  <p style={{ fontWeight: 600, color: TEXT, margin: 0 }}>{u.full_name || u.username}</p>
                  <p style={{ fontSize: 11, color: TEXT3, margin: 0 }}>{u.email} {u.is_admin && <span style={{ color: PURPLE, fontWeight: 700 }}>· ADMIN</span>}</p>
                </td>
                <td><span className="badge badge-purple" style={{ textTransform: 'capitalize' }}>{u.plan}</span></td>
                <td>{u.download_credits}</td>
                <td>{u.file_count}</td>
                <td>{u.analysis_count}</td>
                <td>{u.is_active ? <span style={{ color: GREEN, fontSize: 12 }}>Active</span> : <span style={{ color: RED, fontSize: 12 }}>Disabled</span>}</td>
                <td style={{ fontSize: 12, color: TEXT3 }}>{new Date(u.created_at).toLocaleDateString()}</td>
                <td>
                  <div style={{ display: 'flex', gap: 6 }}>
                    <button onClick={() => setEditingUser(u)} style={{ background: 'none', border: `1px solid ${BORDER}`, borderRadius: 6, padding: 5, cursor: 'pointer' }}>
                      <Edit3 size={13} style={{ color: PURPLE }} />
                    </button>
                    <button onClick={() => deleteUser(u.id)} style={{ background: 'none', border: `1px solid ${BORDER}`, borderRadius: 6, padding: 5, cursor: 'pointer' }}>
                      <Trash2 size={13} style={{ color: RED }} />
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <Pagination page={page} totalPages={totalPages} onChange={setPage} />

      {editingUser && (
        <EditUserModal user={editingUser} onClose={() => setEditingUser(null)} onSave={saveUser} />
      )}
    </div>
  )
}

function EditUserModal({ user, onClose, onSave }) {
  const [plan, setPlan] = useState(user.plan)
  const [credits, setCredits] = useState(user.download_credits)
  const [isActive, setIsActive] = useState(user.is_active)
  const [isAdmin, setIsAdmin] = useState(user.is_admin)

  return (
    <div style={{ position: 'fixed', inset: 0, background: 'rgba(36,27,51,0.5)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000, padding: 20 }}>
      <div style={{ background: '#fff', borderRadius: 16, padding: 24, width: '100%', maxWidth: 400 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
          <h3 style={{ fontSize: 16, fontWeight: 700, color: TEXT, margin: 0 }}>Edit {user.username}</h3>
          <button onClick={onClose} style={{ background: 'none', border: 'none', cursor: 'pointer' }}><X size={18} /></button>
        </div>

        <label style={{ fontSize: 12, fontWeight: 600, color: TEXT2, display: 'block', marginBottom: 4 }}>Plan</label>
        <select value={plan} onChange={e => setPlan(e.target.value)} className="input" style={{ width: '100%', marginBottom: 14 }}>
          {['free', 'daily', 'weekly', 'monthly', 'yearly'].map(p => <option key={p} value={p}>{p}</option>)}
        </select>

        <label style={{ fontSize: 12, fontWeight: 600, color: TEXT2, display: 'block', marginBottom: 4 }}>Download Credits</label>
        <input type="number" value={credits} onChange={e => setCredits(e.target.value)} className="input" style={{ width: '100%', boxSizing: 'border-box', marginBottom: 14 }} />

        <label style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10, fontSize: 13, color: TEXT }}>
          <input type="checkbox" checked={isActive} onChange={e => setIsActive(e.target.checked)} /> Account Active
        </label>
        <label style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 20, fontSize: 13, color: TEXT }}>
          <input type="checkbox" checked={isAdmin} onChange={e => setIsAdmin(e.target.checked)} /> Admin Access
        </label>

        <button
          onClick={() => onSave(user.id, { plan, download_credits: Number(credits), is_active: isActive, is_admin: isAdmin })}
          style={{ width: '100%', padding: '11px', borderRadius: 10, border: 'none', background: PURPLE, color: '#fff', fontWeight: 700, cursor: 'pointer' }}>
          Save Changes
        </button>
      </div>
    </div>
  )
}

// ── Files Tab (the core "AI verification" view) ───────────────────────────
function FilesTab() {
  const [files, setFiles] = useState([])
  const [loading, setLoading] = useState(true)
  const [page, setPage] = useState(1)
  const [totalPages, setTotalPages] = useState(1)
  const [verifiedFilter, setVerifiedFilter] = useState('')
  const [search, setSearch] = useState('')
  const [reverifyingId, setReverifyingId] = useState(null)

  const load = useCallback(() => {
    setLoading(true)
    adminApi.get('/files', { params: { page, per_page: 15, verified: verifiedFilter, search } })
      .then(r => { setFiles(r.data.files); setTotalPages(r.data.total_pages); setLoading(false) })
      .catch(() => { toast.error('Failed to load files'); setLoading(false) })
  }, [page, verifiedFilter, search])

  useEffect(() => { load() }, [load])

  const reverify = async (fileId, useAi) => {
    setReverifyingId(fileId)
    try {
      await adminApi.post(`/files/${fileId}/reverify`, { use_ai: useAi })
      toast.success(useAi ? 'Re-verified using AI' : 'Re-verified using local check')
      load()
    } catch (e) {
      toast.error(e.response?.data?.error || 'Re-verification failed')
    } finally {
      setReverifyingId(null)
    }
  }

  const override = async (fileId, verified) => {
    try {
      await adminApi.post(`/files/${fileId}/override`, { verified, notes: `Manually marked ${verified ? 'verified' : 'unverified'} by admin.` })
      toast.success('Override applied')
      load()
    } catch (e) {
      toast.error('Override failed')
    }
  }

  return (
    <div>
      <div style={{ display: 'flex', gap: 10, marginBottom: 16, flexWrap: 'wrap' }}>
        <div style={{ position: 'relative', flex: 1, maxWidth: 280 }}>
          <Search size={14} style={{ position: 'absolute', left: 12, top: '50%', transform: 'translateY(-50%)', color: TEXT3 }} />
          <input
            value={search}
            onChange={e => { setSearch(e.target.value); setPage(1) }}
            placeholder="Search file name…"
            style={{ width: '100%', boxSizing: 'border-box', padding: '9px 12px 9px 34px', fontSize: 13, border: `1px solid ${BORDER}`, borderRadius: 10, outline: 'none' }}
          />
        </div>
        <div style={{ display: 'flex', gap: 6 }}>
          {[
            { v: '', label: 'All' },
            { v: 'true', label: 'Verified' },
            { v: 'false', label: 'Needs Review' },
            { v: 'pending', label: 'Pending' },
          ].map(f => (
            <button key={f.v} onClick={() => { setVerifiedFilter(f.v); setPage(1) }}
              style={{
                padding: '8px 14px', borderRadius: 8, fontSize: 12, fontWeight: 600, cursor: 'pointer',
                border: verifiedFilter === f.v ? `1px solid ${PURPLE}` : `1px solid ${BORDER}`,
                background: verifiedFilter === f.v ? 'rgba(107,45,139,0.08)' : '#fff',
                color: verifiedFilter === f.v ? PURPLE : TEXT2,
              }}>
              {f.label}
            </button>
          ))}
        </div>
      </div>

      <div className="card" style={{ overflow: 'auto' }}>
        <table className="table">
          <thead>
            <tr>
              <th>File</th><th>Owner</th><th>Detected Type</th><th>Verification</th><th>Notes</th><th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr><td colSpan={6} style={{ textAlign: 'center', padding: 30, color: TEXT3 }}>Loading…</td></tr>
            ) : files.length === 0 ? (
              <tr><td colSpan={6} style={{ textAlign: 'center', padding: 30, color: TEXT3 }}>No files found.</td></tr>
            ) : files.map(f => (
              <tr key={f.id}>
                <td>
                  <p style={{ fontWeight: 600, color: TEXT, margin: 0, maxWidth: 220, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{f.original_name}</p>
                  <p style={{ fontSize: 11, color: TEXT3, margin: 0 }}>{f.total_rows} rows · {f.total_cols} cols</p>
                </td>
                <td style={{ fontSize: 12 }}>{f.owner_email || '—'}</td>
                <td><span className="badge badge-purple">{f.detected_data_type || 'Unknown'}</span></td>
                <td><VerifyBadge verified={f.ai_verified} method={f.ai_verification_method} /></td>
                <td style={{ fontSize: 11, color: TEXT2, maxWidth: 240 }}>{f.ai_verification_notes || '—'}</td>
                <td>
                  <div style={{ display: 'flex', gap: 5, flexWrap: 'wrap' }}>
                    <button onClick={() => reverify(f.id, true)} disabled={reverifyingId === f.id}
                      title="Re-verify with AI"
                      style={{ display: 'flex', alignItems: 'center', gap: 3, fontSize: 10, fontWeight: 600, padding: '4px 8px', borderRadius: 6, border: `1px solid ${BORDER}`, background: '#fff', color: PURPLE, cursor: 'pointer' }}>
                      {reverifyingId === f.id ? <RefreshCw size={10} style={{ animation: 'spin 1s linear infinite' }} /> : <Sparkles size={10} />} AI
                    </button>
                    <button onClick={() => reverify(f.id, false)} disabled={reverifyingId === f.id}
                      title="Re-verify locally"
                      style={{ display: 'flex', alignItems: 'center', gap: 3, fontSize: 10, fontWeight: 600, padding: '4px 8px', borderRadius: 6, border: `1px solid ${BORDER}`, background: '#fff', color: TEXT2, cursor: 'pointer' }}>
                      <Cpu size={10} /> Local
                    </button>
                    <button onClick={() => override(f.id, true)} title="Mark verified"
                      style={{ background: 'none', border: `1px solid rgba(22,163,74,0.3)`, borderRadius: 6, padding: '4px 6px', cursor: 'pointer' }}>
                      <CheckCircle2 size={11} style={{ color: GREEN }} />
                    </button>
                    <button onClick={() => override(f.id, false)} title="Mark needs review"
                      style={{ background: 'none', border: `1px solid rgba(220,38,38,0.3)`, borderRadius: 6, padding: '4px 6px', cursor: 'pointer' }}>
                      <XCircle size={11} style={{ color: RED }} />
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <Pagination page={page} totalPages={totalPages} onChange={setPage} />
      <style>{`@keyframes spin{from{transform:rotate(0deg)}to{transform:rotate(360deg)}}`}</style>
    </div>
  )
}

// ── Analyses Tab ───────────────────────────────────────────────────────────
function AnalysesTab() {
  const [analyses, setAnalyses] = useState([])
  const [loading, setLoading] = useState(true)
  const [page, setPage] = useState(1)
  const [totalPages, setTotalPages] = useState(1)

  useEffect(() => {
    setLoading(true)
    adminApi.get('/analyses', { params: { page, per_page: 15 } })
      .then(r => { setAnalyses(r.data.analyses); setTotalPages(r.data.total_pages); setLoading(false) })
      .catch(() => { toast.error('Failed to load analyses'); setLoading(false) })
  }, [page])

  return (
    <div>
      <div className="card" style={{ overflow: 'auto' }}>
        <table className="table">
          <thead><tr><th>Analysis</th><th>File</th><th>User</th><th>Status</th><th>Date</th></tr></thead>
          <tbody>
            {loading ? (
              <tr><td colSpan={5} style={{ textAlign: 'center', padding: 30, color: TEXT3 }}>Loading…</td></tr>
            ) : analyses.length === 0 ? (
              <tr><td colSpan={5} style={{ textAlign: 'center', padding: 30, color: TEXT3 }}>No analyses yet.</td></tr>
            ) : analyses.map(a => (
              <tr key={a.id}>
                <td style={{ fontSize: 12, fontWeight: 600, color: TEXT }}>{a.title}</td>
                <td style={{ fontSize: 12, color: TEXT2 }}>{a.file_name || '—'}</td>
                <td style={{ fontSize: 12, color: TEXT2 }}>{a.owner_email || '—'}</td>
                <td>{a.status === 'done' ? <span style={{ color: GREEN, fontSize: 12 }}>Done</span> : <span style={{ color: AMBER, fontSize: 12 }}>{a.status}</span>}</td>
                <td style={{ fontSize: 11, color: TEXT3 }}>{new Date(a.created_at).toLocaleString()}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <Pagination page={page} totalPages={totalPages} onChange={setPage} />
    </div>
  )
}

// ── Payments Tab ────────────────────────────────────────────────────────────
function PaymentsTab() {
  const [payments, setPayments] = useState([])
  const [loading, setLoading] = useState(true)
  const [page, setPage] = useState(1)
  const [totalPages, setTotalPages] = useState(1)

  useEffect(() => {
    setLoading(true)
    adminApi.get('/payments', { params: { page, per_page: 15 } })
      .then(r => { setPayments(r.data.payments); setTotalPages(r.data.total_pages); setLoading(false) })
      .catch(() => { toast.error('Failed to load payments'); setLoading(false) })
  }, [page])

  return (
    <div>
      <div className="card" style={{ overflow: 'auto' }}>
        <table className="table">
          <thead><tr><th>User</th><th>Plan</th><th>Amount</th><th>Status</th><th>Date</th></tr></thead>
          <tbody>
            {loading ? (
              <tr><td colSpan={5} style={{ textAlign: 'center', padding: 30, color: TEXT3 }}>Loading…</td></tr>
            ) : payments.length === 0 ? (
              <tr><td colSpan={5} style={{ textAlign: 'center', padding: 30, color: TEXT3 }}>No payments yet.</td></tr>
            ) : payments.map(p => (
              <tr key={p.id}>
                <td style={{ fontSize: 12 }}>{p.owner_email || '—'}</td>
                <td><span className="badge badge-purple" style={{ textTransform: 'capitalize' }}>{p.plan}</span></td>
                <td style={{ fontWeight: 600 }}>₹{p.amount}</td>
                <td>{p.status === 'paid' ? <span style={{ color: GREEN, fontSize: 12 }}>Paid</span> : <span style={{ color: RED, fontSize: 12 }}>{p.status}</span>}</td>
                <td style={{ fontSize: 11, color: TEXT3 }}>{new Date(p.created_at).toLocaleDateString()}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <Pagination page={page} totalPages={totalPages} onChange={setPage} />
    </div>
  )
}

// ── Main Admin Dashboard ────────────────────────────────────────────────────
export default function AdminDashboardPage() {
  const navigate = useNavigate()
  const [stats, setStats] = useState(null)
  const [activeTab, setActiveTab] = useState('overview')
  const [adminUser, setAdminUser] = useState(null)

  useEffect(() => {
    const token = localStorage.getItem('admin_token')
    if (!token) { navigate('/admin/login'); return }

    const u = localStorage.getItem('admin_user')
    if (u) setAdminUser(JSON.parse(u))

    adminApi.get('/stats')
      .then(r => setStats(r.data))
      .catch(err => {
        if (err.response?.status === 401 || err.response?.status === 403) {
          localStorage.removeItem('admin_token')
          localStorage.removeItem('admin_user')
          navigate('/admin/login')
        }
      })
  }, [navigate])

  const logout = () => {
    localStorage.removeItem('admin_token')
    localStorage.removeItem('admin_user')
    navigate('/admin/login')
  }

  const tabs = [
    { id: 'overview', label: 'Overview', icon: BarChart3 },
    { id: 'users', label: 'Users', icon: Users },
    { id: 'files', label: 'Files & AI Verification', icon: ShieldCheck },
    { id: 'analyses', label: 'Analyses', icon: FileSpreadsheet },
    { id: 'payments', label: 'Payments', icon: CreditCard },
  ]

  return (
    <div style={{ minHeight: '100vh', background: '#FAF8FC' }}>
      {/* Top bar */}
      <div style={{ background: '#fff', borderBottom: `1px solid ${BORDER}`, padding: '14px 24px', display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 10 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <div style={{ width: 36, height: 36, borderRadius: 10, background: `linear-gradient(135deg, ${PURPLE} 0%, ${GOLD} 100%)`, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <ShieldCheck size={18} color="#fff" />
          </div>
          <div>
            <p style={{ fontWeight: 700, color: TEXT, margin: 0, fontSize: 14 }}>RaaS Admin Panel</p>
            <p style={{ fontSize: 11, color: TEXT3, margin: 0 }}>{adminUser?.email}</p>
          </div>
        </div>
        <button onClick={logout} style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '8px 14px', borderRadius: 10, border: `1px solid ${BORDER}`, background: '#fff', color: RED, fontSize: 12, fontWeight: 600, cursor: 'pointer' }}>
          <LogOut size={13} /> Logout
        </button>
      </div>

      <div style={{ maxWidth: 1300, margin: '0 auto', padding: '24px' }}>
        {/* Tabs */}
        <div style={{ display: 'flex', gap: 6, marginBottom: 20, flexWrap: 'wrap' }}>
          {tabs.map(t => {
            const Icon = t.icon
            const active = activeTab === t.id
            return (
              <button key={t.id} onClick={() => setActiveTab(t.id)}
                style={{
                  display: 'flex', alignItems: 'center', gap: 6, padding: '9px 16px', borderRadius: 10,
                  border: active ? `1px solid ${PURPLE}` : `1px solid ${BORDER}`,
                  background: active ? 'rgba(107,45,139,0.08)' : '#fff',
                  color: active ? PURPLE : TEXT2, fontSize: 13, fontWeight: active ? 700 : 500, cursor: 'pointer',
                }}>
                <Icon size={14} /> {t.label}
              </button>
            )
          })}
        </div>

        {/* Overview */}
        {activeTab === 'overview' && stats && (
          <div>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: 14, marginBottom: 20 }}>
              <StatCard icon={Users} label="Total Users" value={stats.total_users} color={PURPLE} sub={`+${stats.new_users_this_week} this week`} />
              <StatCard icon={FileSpreadsheet} label="Total Files" value={stats.total_files} color={GOLD} sub={`+${stats.new_files_this_week} this week`} />
              <StatCard icon={BarChart3} label="Total Analyses" value={stats.total_analyses} color={PURPLE2} />
              <StatCard icon={CreditCard} label="Total Revenue" value={`₹${stats.total_revenue.toLocaleString()}`} color={GREEN} />
            </div>

            <div className="card" style={{ padding: 20, marginBottom: 20 }}>
              <h3 style={{ fontSize: 15, fontWeight: 700, color: TEXT, marginTop: 0, marginBottom: 14 }}>File Verification Status</h3>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: 12 }}>
                <div style={{ padding: 14, borderRadius: 12, background: 'rgba(22,163,74,0.06)' }}>
                  <p style={{ fontSize: 11, color: TEXT3, margin: 0 }}><Sparkles size={11} style={{ verticalAlign: 'middle' }} /> Verified by AI</p>
                  <p style={{ fontSize: 24, fontWeight: 700, color: GREEN, margin: '4px 0 0' }}>{stats.verification.verified_by_ai}</p>
                </div>
                <div style={{ padding: 14, borderRadius: 12, background: 'rgba(107,45,139,0.06)' }}>
                  <p style={{ fontSize: 11, color: TEXT3, margin: 0 }}><Cpu size={11} style={{ verticalAlign: 'middle' }} /> Verified Locally</p>
                  <p style={{ fontSize: 24, fontWeight: 700, color: PURPLE, margin: '4px 0 0' }}>{stats.verification.verified_by_local}</p>
                </div>
                <div style={{ padding: 14, borderRadius: 12, background: 'rgba(220,38,38,0.06)' }}>
                  <p style={{ fontSize: 11, color: TEXT3, margin: 0 }}><XCircle size={11} style={{ verticalAlign: 'middle' }} /> Needs Review</p>
                  <p style={{ fontSize: 24, fontWeight: 700, color: RED, margin: '4px 0 0' }}>{stats.verification.failed_verification}</p>
                </div>
                <div style={{ padding: 14, borderRadius: 12, background: SURFACE }}>
                  <p style={{ fontSize: 11, color: TEXT3, margin: 0 }}><Clock size={11} style={{ verticalAlign: 'middle' }} /> Pending</p>
                  <p style={{ fontSize: 24, fontWeight: 700, color: TEXT3, margin: '4px 0 0' }}>{stats.verification.pending_verification}</p>
                </div>
              </div>
            </div>

            <div className="card" style={{ padding: 20 }}>
              <h3 style={{ fontSize: 15, fontWeight: 700, color: TEXT, marginTop: 0, marginBottom: 14 }}>Plan Distribution</h3>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(120px, 1fr))', gap: 12 }}>
                {Object.entries(stats.plan_distribution).map(([plan, count]) => (
                  <div key={plan} style={{ padding: 14, borderRadius: 12, background: SURFACE, textAlign: 'center' }}>
                    <p style={{ fontSize: 11, color: TEXT3, textTransform: 'capitalize', margin: 0 }}>{plan}</p>
                    <p style={{ fontSize: 22, fontWeight: 700, color: TEXT, margin: '4px 0 0' }}>{count}</p>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

        {activeTab === 'users' && <UsersTab />}
        {activeTab === 'files' && <FilesTab />}
        {activeTab === 'analyses' && <AnalysesTab />}
        {activeTab === 'payments' && <PaymentsTab />}
      </div>
    </div>
  )
}
