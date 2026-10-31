import React, { useEffect, useState, useMemo } from 'react'
import api from '../utils/api'
import toast from 'react-hot-toast'
import {
  Wrench, Activity, Gauge, FlaskConical, Target, AlertTriangle,
  Dices, Users, Network, Calculator, RefreshCw, PlayCircle,
  ChevronRight, FileSpreadsheet, Lock, Zap
} from 'lucide-react'
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, Legend
} from 'recharts'

const MODULE_ICONS = {
  Reliability: Activity,
  QualityControl: Gauge,
  DOE: FlaskConical,
  Optimization: Target,
  ErrorAnalysis: AlertTriangle,
  Simulation: Dices,
  Queuing: Users,
  NetworkAnalysis: Network,
  NumericalMethods: Calculator,
}

// ── Field renderer, driven by the catalog's `inputs` schema ────────────────
function InputField({ field, value, onChange, numericColumns, categoricalColumns }) {
  const label = (
    <label className="label">
      {field.label}
      {field.required === false && <span className="text-[var(--text3)]"> (optional)</span>}
    </label>
  )

  if (field.type === 'column_numeric' || field.type === 'column_categorical') {
    const options = field.type === 'column_numeric' ? numericColumns : categoricalColumns
    return (
      <div className="mb-4">
        {label}
        <select className="input" value={value || ''} onChange={e => onChange(e.target.value)}>
          <option value="">Select a column…</option>
          {(options || []).map(c => <option key={c} value={c}>{c}</option>)}
        </select>
      </div>
    )
  }

  if (field.type === 'select') {
    return (
      <div className="mb-4">
        {label}
        <select className="input" value={value || field.options[0]} onChange={e => onChange(e.target.value)}>
          {field.options.map(o => <option key={o} value={o}>{o}</option>)}
        </select>
      </div>
    )
  }

  if (field.type === 'number') {
    return (
      <div className="mb-4">
        {label}
        <input
          type="number" className="input"
          value={value ?? ''}
          onChange={e => onChange(e.target.value === '' ? '' : Number(e.target.value))}
        />
      </div>
    )
  }

  if (field.type === 'text') {
    return (
      <div className="mb-4">
        {label}
        <input type="text" className="input font-mono text-sm" value={value || ''} onChange={e => onChange(e.target.value)} />
      </div>
    )
  }

  if (field.type === 'number_array') {
    return (
      <div className="mb-4">
        {label}
        <input type="text" placeholder="e.g. 3, 5, 2" className="input" value={value || ''} onChange={e => onChange(e.target.value)} />
        <p className="text-[11px] text-[var(--text3)] mt-1">Comma-separated numbers</p>
      </div>
    )
  }

  if (field.type === 'number_matrix') {
    return (
      <div className="mb-4">
        {label}
        <textarea
          rows={3} placeholder={'e.g.\n1, 2\n3, 1'}
          className="input font-mono text-sm" value={value || ''} onChange={e => onChange(e.target.value)}
        />
        <p className="text-[11px] text-[var(--text3)] mt-1">One constraint row per line, comma-separated</p>
      </div>
    )
  }

  if (field.type === 'edge_list') {
    return (
      <div className="mb-4">
        {label}
        <textarea
          rows={3} placeholder={'e.g.\nA, B, 4\nB, C, 2'}
          className="input font-mono text-sm" value={value || ''} onChange={e => onChange(e.target.value)}
        />
        <p className="text-[11px] text-[var(--text3)] mt-1">One edge per line: nodeA, nodeB, weight</p>
      </div>
    )
  }

  if (field.type === 'distribution_list') {
    return (
      <div className="mb-4">
        {label}
        <textarea
          rows={3} placeholder={'e.g.\nspeed, normal, 100, 10\nhours, uniform, 6, 9'}
          className="input font-mono text-sm" value={value || ''} onChange={e => onChange(e.target.value)}
        />
        <p className="text-[11px] text-[var(--text3)] mt-1">
          One variable per line: name, normal|uniform, param1, param2 (normal = mean, std · uniform = low, high)
        </p>
      </div>
    )
  }

  return null
}

