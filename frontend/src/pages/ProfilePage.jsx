import React, { useEffect, useState } from 'react'
import api from '../utils/api'
import useAuthStore from '../store/authStore'
import { User, CreditCard, Shield, Key, RefreshCw, Check, Eye, EyeOff } from 'lucide-react'
import { formatDistanceToNow } from 'date-fns'
import toast from 'react-hot-toast'

export default function ProfilePage() {
  const { user, refreshUser } = useAuthStore()
  const [fullName, setFullName] = useState(user?.full_name || '')
  const [savingProfile, setSavingProfile] = useState(false)
  const [payments, setPayments] = useState([])
  const [loadingPayments, setLoadingPayments] = useState(true)
  const [passwords, setPasswords] = useState({ current: '', newPass: '', confirm: '' })
  const [showPass, setShowPass] = useState(false)
  const [savingPass, setSavingPass] = useState(false)

  useEffect(() => {
    api.get('/payment/history').then(r => {
      setPayments(r.data.payments)
      setLoadingPayments(false)
    }).catch(() => setLoadingPayments(false))
  }, [])

  const saveProfile = async () => {
    setSavingProfile(true)
    try {
      await api.put('/user/profile', { full_name: fullName })
      await refreshUser()
      toast.success('Profile updated')
    } catch {
      toast.error('Failed to update profile')
    } finally {
      setSavingProfile(false)
    }
  }

  const savePassword = async () => {
    if (!passwords.current) { toast.error('Current password required'); return }
    if (passwords.newPass.length < 8) { toast.error('New password must be 8+ characters'); return }
    if (passwords.newPass !== passwords.confirm) { toast.error('Passwords do not match'); return }
    setSavingPass(true)
    try {
      await api.put('/auth/change-password', { current_password: passwords.current, new_password: passwords.newPass })
      toast.success('Password changed')
      setPasswords({ current: '', newPass: '', confirm: '' })
    } catch (err) {
      toast.error(err.response?.data?.error || 'Failed to change password')
    } finally {
      setSavingPass(false)
    }
  }

  const planColors = { free: 'text-[var(--text2)]', basic: 'text-blue-400', pro: 'text-[var(--accent)]', enterprise: 'text-amber-400' }

  return (
    <div className="max-w-3xl mx-auto space-y-6 stagger">
      <div>
        <h1 className="text-xl font-bold text-[var(--text)]">Profile & Settings</h1>
        <p className="text-sm text-[var(--text2)] mt-0.5">Manage your account details and subscription</p>
      </div>

      {/* Account overview */}
      <div className="card p-5">
        <div className="flex items-center gap-4 mb-5">
          <div className="w-14 h-14 rounded-2xl bg-gradient-to-br from-[var(--accent)] to-purple-600 flex items-center justify-center text-white text-xl font-bold flex-shrink-0">
            {(user?.full_name || user?.username || 'U')[0].toUpperCase()}
          </div>
          <div>
            <h2 className="font-bold text-[var(--text)]">{user?.full_name || user?.username}</h2>
            <p className="text-sm text-[var(--text2)]">{user?.email}</p>
            <div className="flex items-center gap-3 mt-1">
              <span className={`text-xs font-bold ${planColors[user?.plan]}`}>{user?.plan?.toUpperCase()} PLAN</span>
              <span className="text-xs text-[var(--text3)]">·</span>
              <span className="text-xs text-[var(--text2)]">{user?.download_credits} credits</span>
            </div>
          </div>
        </div>

        {/* Stats row */}
        <div className="grid grid-cols-3 gap-3">
          {[
            { label: 'Plan', value: user?.plan?.toUpperCase() },
            { label: 'Credits', value: user?.download_credits },
            { label: 'Member Since', value: user?.created_at ? new Date(user.created_at).getFullYear() : '—' },
          ].map(s => (
            <div key={s.label} className="text-center p-3 rounded-xl bg-[var(--surface2)]">
              <div className="text-lg font-bold text-[var(--text)]">{s.value}</div>
              <div className="text-[11px] text-[var(--text3)]">{s.label}</div>
            </div>
          ))}
        </div>
      </div>

      {/* Edit profile */}
      <div className="card p-5">
        <h3 className="section-title flex items-center gap-2 mb-4">
          <User size={16} className="text-[var(--accent)]" /> Edit Profile
        </h3>
        <div className="space-y-4">
          <div>
            <label className="label">Full Name</label>
            <input type="text" className="input" placeholder="Your full name" value={fullName}
              onChange={e => setFullName(e.target.value)} />
          </div>
          <div>
            <label className="label">Email</label>
            <input type="email" className="input opacity-60" value={user?.email || ''} disabled />
            <p className="text-[11px] text-[var(--text3)] mt-1">Email cannot be changed</p>
          </div>
          <div>
            <label className="label">Username</label>
            <input type="text" className="input opacity-60" value={user?.username || ''} disabled />
          </div>
          <button onClick={saveProfile} disabled={savingProfile} className="btn btn-primary btn-md">
            {savingProfile ? <RefreshCw size={14} className="animate-spin" /> : <Check size={14} />}
            Save Profile
          </button>
        </div>
      </div>

      {/* Change password */}
      <div className="card p-5">
        <h3 className="section-title flex items-center gap-2 mb-4">
          <Key size={16} className="text-[var(--accent)]" /> Change Password
        </h3>
        <div className="space-y-4">
          {[
            { key: 'current', label: 'Current Password', placeholder: '••••••••' },
            { key: 'newPass', label: 'New Password', placeholder: 'Min 8 characters' },
            { key: 'confirm', label: 'Confirm New Password', placeholder: 'Repeat new password' },
          ].map(({ key, label, placeholder }) => (
            <div key={key}>
              <label className="label">{label}</label>
              <div className="relative">
                <input type={showPass ? 'text' : 'password'} className="input pr-11" placeholder={placeholder}
                  value={passwords[key]} onChange={e => setPasswords({ ...passwords, [key]: e.target.value })} />
                {key === 'current' && (
                  <button type="button" onClick={() => setShowPass(!showPass)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-[var(--text3)] hover:text-[var(--text2)]">
                    {showPass ? <EyeOff size={16} /> : <Eye size={16} />}
                  </button>
                )}
              </div>
            </div>
          ))}
          <button onClick={savePassword} disabled={savingPass} className="btn btn-secondary btn-md">
            {savingPass ? <RefreshCw size={14} className="animate-spin" /> : <Shield size={14} />}
            Update Password
          </button>
        </div>
      </div>

      {/* Payment history */}
      <div className="card p-5">
        <h3 className="section-title flex items-center gap-2 mb-4">
          <CreditCard size={16} className="text-[var(--accent)]" /> Payment History
        </h3>
        {loadingPayments ? (
          <div className="space-y-2">{[...Array(3)].map((_, i) => <div key={i} className="skeleton h-12 rounded-xl" />)}</div>
        ) : !payments.length ? (
          <p className="text-sm text-[var(--text2)]">No payments yet.</p>
        ) : (
          <div className="table-container">
            <table className="table">
              <thead><tr><th>Plan</th><th>Amount</th><th>Credits</th><th>Status</th><th>Date</th></tr></thead>
              <tbody>
                {payments.map(p => (
                  <tr key={p.id}>
                    <td className="font-medium text-[var(--text)] capitalize">{p.plan?.replace('_', ' ')}</td>
                    <td className="font-mono">${p.amount?.toFixed(2)}</td>
                    <td>+{p.credits_added}</td>
                    <td><span className={`badge ${p.status === 'paid' ? 'badge-green' : 'badge-amber'}`}>{p.status}</span></td>
                    <td className="text-xs">{formatDistanceToNow(new Date(p.created_at), { addSuffix: true })}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}
