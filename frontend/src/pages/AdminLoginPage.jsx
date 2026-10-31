import React, { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import api from '../utils/api'
import { Eye, EyeOff, ShieldCheck } from 'lucide-react'
import toast from 'react-hot-toast'

const PURPLE = '#6B2D8B'
const GOLD   = '#C8860B'
const TEXT   = '#241B33'
const TEXT2  = '#6B6280'

export default function AdminLoginPage() {
  const [form, setForm]       = useState({ email: '', password: '' })
  const [showPass, setShowPass] = useState(false)
  const [loading, setLoading] = useState(false)
  const navigate = useNavigate()

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!form.email || !form.password) {
      toast.error('Email and password are required')
      return
    }
    setLoading(true)
    try {
      const res = await api.post('/admin/login', form)
      localStorage.setItem('admin_token', res.data.access_token)
      localStorage.setItem('admin_user', JSON.stringify(res.data.user))
      toast.success('Welcome, Admin')
      navigate('/admin/dashboard')
    } catch (err) {
      toast.error(err.response?.data?.error || 'Login failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={{
      minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center',
      background: `linear-gradient(135deg, #1a0d26 0%, #2d1640 50%, #1a0d26 100%)`,
      padding: '20px',
    }}>
      <div style={{
        width: '100%', maxWidth: '420px', background: '#FFFFFF', borderRadius: '20px',
        padding: '40px 36px', boxShadow: '0 20px 60px rgba(0,0,0,0.4)',
      }}>
        <div style={{ textAlign: 'center', marginBottom: '28px' }}>
          <div style={{
            width: '56px', height: '56px', borderRadius: '16px', margin: '0 auto 14px',
            background: `linear-gradient(135deg, ${PURPLE} 0%, ${GOLD} 100%)`,
            display: 'flex', alignItems: 'center', justifyContent: 'center',
          }}>
            <ShieldCheck size={28} color="#fff" />
          </div>
          <h1 style={{ fontSize: '22px', fontWeight: 700, color: TEXT, margin: 0 }}>RaaS Admin Panel</h1>
          <p style={{ fontSize: '13px', color: TEXT2, marginTop: '4px' }}>VP Research Company — Internal Access Only</p>
        </div>

        <form onSubmit={handleSubmit}>
          <div style={{ marginBottom: '16px' }}>
            <label style={{ fontSize: '12px', fontWeight: 600, color: TEXT2, display: 'block', marginBottom: '6px' }}>Admin Email</label>
            <input
              type="email"
              value={form.email}
              onChange={e => setForm({ ...form, email: e.target.value })}
              placeholder="admin@raas.com"
              style={{
                width: '100%', boxSizing: 'border-box', padding: '11px 14px', fontSize: '14px',
                border: '1px solid rgba(107,45,139,0.18)', borderRadius: '10px', outline: 'none',
              }}
            />
          </div>

          <div style={{ marginBottom: '22px' }}>
            <label style={{ fontSize: '12px', fontWeight: 600, color: TEXT2, display: 'block', marginBottom: '6px' }}>Password</label>
            <div style={{ position: 'relative' }}>
              <input
                type={showPass ? 'text' : 'password'}
                value={form.password}
                onChange={e => setForm({ ...form, password: e.target.value })}
                placeholder="••••••••"
                style={{
                  width: '100%', boxSizing: 'border-box', padding: '11px 40px 11px 14px', fontSize: '14px',
                  border: '1px solid rgba(107,45,139,0.18)', borderRadius: '10px', outline: 'none',
                }}
              />
              <button type="button" onClick={() => setShowPass(!showPass)}
                style={{ position: 'absolute', right: '12px', top: '50%', transform: 'translateY(-50%)', background: 'none', border: 'none', cursor: 'pointer', color: TEXT2 }}>
                {showPass ? <EyeOff size={16} /> : <Eye size={16} />}
              </button>
            </div>
          </div>

          <button type="submit" disabled={loading}
            style={{
              width: '100%', padding: '12px', borderRadius: '10px', border: 'none', cursor: loading ? 'wait' : 'pointer',
              background: PURPLE, color: '#fff', fontSize: '14px', fontWeight: 700,
            }}>
            {loading ? 'Signing in…' : 'Sign In to Admin Panel'}
          </button>
        </form>

        <p style={{ fontSize: '11px', color: TEXT2, textAlign: 'center', marginTop: '20px' }}>
          This panel is restricted to platform administrators only.
        </p>
      </div>
    </div>
  )
}