// ── Parse raw text-area strings into the JSON shapes the backend expects ──
function buildParameters(item, rawValues) {
  const params = {}
  for (const field of item.inputs) {
    const raw = rawValues[field.name]
    if (raw === undefined || raw === '') continue

    switch (field.type) {
      case 'number':
        params[field.name] = Number(raw)
        break
      case 'number_array':
        params[field.name] = String(raw).split(',').map(s => Number(s.trim())).filter(n => !isNaN(n))
        break
      case 'number_matrix':
        params[field.name] = String(raw).split('\n').filter(Boolean).map(line =>
          line.split(',').map(s => Number(s.trim())))
        break
      case 'edge_list':
        params[field.name] = String(raw).split('\n').filter(Boolean).map(line => {
          const [a, b, w] = line.split(',').map(s => s.trim())
          return [a, b, Number(w)]
        })
        break
      case 'distribution_list':
        params[field.name] = String(raw).split('\n').filter(Boolean).map(line => {
          const [name, distribution, p1, p2] = line.split(',').map(s => s.trim())
          return { name, distribution: distribution || 'normal', p1: Number(p1), p2: Number(p2) }
        })
        break
      default:
        params[field.name] = raw
    }
  }
  return params
}

// ── Render a result payload: scalars as stat tiles, arrays as chart/table ──
function ResultView({ result }) {
  if (!result) return null
  const curveKey = ['curve', 'chart_points', 'histogram', 'history'].find(k => Array.isArray(result[k]))
  const scalarEntries = Object.entries(result).filter(([k, v]) => typeof v !== 'object' && k !== 'type')

  return (
    <div className="space-y-5">
      {scalarEntries.length > 0 && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          {scalarEntries.map(([k, v]) => (
            <div key={k} className="text-center p-3 rounded-xl bg-[var(--surface2)] border border-[var(--border)]">
              <div className="text-lg font-bold text-[var(--text)]">{String(v)}</div>
              <div className="text-[11px] text-[var(--text3)] capitalize">{k.replace(/_/g, ' ')}</div>
            </div>
          ))}
        </div>
      )}

      {curveKey && result[curveKey].length > 0 && (
        <div className="card p-4">
          <p className="text-xs font-semibold text-[var(--text3)] uppercase tracking-wider mb-2">
            {curveKey.replace(/_/g, ' ')}
          </p>
          <ResponsiveContainer width="100%" height={260}>
            <LineChart data={result[curveKey]}>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(107,45,139,0.08)" />
              <XAxis dataKey={Object.keys(result[curveKey][0])[0]} stroke="#A89FBC" fontSize={11} />
              <YAxis stroke="#A89FBC" fontSize={11} />
              <Tooltip contentStyle={{ background: '#FFFFFF', border: '1px solid rgba(107,45,139,0.18)', borderRadius: '10px', fontSize: '12px' }} />
              <Legend wrapperStyle={{ fontSize: '12px' }} />
              {Object.keys(result[curveKey][0]).slice(1).map((k, i) => (
                <Line key={k} type="monotone" dataKey={k} stroke={i === 0 ? '#6B2D8B' : '#16A34A'} dot={false} strokeWidth={2} />
              ))}
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}

      {result.group_means && (
        <div className="card p-4">
          <p className="text-xs font-semibold text-[var(--text3)] uppercase tracking-wider mb-2">Group Means</p>
          <div className="table-container">
            <table className="table">
              <tbody>
                {Object.entries(result.group_means).map(([k, v]) => (
                  <tr key={k}><td>{k}</td><td className="text-right font-mono">{v}</td></tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {Array.isArray(result.table) && (
        <div className="card p-4">
          <p className="text-xs font-semibold text-[var(--text3)] uppercase tracking-wider mb-2">ANOVA Table</p>
          <div className="table-container">
            <table className="table">
              <thead>
                <tr>{Object.keys(result.table[0]).map(k => <th key={k}>{k}</th>)}</tr>
              </thead>
              <tbody>
                {result.table.map((row, i) => (
                  <tr key={i}>
                    {Object.values(row).map((v, j) => <td key={j}>{v === null ? '—' : String(v)}</td>)}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {result.shortest_path && (
        <div className="card p-4">
          <p className="text-xs font-semibold text-[var(--text3)] uppercase tracking-wider mb-2">Shortest Path</p>
          <div className="flex items-center flex-wrap gap-2">
            {result.shortest_path.map((node, i) => (
              <React.Fragment key={i}>
                <span className="badge badge-purple">{node}</span>
                {i < result.shortest_path.length - 1 && <ChevronRight size={14} className="text-[var(--text3)]" />}
              </React.Fragment>
            ))}
          </div>
        </div>
      )}

      <details className="text-xs text-[var(--text3)]">
        <summary className="cursor-pointer select-none">Raw JSON</summary>
        <pre className="mt-2 bg-[var(--surface2)] p-3 rounded-xl overflow-x-auto">{JSON.stringify(result, null, 2)}</pre>
      </details>
    </div>
  )
}

export default function EngineeringPage() {
  const [modules, setModules] = useState([])
  const [activeModuleKey, setActiveModuleKey] = useState(null)
  const [activeItem, setActiveItem] = useState(null)
  const [rawValues, setRawValues] = useState({})
  const [files, setFiles] = useState([])
  const [fileId, setFileId] = useState('')
  const [fileColumns, setFileColumns] = useState({ numeric: [], categorical: [] })
  const [loadingCatalog, setLoadingCatalog] = useState(true)
  const [running, setRunning] = useState(false)
  const [result, setResult] = useState(null)
  const [creditsRemaining, setCreditsRemaining] = useState(null)

  useEffect(() => {
    api.get('/engineering/catalog')
      .then(r => {
        setModules(r.data.modules || [])
        if (r.data.modules?.length) setActiveModuleKey(r.data.modules[0].module_key)
      })
      .catch(() => toast.error('Could not load Engineering catalog'))
      .finally(() => setLoadingCatalog(false))
  }, [])

  useEffect(() => {
    api.get('/excel/files?per_page=50').then(r => setFiles(r.data.files || [])).catch(() => {})
  }, [])

  const activeModule = useMemo(
    () => modules.find(m => m.module_key === activeModuleKey),
    [modules, activeModuleKey]
  )

  useEffect(() => {
    if (!fileId) { setFileColumns({ numeric: [], categorical: [] }); return }
    const f = files.find(x => String(x.id) === String(fileId))
    if (!f) return
    setFileColumns({
      numeric: (f.columns_meta || []).filter(c => ['integer', 'float'].includes(c.python_type)).map(c => c.name),
      categorical: (f.columns_meta || []).filter(c => c.python_type === 'string').map(c => c.name),
    })
  }, [fileId, files])

  const selectItem = (item) => {
    setActiveItem(item)
    setRawValues({})
    setResult(null)
  }

  const handleRun = async () => {
    if (!activeItem) return
    if (activeModule?.needs_dataframe && !fileId) {
      toast.error('Please select a file first')
      return
    }
    setRunning(true)
    setResult(null)
    try {
      const parameters = buildParameters(activeItem, rawValues)
      const payload = { analysis_type: activeItem.analysis_id, parameters }
      if (activeModule?.needs_dataframe) payload.file_id = Number(fileId)

      const { data } = await api.post('/engineering/run', payload)
      setResult(data.result)
      setCreditsRemaining(data.credits_remaining)
      toast.success('Analysis complete')
    } catch (err) {
      toast.error(err.response?.data?.error || 'Something went wrong running this analysis')
      if (err.response?.data?.credits_remaining !== undefined) {
        setCreditsRemaining(err.response.data.credits_remaining)
      }
    } finally {
      setRunning(false)
    }
  }

  if (loadingCatalog) {
    return (
      <div className="space-y-6">
        <div className="skeleton h-10 w-64 rounded-xl" />
        <div className="grid lg:grid-cols-[260px_1fr] gap-5">
          <div className="skeleton h-80 rounded-2xl" />
          <div className="skeleton h-80 rounded-2xl" />
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-6 stagger">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-xl font-bold text-[var(--text)] flex items-center gap-2">
            <Wrench size={20} className="text-[var(--accent)]" />
            Engineering Analytics <span className="gradient-text">— Stage 2</span>
          </h1>
          <p className="text-sm text-[var(--text2)] mt-0.5">
            Reliability, Quality Control, DOE, Optimization, and 5 more engineering modules
          </p>
        </div>
        {creditsRemaining !== null && (
          <div className="flex items-center gap-2 bg-[var(--surface2)] border border-[var(--border)] px-3 py-1.5 rounded-lg">
            <Zap size={13} className="text-[var(--accent)]" />
            <span className="text-xs font-semibold text-[var(--text)]">{creditsRemaining}</span>
            <span className="text-xs text-[var(--text3)]">credits</span>
          </div>
        )}
      </div>

      <div className="grid lg:grid-cols-[260px_1fr] gap-5">
        {/* ── Module sidebar ── */}
        <div className="card p-3 h-fit space-y-1">
          {modules.map(mod => {
            const Icon = MODULE_ICONS[mod.module_key] || Wrench
            const isActive = mod.module_key === activeModuleKey
            return (
              <button
                key={mod.module_key}
                onClick={() => { setActiveModuleKey(mod.module_key); setActiveItem(null); setResult(null) }}
                className={`nav-link w-full ${isActive ? 'active' : ''}`}
              >
                <Icon size={16} />
                <span>{mod.label}</span>
              </button>
            )
          })}
        </div>

        {/* ── Main panel ── */}
        <div className="space-y-4">
          {activeModule && (
            <div className="card p-5">
              <h2 className="section-title">{activeModule.label}</h2>
              <p className="section-desc mb-4">{activeModule.description}</p>

              <div className="flex flex-wrap gap-2">
                {activeModule.items.map(item => (
                  <button
                    key={item.key}
                    onClick={() => selectItem(item)}
                    className={`badge cursor-pointer ${activeItem?.key === item.key ? 'badge-purple' : 'badge-gray'}`}
                  >
                    {item.number && <span className="opacity-70">{item.number}</span>}
                    {item.label}
                    {item.premium && <Lock size={11} />}
                  </button>
                ))}
              </div>
            </div>
          )}

          {activeItem && (
            <div className="card p-5">
              {activeModule.needs_dataframe && (
                <div className="mb-4 pb-4 border-b border-[var(--border)]">
                  <label className="label flex items-center gap-1.5">
                    <FileSpreadsheet size={14} /> Source File
                  </label>
                  <select className="input" value={fileId} onChange={e => setFileId(e.target.value)}>
                    <option value="">Select an uploaded file…</option>
                    {files.map(f => <option key={f.id} value={f.id}>{f.original_name}</option>)}
                  </select>
                </div>
              )}

              {activeItem.inputs.map(field => (
                <InputField
                  key={field.name}
                  field={field}
                  value={rawValues[field.name]}
                  onChange={v => setRawValues(prev => ({ ...prev, [field.name]: v }))}
                  numericColumns={fileColumns.numeric}
                  categoricalColumns={fileColumns.categorical}
                />
              ))}

              <button onClick={handleRun} disabled={running} className="btn btn-primary btn-md">
                {running ? <RefreshCw size={14} className="animate-spin" /> : <PlayCircle size={14} />}
                Run Analysis
              </button>

              {result && (
                <div className="mt-6 pt-6 border-t border-[var(--border)]">
                  <ResultView result={result} />
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}