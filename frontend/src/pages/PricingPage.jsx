import React, { useState } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import api from '../utils/api'
import useAuthStore from '../store/authStore'
import { Check, Zap, Star, Crown, Building2, TrendingUp, CalendarDays, ArrowRight, RefreshCw, Mail } from 'lucide-react'
import toast from 'react-hot-toast'

const PLANS = [
  {
    id: 'free',
    name: 'Free',
    price: 0,
    period: 'forever',
    icon: TrendingUp,
    color: 'from-gray-500/20 to-gray-500/5',
    border: 'border-[var(--border)]',
    credits: 3,
    files: 5,
    features: ['5 file uploads', '3 download credits', 'Summary statistics', 'Data quality check', 'Distribution analysis', 'Category analysis'],
    locked: ['Advanced Analytics Engine', 'AI Insights', 'PDF / Excel reports'],
  },
  {
    id: 'daily',
    name: 'Daily',
    price: 49,
    originalPrice: 79,
    period: '/day',
    icon: Zap,
    color: 'from-blue-500/20 to-blue-500/5',
    border: 'border-blue-500/30',
    credits: 15,
    files: 10,
    features: ['10 file uploads', '15 download credits', 'All quick analysis types', 'Advanced Analytics Engine (Stage 1)', 'PDF & Excel reports'],
  },
  {
    id: 'weekly',
    name: 'Weekly',
    price: 199,
    originalPrice: 299,
    period: '/week',
    icon: CalendarDays,
    color: 'from-[var(--cyan)]/20 to-[var(--cyan)]/5',
    border: 'border-[var(--cyan)]/30',
    credits: 60,
    files: 40,
    features: ['40 file uploads', '60 download credits', 'All analysis types', 'Advanced Analytics Engine', 'AI Insights', 'PDF & Excel reports'],
  },
  {
    id: 'monthly',
    name: 'Monthly',
    price: 399,
    originalPrice: 599,
    period: '/month',
    icon: Star,
    color: 'from-[var(--accent)]/20 to-purple-500/10',
    border: 'border-[var(--accent)]/40',
    credits: 150,
    files: 150,
    popular: true,
    features: ['150 file uploads', '150 download credits', 'All analysis types', 'Advanced Analytics Engine', 'AI Insights', 'Priority processing', 'All report formats'],
  },
  {
    id: 'yearly',
    name: 'Yearly',
    price: 1599,
    originalPrice: 1799,
    period: '/year',
    icon: Crown,
    color: 'from-amber-500/20 to-amber-500/5',
    border: 'border-amber-500/30',
    credits: 2000,
    files: '∞',
    bestValue: true,
    features: ['Unlimited file uploads', '2000 download credits', 'All analysis types', 'Advanced Analytics Engine', 'AI Insights', 'Priority processing & support', 'All report formats'],
  },
]

const COMMERCIAL_PLAN = {
  name: 'Commercial',
  icon: Building2,
  desc: 'For agencies, enterprises and teams that need custom limits, billing, and support.',
  features: ['Unlimited uploads & downloads', 'API access', 'Dedicated account manager', 'Custom integrations', 'Team seats & SLA', 'Custom invoicing (GST)'],
}

const CREDIT_PACK = {
  id: 'credits_10',
  name: '10 Credits',
  price: 299,
  desc: 'One-time purchase',
  features: ['10 download credits', 'Never expire (1 year)', 'Works with any plan'],
}

function PriceTag({ plan }) {
  if (plan.id === 'free') {
    return (
      <div className="mb-4">
        <span className="text-2xl font-bold text-[var(--text)]">Free</span>
        <span className="text-sm text-[var(--text3)]"> {plan.period}</span>
      </div>
    )
  }

  const savings = plan.originalPrice ? Math.round((1 - plan.price / plan.originalPrice) * 100) : 0

  return (
    <div className="mb-4">
      <div className="flex items-center gap-2 flex-wrap">
        <span className="text-2xl font-bold text-[var(--text)]">₹{plan.price}</span>
        <span className="text-sm text-[var(--text3)]">{plan.period}</span>
        {savings > 0 && <span className="badge badge-green text-[10px]">Save {savings}%</span>}
      </div>
      {plan.originalPrice && (
        <div className="text-xs text-[var(--text3)] mt-0.5">
          <span className="line-through">₹{plan.originalPrice}{plan.period}</span> regular price
        </div>
      )}
    </div>
  )
}

