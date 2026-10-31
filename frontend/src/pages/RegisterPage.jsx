import React, { useState, useMemo, useRef, useEffect } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import useAuthStore from '../store/authStore'
import { Eye, EyeOff, TrendingUp, ArrowRight, Check, X, ShieldCheck } from 'lucide-react'
import toast from 'react-hot-toast'

// ── Validators ──────────────────────────────────────────────────────────
const EMAIL_RE = /^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$/
const USERNAME_RE = /^[a-zA-Z0-9_]+$/
const NAME_RE = /^[a-zA-Z\s.'-]*$/

function validateEmail(email) {
  if (!email) return 'Email is required'
  if (email.length > 254) return 'Email is too long'
  if (!EMAIL_RE.test(email)) return 'Enter a valid email (e.g. example@gmail.com)'
  const [local, domain] = email.split('@')
  if (!domain || !domain.includes('.')) return 'Email must contain @ and a domain (e.g. .com)'
  if (local.length > 64) return 'Email username part is too long'
  return ''
}

function validateUsername(username) {
  if (!username) return 'Username is required'
  if (username.length < 3) return 'Min 3 characters'
  if (username.length > 30) return 'Max 30 characters'
  if (!USERNAME_RE.test(username)) return 'Letters, numbers, underscores only'
  return ''
}

function validateFullName(name) {
  if (!name) return ''   // optional field
  if (name.length > 50) return 'Full name must be 50 characters or fewer'
  if (!NAME_RE.test(name)) return 'Name can only contain letters, spaces, and . \' -'
  return ''
}

function validatePhone(phone) {
  if (!phone) return ''   // optional field
  const digits = phone.replace(/\D/g, '')
  if (digits.length < 10) return 'Phone number is too short (min 10 digits)'
  if (digits.length > 15) return 'Phone number is too long (max 15 digits)'
  if (!/^[\d\s+()-]+$/.test(phone)) return 'Phone can only contain numbers, spaces, +, -, ()'
  return ''
}

function passwordChecks(password) {
  return [
    { key: 'length', label: '8+ characters', ok: password.length >= 8 },
    { key: 'upper', label: 'Uppercase letter', ok: /[A-Z]/.test(password) },
    { key: 'lower', label: 'Lowercase letter', ok: /[a-z]/.test(password) },
    { key: 'number', label: 'Number', ok: /\d/.test(password) },
    { key: 'special', label: 'Special character', ok: /[!@#$%^&*(),.?":{}|<>]/.test(password) },
  ]
}

function validatePassword(password) {
  if (!password) return 'Password is required'
  const checks = passwordChecks(password)
  const failed = checks.find(c => !c.ok)
  if (failed) {
    const messages = {
      length: 'Password must be at least 8 characters',
      upper: 'Password must contain an uppercase letter',
      lower: 'Password must contain a lowercase letter',
      number: 'Password must contain a number',
      special: 'Password must contain a special character',
    }
    return messages[failed.key]
  }
  if (password.length > 72) return 'Password is too long (max 72 characters)'
  return ''
}

// ── Password strength meter ────────────────────────────────────────────
function PasswordStrength({ password }) {
  const checks = passwordChecks(password)
  const score = checks.filter(c => c.ok).length
  const colors = ['', '#DC2626', '#EA580C', '#CA8A04', '#16A34A', '#16A34A']
  const labels = ['', 'Very Weak', 'Weak', 'Fair', 'Strong', 'Very Strong']

  if (!password) return null
  return (
    <div className="mt-2 space-y-2">
      <div className="flex gap-1">
        {[1, 2, 3, 4, 5].map(i => (
          <div key={i} className="h-1 flex-1 rounded-full transition-all duration-300"
            style={{ background: i <= score ? colors[score] : 'var(--surface3)' }} />
        ))}
      </div>
      <p className="text-xs font-medium" style={{ color: colors[score] }}>{labels[score]}</p>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-1">
        {checks.map(c => (
          <div key={c.key} className="flex items-center gap-1.5 text-[11px]">
            {c.ok
              ? <Check size={10} className="text-green-400 flex-shrink-0" />
              : <X size={10} className="text-[var(--text3)] flex-shrink-0" />}
            <span className={c.ok ? 'text-green-400' : 'text-[var(--text3)]'}>{c.label}</span>
          </div>
        ))}
      </div>
    </div>
  )
}

// ── Lightweight "I am human" challenge (no external API needed) ─────────
function HumanCheck({ checked, onChange }) {
  const [a, setA] = useState(0)
  const [b, setB] = useState(0)
  const [answer, setAnswer] = useState('')
  const [solved, setSolved] = useState(false)

  useEffect(() => {
    setA(Math.floor(Math.random() * 8) + 1)
    setB(Math.floor(Math.random() * 8) + 1)
  }, [])

  useEffect(() => {
    const correct = answer !== '' && Number(answer) === a + b
    setSolved(correct)
    onChange(correct)
  }, [answer, a, b])

  return (
    <div
      className="rounded-xl p-3 flex flex-col sm:flex-row sm:items-center gap-3"
      style={{ background: 'var(--surface2)', border: `1px solid ${solved ? 'rgba(22,163,74,0.4)' : 'var(--surface3)'}` }}
    >
      <div className="flex items-center gap-2 flex-shrink-0">
        <ShieldCheck size={16} style={{ color: solved ? '#16A34A' : 'var(--text3)' }} />
        <span className="text-xs font-medium text-[var(--text2)] whitespace-nowrap">
          I'm not a robot — what is {a} + {b}?
        </span>
      </div>
      <input
        type="text"
        inputMode="numeric"
        value={answer}
        onChange={e => setAnswer(e.target.value.replace(/[^\d]/g, ''))}
        placeholder="Answer"
        className="input"
        style={{ maxWidth: '90px', padding: '7px 10px', fontSize: '13px' }}
      />
      {solved && <Check size={16} className="text-green-500 flex-shrink-0" />}
    </div>
  )
}

export default function RegisterPage() {
  const [form, setForm] = useState({ email: '', username: '', full_name: '', phone: '', password: '', confirm: '' })
  const [showPass, setShowPass] = useState(false)
  const [showConfirm, setShowConfirm] = useState(false)
  const [loading, setLoading] = useState(false)
  const [errors, setErrors] = useState({})
  const [touched, setTouched] = useState({})
  const [isHuman, setIsHuman] = useState(false)
  const { register } = useAuthStore()
  const navigate = useNavigate()

  const liveErrors = useMemo(() => ({
    email: validateEmail(form.email),
    username: validateUsername(form.username),
    full_name: validateFullName(form.full_name),
    phone: validatePhone(form.phone),
    password: validatePassword(form.password),
    confirm: form.confirm && form.password !== form.confirm ? 'Passwords do not match' : '',
  }), [form])

  const validateAll = () => {
    const e = {}
    Object.entries(liveErrors).forEach(([k, v]) => { if (v) e[k] = v })
    if (!form.confirm) e.confirm = 'Please confirm your password'
    if (!isHuman) e.is_human = 'Please complete the human verification'
    return e
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    setTouched({ email: true, username: true, full_name: true, phone: true, password: true, confirm: true })
    const errs = validateAll()
    if (Object.keys(errs).length) {
      setErrors(errs)
      toast.error('Please fix the highlighted fields')
      return
    }
    setLoading(true)
    setErrors({})
    try {
      await register(form.email, form.username, form.password, form.full_name, form.phone, isHuman)
      toast.success('Account created! Welcome to Raas 🎉')
      navigate('/dashboard')
    } catch (err) {
      const details = err.response?.data?.details || {}
      const msg = err.response?.data?.error || 'Registration failed'
      if (Object.keys(details).length) setErrors(prev => ({ ...prev, ...details }))
      else toast.error(msg)
    } finally {
      setLoading(false)
    }
  }

  const f = (field, opts = {}) => ({
    value: form[field],
    onChange: e => {
      let val = e.target.value
      if (field === 'full_name' && val.length > 50) val = val.slice(0, 50)
      if (field === 'phone') val = val.slice(0, 20)
      setForm(prev => ({ ...prev, [field]: val }))
    },
    onBlur: () => setTouched(prev => ({ ...prev, [field]: true })),
    ...opts,
  })

  const blockPaste = (e) => {
    e.preventDefault()
    toast.error('Pasting is disabled for security — please type your password manually', { id: 'no-paste' })
  }
  const blockCopyCutDrag = (e) => e.preventDefault()

  const errFor = (field) => (touched[field] && (errors[field] || liveErrors[field])) || ''

  return (
    <div className="min-h-screen bg-[var(--bg)] flex items-center justify-center p-4 sm:p-6">
      <div className="w-full max-w-md">
        <Link to="/" className="flex items-center gap-3 mb-6 sm:mb-8">
          <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-[var(--accent)] to-[var(--cyan)] flex items-center justify-center flex-shrink-0">
            <TrendingUp size={18} className="text-white" />
          </div>
          <span className="text-base font-bold">Raas</span>
        </Link>

        <h1 className="text-xl sm:text-2xl font-bold text-[var(--text)] mb-1">Create account</h1>
        <p className="text-sm text-[var(--text2)] mb-6 sm:mb-8">
          Already have one? <Link to="/login" className="text-[var(--accent)] hover:underline">Sign in</Link>
        </p>

        <div className="p-3 mb-6 rounded-xl bg-[var(--accent)]/10 border border-[var(--accent)]/20 flex items-start gap-2">
          <span className="text-[var(--accent)] text-lg flex-shrink-0">🎁</span>
          <div>
            <p className="text-xs font-semibold text-[var(--text)]">Free plan includes 3 download credits</p>
            <p className="text-[11px] text-[var(--text2)]">No credit card required to get started</p>
          </div>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4" autoComplete="off">
          <div>
            <label className="label">Full Name <span className="text-[var(--text3)]">(optional, max 50 chars)</span></label>
            <input
              type="text"
              className={`input ${errFor('full_name') ? 'border-red-500/60' : ''}`}
              placeholder="e.g. Test Example"
              maxLength={50}
              autoComplete="name"
              {...f('full_name')}
            />
            <div className="flex items-center justify-between mt-1">
              {errFor('full_name') && <p className="text-xs text-red-400">{errFor('full_name')}</p>}
              <p className="text-[10px] text-[var(--text3)] ml-auto">{form.full_name.length}/50</p>
            </div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <label className="label">Email *</label>
              <input
                type="email"
                className={`input ${errFor('email') ? 'border-red-500/60' : ''}`}
                placeholder="example@gmail.com"
                maxLength={254}
                autoComplete="email"
                {...f('email')}
              />
              {errFor('email') && <p className="text-xs text-red-400 mt-1">{errFor('email')}</p>}
            </div>
            <div>
              <label className="label">Username *</label>
              <input
                type="text"
                className={`input ${errFor('username') ? 'border-red-500/60' : ''}`}
                placeholder="e.g. test_example"
                maxLength={30}
                autoComplete="username"
                {...f('username')}
              />
              {errFor('username') && <p className="text-xs text-red-400 mt-1">{errFor('username')}</p>}
            </div>
          </div>

          <div>
            <label className="label">Mobile Number <span className="text-[var(--text3)]">(optional)</span></label>
            <input
              type="tel"
              className={`input ${errFor('phone') ? 'border-red-500/60' : ''}`}
              placeholder="e.g. +91 98765 43210"
              maxLength={20}
              autoComplete="tel"
              {...f('phone')}
            />
            {errFor('phone') && <p className="text-xs text-red-400 mt-1">{errFor('phone')}</p>}
          </div>

          <div>
            <label className="label">Password *</label>
            <div className="relative">
              <input
                type={showPass ? 'text' : 'password'}
                className={`input pr-11 ${errFor('password') ? 'border-red-500/60' : ''}`}
                placeholder="Create a strong password"
                autoComplete="new-password"
                maxLength={72}
                onPaste={blockPaste}
                onCopy={blockCopyCutDrag}
                onCut={blockCopyCutDrag}
                onDrop={blockCopyCutDrag}
                onContextMenu={blockCopyCutDrag}
                {...f('password')}
              />
              <button type="button" onClick={() => setShowPass(!showPass)}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-[var(--text3)] hover:text-[var(--text2)]">
                {showPass ? <EyeOff size={16} /> : <Eye size={16} />}
              </button>
            </div>
            {errFor('password') && <p className="text-xs text-red-400 mt-1">{errFor('password')}</p>}
            <PasswordStrength password={form.password} />
          </div>

          <div>
            <label className="label">Confirm Password *</label>
            <div className="relative">
              <input
                type={showConfirm ? 'text' : 'password'}
                className={`input pr-11 ${errFor('confirm') ? 'border-red-500/60' : ''}`}
                placeholder="Repeat your password"
                autoComplete="new-password"
                maxLength={72}
                onPaste={blockPaste}
                onCopy={blockCopyCutDrag}
                onCut={blockCopyCutDrag}
                onDrop={blockCopyCutDrag}
                onContextMenu={blockCopyCutDrag}
                {...f('confirm')}
              />
              <button type="button" onClick={() => setShowConfirm(!showConfirm)}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-[var(--text3)] hover:text-[var(--text2)]">
                {showConfirm ? <EyeOff size={16} /> : <Eye size={16} />}
              </button>
            </div>
            {errFor('confirm') && <p className="text-xs text-red-400 mt-1">{errFor('confirm')}</p>}
          </div>

          <HumanCheck checked={isHuman} onChange={setIsHuman} />
          {touched.password && errors.is_human && !isHuman && (
            <p className="text-xs text-red-400 -mt-2">{errors.is_human}</p>
          )}

          <button
            type="submit"
            disabled={loading}
            className="btn btn-primary btn-lg w-full mt-2 flex items-center justify-center gap-2"
          >
            {loading
              ? <span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
              : <>Create Account <ArrowRight size={16} /></>}
          </button>
        </form>

        <p className="text-xs text-[var(--text3)] text-center mt-4 px-2">
          By registering, you agree to our Terms of Service and Privacy Policy
        </p>
      </div>
    </div>
  )
}
