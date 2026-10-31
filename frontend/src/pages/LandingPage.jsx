import React from 'react'
import { Link } from 'react-router-dom'
import {
  TrendingUp, Upload, Brain, Download, Shield, BarChart2,
  FileSpreadsheet, Zap, ArrowRight, Check, Star, ChevronRight
} from 'lucide-react'

const FEATURES = [
  { icon: Upload, title: 'Instant File Analysis', desc: 'Upload Excel or CSV and get immediate structural analysis — rows, columns, missing data, quality score.' },
  { icon: Brain, title: 'Smart Insights', desc: 'Reads your data and delivers plain-English findings, patterns, anomalies and recommendations.' },
  { icon: BarChart2, title: '6 Analysis Types', desc: 'Summary stats, correlations, distributions, category breakdowns, data quality — all in one platform.' },
  { icon: Shield, title: 'Data Quality Scoring', desc: 'Automatic quality assessment. Know exactly how clean your data is before you act on it.' },
  { icon: Download, title: 'Professional Reports', desc: 'Export polished PDF and Excel reports. Paid feature ensures report value.' },
  { icon: Zap, title: 'Smart Recommendations', desc: 'The system detects your data type and suggests the most relevant analyses automatically.' },
]

export default function LandingPage() {
  return (
    <div className="min-h-screen bg-[var(--bg)] overflow-x-hidden">
      {/* Nav */}
      <nav className="fixed top-0 inset-x-0 z-50 border-b border-[var(--border)] bg-[var(--bg)]/80 backdrop-blur-lg">
        <div className="max-w-6xl mx-auto px-4 h-14 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-xl bg-gradient-to-br from-[var(--accent)] to-[var(--cyan)] flex items-center justify-center">
              <TrendingUp size={16} className="text-white" />
            </div>
            <span className="font-bold text-[var(--text)]">Raas <span className="gradient-text">by VP</span></span>
          </div>
          <div className="flex items-center gap-3">
            <Link to="/pricing" className="hidden sm:block text-sm text-[var(--text2)] hover:text-[var(--text)] transition-colors">Pricing</Link>
            <Link to="/login" className="btn btn-ghost btn-sm">Sign In</Link>
            <Link to="/register" className="btn btn-primary btn-sm">Get Started Free</Link>
          </div>
        </div>
      </nav>

      {/* Hero */}
      <section className="pt-28 pb-20 px-4 relative overflow-hidden">
        <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_50%_-20%,var(--accent-glow),transparent_60%)]" />
        <div className="absolute top-32 left-1/4 w-64 h-64 rounded-full bg-[var(--accent)]/5 blur-3xl" />
        <div className="absolute top-48 right-1/4 w-48 h-48 rounded-full bg-cyan-500/5 blur-3xl" />
        <div className="max-w-4xl mx-auto text-center relative z-10">
          <div className="inline-flex items-center gap-2 bg-[var(--accent)]/10 border border-[var(--accent)]/20 rounded-full px-4 py-1.5 text-xs font-semibold text-[var(--accent)] mb-8">
            <Star size={11} /> Advanced Excel Analytics Platform
          </div>
          <h1 className="text-4xl sm:text-5xl lg:text-6xl font-bold text-[var(--text)] leading-tight mb-6">
            Your Excel data,{' '}
            <span className="gradient-text">intelligently</span>{' '}
            analyzed
          </h1>
          <p className="text-lg text-[var(--text2)] max-w-2xl mx-auto mb-10 leading-relaxed">
            Upload any Excel or CSV file. Get instant structural insights, automated analysis,
            data quality scoring, and professional downloadable reports.
          </p>
          <div className="flex flex-col sm:flex-row gap-3 justify-center">
            <Link to="/register" className="btn btn-primary btn-xl">
              Start Free — No Card Required <ArrowRight size={18} />
            </Link>
            <Link to="/pricing" className="btn btn-secondary btn-xl">
              View Plans
            </Link>
          </div>
          <p className="text-xs text-[var(--text3)] mt-4">Free plan includes 3 download credits · No credit card required</p>
        </div>
      </section>

      {/* Feature grid */}
      <section className="py-16 px-4 bg-[var(--surface)]/40">
        <div className="max-w-5xl mx-auto">
          <div className="text-center mb-12">
            <h2 className="text-2xl sm:text-3xl font-bold text-[var(--text)] mb-3">Everything you need to understand your data</h2>
            <p className="text-[var(--text2)]">From raw spreadsheet to actionable insights in minutes</p>
          </div>
          <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {FEATURES.map(({ icon: Icon, title, desc }) => (
              <div key={title} className="card-hover p-5 group">
                <div className="w-10 h-10 rounded-xl bg-[var(--accent)]/10 flex items-center justify-center mb-4 group-hover:bg-[var(--accent)]/20 transition-colors">
                  <Icon size={20} className="text-[var(--accent)]" />
                </div>
                <h3 className="font-semibold text-[var(--text)] mb-1.5">{title}</h3>
                <p className="text-sm text-[var(--text2)] leading-relaxed">{desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* How it works */}
      <section className="py-16 px-4">
        <div className="max-w-4xl mx-auto">
          <div className="text-center mb-12">
            <h2 className="text-2xl sm:text-3xl font-bold text-[var(--text)] mb-3">How it works</h2>
          </div>
          <div className="grid sm:grid-cols-3 gap-6">
            {[
              { step: '01', title: 'Upload', desc: 'Drag and drop your Excel or CSV file — up to 50MB, any format' },
              { step: '02', title: 'Analyze', desc: 'Run any of 6 analysis types. AI reads your data and generates insights' },
              { step: '03', title: 'Download', desc: 'Export professional PDF or Excel reports. Preview free, download with credits' },
            ].map((s, i) => (
              <div key={i} className="text-center">
                <div className="text-5xl font-display font-bold text-[var(--accent)]/20 mb-3">{s.step}</div>
                <h3 className="font-bold text-[var(--text)] mb-2">{s.title}</h3>
                <p className="text-sm text-[var(--text2)]">{s.desc}</p>
                {i < 2 && <ChevronRight size={20} className="text-[var(--text3)] mx-auto mt-4 hidden sm:block" />}
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Pricing preview */}
      <section className="py-16 px-4 bg-[var(--surface)]/40">
        <div className="max-w-4xl mx-auto text-center">
          <h2 className="text-2xl font-bold text-[var(--text)] mb-3">Start free today</h2>
          <p className="text-[var(--text2)] mb-8">Free plan includes uploads, all 4 basic analyses, and 3 download credits. No card needed. Paid plans available daily, weekly, monthly or yearly — in ₹.</p>
          <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
            {[
              { label: 'Free', highlight: '₹0', sub: 'forever', features: ['5 uploads', '3 credits', '4 analysis types'] },
              { label: 'Daily', highlight: '₹49', was: '₹79', sub: '/day', features: ['10 uploads', '15 credits', 'Advanced Engine'] },
              { label: 'Monthly', highlight: '₹399', was: '₹599', sub: '/month', features: ['150 uploads', '150 credits', 'All features'] },
              { label: 'Yearly', highlight: '₹1599', was: '₹1799', sub: '/year', features: ['Unlimited uploads', '2000 credits', 'Priority support'] },
            ].map(p => (
              <div key={p.label} className="card p-4 text-left">
                <p className="text-xs font-semibold text-[var(--text3)] uppercase mb-1">{p.label}</p>
                <p className="text-2xl font-bold text-[var(--text)]">{p.highlight}<span className="text-sm text-[var(--text3)]">{p.sub}</span></p>
                {p.was && <p className="text-xs text-[var(--text3)] line-through mb-1">{p.was}{p.sub}</p>}
                <ul className="mt-3 space-y-1">
                  {p.features.map(f => <li key={f} className="flex items-center gap-1.5 text-xs text-[var(--text2)]"><Check size={11} className="text-[#16A34A]" />{f}</li>)}
                </ul>
              </div>
            ))}
          </div>
          <Link to="/register" className="btn btn-primary btn-xl">
            Create Free Account <ArrowRight size={18} />
          </Link>
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-[var(--border)] py-8 px-4">
        <div className="max-w-5xl mx-auto flex flex-col sm:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-2">
            <div className="w-6 h-6 rounded-lg bg-gradient-to-br from-[var(--accent)] to-[var(--cyan)] flex items-center justify-center">
              <TrendingUp size={12} className="text-white" />
            </div>
            <span className="text-sm font-semibold text-[var(--text)]">Raas — VP Research Company</span>
          </div>
          <p className="text-xs text-[var(--text3)]">Built for data analysts, business teams, and developers</p>
          <div className="flex gap-4 text-xs text-[var(--text3)]">
            <Link to="/pricing" className="hover:text-[var(--text)]">Pricing</Link>
            <Link to="/register" className="hover:text-[var(--text)]">Sign Up</Link>
          </div>
        </div>
      </footer>
    </div>
  )
}