export default function PricingPage({ standalone = false }) {
  const { user, refreshUser } = useAuthStore()
  const navigate = useNavigate()
  const [loading, setLoading] = useState(null)

  const handlePurchase = async (planId) => {
    if (!user) { navigate('/register'); return }
    setLoading(planId)
    try {
      const res = await api.post('/payment/create-checkout', { plan_id: planId })
      if (res.data.checkout_url) {
        window.location.href = res.data.checkout_url
      } else {
        // Demo mode — use demo activate
        const demoRes = await api.post('/payment/demo-activate', { plan_id: planId })
        await refreshUser()
        toast.success(demoRes.data.message || 'Plan activated (Demo Mode)!')
        if (!standalone) navigate('/dashboard')
      }
    } catch (err) {
      toast.error(err.response?.data?.error || 'Purchase failed')
    } finally {
      setLoading(null)
    }
  }

  const Wrapper = standalone
    ? ({ children }) => (
        <div className="min-h-screen bg-[var(--bg)] py-16 px-4">
          <div className="max-w-6xl mx-auto">
            {user && (
              <Link to="/dashboard" className="inline-flex items-center gap-2 text-sm text-[var(--text2)] hover:text-[var(--text)] mb-8">
                ← Back to Dashboard
              </Link>
            )}
            {children}
          </div>
        </div>
      )
    : ({ children }) => <div className="max-w-6xl mx-auto">{children}</div>

  return (
    <Wrapper>
      <div className="text-center mb-12">
        <h1 className="text-3xl font-bold text-[var(--text)] mb-3">
          Simple, <span className="gradient-text">transparent</span> pricing
        </h1>
        <p className="text-[var(--text2)] max-w-lg mx-auto">
          Pick a plan that matches how often you analyze data — daily, weekly, monthly or yearly.
          All paid plans include the full Advanced Analytics Engine and AI Insights. Prices in INR (₹), inclusive of all launch offers.
        </p>
      </div>

      {/* Plan Cards */}
      <div className="grid sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5 gap-4 mb-6">
        {PLANS.map(plan => {
          const Icon = plan.icon
          const isCurrent = user?.plan === plan.id
          const isLoading = loading === plan.id
          return (
            <div key={plan.id}
              className={`card p-5 flex flex-col bg-gradient-to-br ${plan.color} ${plan.border} relative
                ${plan.popular ? 'ring-2 ring-[var(--accent)]/50' : ''}`}>
              {plan.popular && (
                <div className="absolute -top-3 left-1/2 -translate-x-1/2 badge badge-purple shadow-lg whitespace-nowrap">
                  Most Popular
                </div>
              )}
              {plan.bestValue && (
                <div className="absolute -top-3 left-1/2 -translate-x-1/2 badge badge-amber shadow-lg whitespace-nowrap">
                  Best Value
                </div>
              )}
              <div className={`w-10 h-10 rounded-xl bg-[var(--surface)] flex items-center justify-center mb-4`}>
                <Icon size={20} className={plan.popular || plan.bestValue ? 'text-[var(--accent)]' : 'text-[var(--text2)]'} />
              </div>
              <div className="mb-1">
                <h3 className="font-bold text-[var(--text)]">{plan.name}</h3>
              </div>

              <PriceTag plan={plan} />

              <div className="text-xs text-[var(--text2)] mb-4 space-y-0.5">
                <div>📁 {plan.files} files</div>
                <div>⬇️ {plan.credits} credits</div>
              </div>
              <ul className="space-y-1.5 flex-1 mb-5">
                {plan.features.map(f => (
                  <li key={f} className="flex items-start gap-2 text-xs text-[var(--text2)]">
                    <Check size={12} className="text-[#16A34A] mt-0.5 flex-shrink-0" />
                    {f}
                  </li>
                ))}
                {plan.locked?.map(f => (
                  <li key={f} className="flex items-start gap-2 text-xs text-[var(--text3)] line-through">
                    <span className="w-3 flex-shrink-0">✗</span>
                    {f}
                  </li>
                ))}
              </ul>
              {plan.id === 'free' ? (
                isCurrent ? (
                  <div className="btn btn-ghost btn-md w-full text-[#16A34A] border border-[#16A34A]/20">
                    <Check size={14} /> Current Plan
                  </div>
                ) : (
                  <Link to="/register" className="btn btn-secondary btn-md w-full">Get Started Free</Link>
                )
              ) : isCurrent ? (
                <div className="flex flex-col gap-2 w-full">
                  <div className="flex items-center justify-center gap-1.5 text-xs font-medium text-[#16A34A]">
                    <Check size={13} /> Active Plan
                    {typeof user?.download_credits === 'number' && (
                      <span className="text-[var(--text3)] font-normal">· {user.download_credits} credits left</span>
                    )}
                  </div>
                  <button
                    onClick={() => handlePurchase(plan.id)}
                    disabled={!!loading}
                    className="btn btn-secondary btn-md w-full"
                  >
                    {isLoading
                      ? <RefreshCw size={14} className="animate-spin" />
                      : <>Renew / Add Credits <RefreshCw size={14} /></>}
                  </button>
                </div>
              ) : (
                <button
                  onClick={() => handlePurchase(plan.id)}
                  disabled={!!loading}
                  className={`btn btn-md w-full ${plan.popular || plan.bestValue ? 'btn-primary' : 'btn-secondary'}`}
                >
                  {isLoading
                    ? <RefreshCw size={14} className="animate-spin" />
                    : <>{user ? (user.plan && user.plan !== 'free' ? 'Switch Plan' : 'Upgrade') : 'Get Started'} <ArrowRight size={14} /></>}
                </button>
              )}
            </div>
          )
        })}
      </div>

      {/* Commercial / Connect with our team */}
      <div className="card p-6 mb-8 flex flex-col sm:flex-row items-start sm:items-center gap-5 border-[var(--border)] bg-gradient-to-r from-[var(--accent)]/5 to-transparent">
        <div className="w-12 h-12 rounded-xl bg-[var(--accent)]/10 flex items-center justify-center flex-shrink-0">
          <Building2 size={24} className="text-[var(--accent)]" />
        </div>
        <div className="flex-1">
          <div className="flex items-center gap-2 mb-1">
            <h3 className="font-semibold text-[var(--text)] text-lg">{COMMERCIAL_PLAN.name}</h3>
            <span className="badge badge-purple text-[10px]">Custom Pricing</span>
          </div>
          <p className="text-sm text-[var(--text2)] mb-3">{COMMERCIAL_PLAN.desc}</p>
          <ul className="flex flex-wrap gap-x-4 gap-y-1.5">
            {COMMERCIAL_PLAN.features.map(f => (
              <li key={f} className="flex items-center gap-1.5 text-xs text-[var(--text2)]">
                <Check size={12} className="text-[#16A34A]" /> {f}
              </li>
            ))}
          </ul>
        </div>
        <a
          href="mailto:sales@vpresearchcompany.com?subject=Commercial%20Plan%20Inquiry%20-%20Raas"
          className="btn btn-primary btn-lg flex-shrink-0 whitespace-nowrap"
        >
          <Mail size={16} /> Connect with our Team
        </a>
      </div>

      {/* Credit Pack */}
      <div className="card p-5 flex flex-col sm:flex-row items-start sm:items-center gap-4 border-[var(--accent)]/20 bg-gradient-to-r from-[var(--accent)]/5 to-transparent">
        <div className="w-10 h-10 rounded-xl bg-[var(--accent)]/10 flex items-center justify-center flex-shrink-0">
          <Crown size={20} className="text-[var(--accent)]" />
        </div>
        <div className="flex-1">
          <h3 className="font-semibold text-[var(--text)]">Need just a few more downloads?</h3>
          <p className="text-sm text-[var(--text2)] mt-0.5">Buy 10 download credits for ₹{CREDIT_PACK.price} — valid for 1 year, works with any plan</p>
          <ul className="flex flex-wrap gap-x-4 gap-y-1 mt-2">
            {CREDIT_PACK.features.map(f => (
              <li key={f} className="flex items-center gap-1.5 text-xs text-[var(--text3)]">
                <Check size={11} className="text-[#16A34A]" /> {f}
              </li>
            ))}
          </ul>
        </div>
        <button
          onClick={() => handlePurchase('credits_10')}
          disabled={!user || !!loading}
          className="btn btn-secondary btn-md flex-shrink-0"
        >
          {loading === 'credits_10' ? <RefreshCw size={14} className="animate-spin" /> : null}
          Buy 10 Credits — ₹{CREDIT_PACK.price}
        </button>
      </div>

      <p className="text-center text-xs text-[var(--text3)] mt-6">
        💡 Demo mode: payment gateway is optional. If not configured, clicking "Upgrade" instantly activates the plan for testing.
      </p>
    </Wrapper>
  )
}