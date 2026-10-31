import React, { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import useAuthStore from '../store/authStore'
import { Eye, EyeOff, TrendingUp, ArrowRight, CheckCircle } from 'lucide-react'
import toast from 'react-hot-toast'

export default function LoginPage() {
  const [form, setForm] = useState({ email: '', password: '' })
  const [showPass, setShowPass] = useState(false)
  const [loading, setLoading] = useState(false)
  const [errors, setErrors] = useState({})
  const { login } = useAuthStore()
  const navigate = useNavigate()

  const validate = () => {
    const e = {}
    if (!form.email) e.email = 'Email is required'
    else if (!/\S+@\S+\.\S+/.test(form.email)) e.email = 'Enter a valid email'
    if (!form.password) e.password = 'Password is required'
    return e
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    const errs = validate()
    if (Object.keys(errs).length) { setErrors(errs); return }
    setLoading(true)
    setErrors({})
    try {
      await login(form.email, form.password)
      toast.success('Welcome back!')
      navigate('/dashboard')
    } catch (err) {
      const msg = err.response?.data?.error || 'Login failed'
      toast.error(msg)
      if (msg.toLowerCase().includes('password')) setErrors({ password: msg })
      else if (msg.toLowerCase().includes('email')) setErrors({ email: msg })
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-[var(--bg)] flex">
      {/* Left Panel */}
      <div className="hidden lg:flex flex-col w-[420px] xl:w-[480px] bg-gradient-to-br from-[var(--accent)]/20 via-[var(--surface)] to-[var(--bg)] border-r border-[var(--border)] p-10 relative overflow-hidden">
        <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top_left,var(--accent-glow),transparent_60%)]" />
        <div className="relative z-10">
          <Link to="/" className="flex items-center gap-3 mb-16">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-[var(--accent)] to-[var(--cyan)] flex items-center justify-center">
              <TrendingUp size={20} className="text-white" />
            </div>
            <span className="text-lg font-bold text-[var(--text)]">Raas</span>
          </Link>
          <h2 className="text-3xl font-display font-semibold text-[var(--text)] mb-4">
            Turn spreadsheets into insights
          </h2>
          <p className="text-[var(--text2)] mb-10 leading-relaxed">
            Automated analysis of your Excel and CSV files. Understand your data instantly.
          </p>
          {['Upload any Excel or CSV file', 'AI analysis in seconds', 'Professional reports & exports', 'Data quality scoring'].map(f => (
            <div key={f} className="flex items-center gap-3 mb-3">
              <CheckCircle size={16} className="text-[var(--accent)] flex-shrink-0" />
              <span className="text-sm text-[var(--text2)]">{f}</span>
            </div>
          ))}
        </div>
      </div>

      {/* Right Panel */}
      <div className="flex-1 flex items-center justify-center p-6">
        <div className="w-full max-w-md">
          <div className="lg:hidden flex items-center gap-3 mb-8">
            <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-[var(--accent)] to-[var(--cyan)] flex items-center justify-center">
              <TrendingUp size={18} className="text-white" />
            </div>
            <span className="text-base font-bold">Raas</span>
          </div>

          <h1 className="text-2xl font-bold text-[var(--text)] mb-1">Sign in</h1>
          <p className="text-sm text-[var(--text2)] mb-8">
            Don't have an account? <Link to="/register" className="text-[var(--accent)] hover:underline">Create one free</Link>
          </p>

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="label">Email</label>
              <input
                type="email"
                className={`input ${errors.email ? 'border-red-500/60 focus:border-red-500' : ''}`}
                placeholder="you@example.com"
                value={form.email}
                onChange={e => setForm({ ...form, email: e.target.value })}
                autoComplete="email"
              />
              {errors.email && <p className="text-xs text-red-400 mt-1">{errors.email}</p>}
            </div>

            <div>
              <label className="label">Password</label>
              <div className="relative">
                <input
                  type={showPass ? 'text' : 'password'}
                  className={`input pr-11 ${errors.password ? 'border-red-500/60 focus:border-red-500' : ''}`}
                  placeholder="••••••••"
                  value={form.password}
                  onChange={e => setForm({ ...form, password: e.target.value })}
                  autoComplete="current-password"
                />
                <button type="button" onClick={() => setShowPass(!showPass)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-[var(--text3)] hover:text-[var(--text2)]">
                  {showPass ? <EyeOff size={16} /> : <Eye size={16} />}
                </button>
              </div>
              {errors.password && <p className="text-xs text-red-400 mt-1">{errors.password}</p>}
            </div>

            <button type="submit" disabled={loading}
              className="btn btn-primary btn-lg w-full mt-2">
              {loading ? <span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" /> : <>Sign In <ArrowRight size={16} /></>}
            </button>
          </form>

          <div className="mt-6 p-4 rounded-xl bg-[var(--surface2)] border border-[var(--border)]">
            <p className="text-xs text-[var(--text3)] font-semibold mb-1 uppercase tracking-wider">Demo Account</p>
            <p className="text-xs text-[var(--text2)]">Register a new account — free plan includes 3 download credits instantly.</p>
          </div>
        </div>
      </div>
    </div>
  )
}
