import React, { useEffect, useState, useMemo } from 'react'
import api from '../utils/api'
import toast from 'react-hot-toast'
import {
  Wrench, Activity, Gauge, FlaskConical, Target, AlertTriangle,
  Dices, Users, Network, Calculator, ChevronDown, ChevronUp,
  PlayCircle, Lock, RefreshCw, FileSpreadsheet, Sparkles
} from 'lucide-react'
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend,
} from 'recharts'

const PURPLE = '#6B2D8B'
const BORDER = 'rgba(107,45,139,0.12)'
const GOLD   = '#C8860B'

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

// ── Field renderer for the inline parameter form ────────────────────────
function InputField({ field, value, onChange, numericColumns, categoricalColumns }) {
  const label = (
    <label style={{ display:'block', fontSize:'12px', fontWeight:600, color:'#6B6280', marginBottom:'6px' }}>
      {field.label}{field.required === false && <span style={{ color:'#A89FBC' }}> (optional)</span>}
    </label>
  )
  const inputStyle = {
    width:'100%', boxSizing:'border-box', padding:'9px 12px', fontSize:'13px',
    border: `1px solid ${BORDER}`, borderRadius:'8px', outline:'none',
  }

  if (field.type === 'column_numeric' || field.type === 'column_categorical') {
    const options = field.type === 'column_numeric' ? numericColumns : categoricalColumns
    return (
      <div style={{ marginBottom:'12px' }}>
        {label}
        <select style={inputStyle} value={value || ''} onChange={e => onChange(e.target.value)}>
          <option value="">Select a column…</option>
          {(options || []).map(c => <option key={c} value={c}>{c}</option>)}
        </select>
      </div>
    )
  }
  if (field.type === 'select') {
    return (
      <div style={{ marginBottom:'12px' }}>
        {label}
        <select style={inputStyle} value={value || field.options[0]} onChange={e => onChange(e.target.value)}>
          {field.options.map(o => <option key={o} value={o}>{o}</option>)}
        </select>
      </div>
    )
  }
  if (field.type === 'number') {
    return (
      <div style={{ marginBottom:'12px' }}>
        {label}
        <input type="number" style={inputStyle} value={value ?? ''}
          onChange={e => onChange(e.target.value === '' ? '' : Number(e.target.value))} />
      </div>
    )
  }
  if (field.type === 'text') {
    return (
      <div style={{ marginBottom:'12px' }}>
        {label}
        <input type="text" style={{ ...inputStyle, fontFamily:'monospace' }} value={value || ''}
          onChange={e => onChange(e.target.value)} />
      </div>
    )
  }
  if (['number_array', 'number_matrix', 'edge_list', 'distribution_list'].includes(field.type)) {
    const placeholders = {
      number_array: 'e.g. 3, 5, 2',
      number_matrix: 'e.g.\n1, 2\n3, 1',
      edge_list: 'e.g.\nA, B, 4\nB, C, 2',
      distribution_list: 'e.g.\nspeed, normal, 100, 10\nhours, uniform, 6, 9',
    }
    const hints = {
      number_array: 'Comma-separated numbers',
      number_matrix: 'One constraint row per line, comma-separated',
      edge_list: 'One edge per line: nodeA, nodeB, weight',
      distribution_list: 'One variable per line: name, normal|uniform, param1, param2',
    }
    const isTextarea = field.type !== 'number_array'
    return (
      <div style={{ marginBottom:'12px' }}>
        {label}
        {isTextarea ? (
          <textarea rows={3} placeholder={placeholders[field.type]} style={{ ...inputStyle, fontFamily:'monospace', resize:'vertical' }}
            value={value || ''} onChange={e => onChange(e.target.value)} />
        ) : (
          <input type="text" placeholder={placeholders[field.type]} style={inputStyle}
            value={value || ''} onChange={e => onChange(e.target.value)} />
        )}
        <p style={{ fontSize:'11px', color:'#A89FBC', marginTop:'4px' }}>{hints[field.type]}</p>
      </div>
    )
  }
  return null
}

function buildParameters(item, rawValues) {
  const params = {}
  for (const field of item.inputs) {
    const raw = rawValues[field.name]
    if (raw === undefined || raw === '') continue
    switch (field.type) {
      case 'number':
        params[field.name] = Number(raw); break
      case 'number_array':
        params[field.name] = String(raw).split(',').map(s => Number(s.trim())).filter(n => !isNaN(n)); break
      case 'number_matrix':
        params[field.name] = String(raw).split('\n').filter(Boolean).map(l => l.split(',').map(s => Number(s.trim()))); break
      case 'edge_list':
        params[field.name] = String(raw).split('\n').filter(Boolean).map(l => {
          const [a, b, w] = l.split(',').map(s => s.trim()); return [a, b, Number(w)]
        }); break
      case 'distribution_list':
        params[field.name] = String(raw).split('\n').filter(Boolean).map(l => {
          const [name, distribution, p1, p2] = l.split(',').map(s => s.trim())
          return { name, distribution: distribution || 'normal', p1: Number(p1), p2: Number(p2) }
        }); break
      default:
        params[field.name] = raw
    }
  }
  return params
}

function ResultView({ result }) {
  if (!result) return null
  const curveKey = ['curve', 'chart_points', 'histogram', 'history'].find(k => Array.isArray(result[k]))
  const scalarEntries = Object.entries(result).filter(([k, v]) => typeof v !== 'object' && k !== 'type')

  return (
    <div style={{ marginTop:'16px' }}>
      {scalarEntries.length > 0 && (
        <div style={{ display:'grid', gridTemplateColumns:'repeat(auto-fit, minmax(110px, 1fr))', gap:'10px', marginBottom:'14px' }}>
          {scalarEntries.map(([k, v]) => (
            <div key={k} style={{ textAlign:'center', padding:'10px', borderRadius:'10px', background:'rgba(107,45,139,0.04)', border:`1px solid ${BORDER}` }}>
              <div style={{ fontSize:'15px', fontWeight:700, color:'#241B33' }}>{String(v)}</div>
              <div style={{ fontSize:'10px', color:'#A89FBC', textTransform:'capitalize' }}>{k.replace(/_/g,' ')}</div>
            </div>
          ))}
        </div>
      )}
      {curveKey && result[curveKey].length > 0 && (
        <div style={{ marginBottom:'14px' }}>
          <p style={{ fontSize:'11px', fontWeight:700, color:'#A89FBC', textTransform:'uppercase', letterSpacing:'0.06em', marginBottom:'6px' }}>
            {curveKey.replace(/_/g,' ')}
          </p>
          <ResponsiveContainer width="100%" height={220}>
            <LineChart data={result[curveKey]}>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(107,45,139,0.08)" />
              <XAxis dataKey={Object.keys(result[curveKey][0])[0]} stroke="#A89FBC" fontSize={11} />
              <YAxis stroke="#A89FBC" fontSize={11} />
              <Tooltip contentStyle={{ background:'#fff', border:`1px solid ${BORDER}`, borderRadius:'8px', fontSize:'12px' }} />
              <Legend wrapperStyle={{ fontSize:'11px' }} />
              {Object.keys(result[curveKey][0]).slice(1).map((k, i) => (
                <Line key={k} type="monotone" dataKey={k} stroke={i === 0 ? PURPLE : '#16A34A'} dot={false} strokeWidth={2} />
              ))}
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}
      {Array.isArray(result.shortest_path) && (
        <div style={{ display:'flex', flexWrap:'wrap', alignItems:'center', gap:'6px', marginBottom:'10px' }}>
          {result.shortest_path.map((node, i) => (
            <React.Fragment key={i}>
              <span style={{ padding:'3px 10px', borderRadius:'999px', background:'rgba(107,45,139,0.08)', color: PURPLE, fontSize:'12px', fontWeight:600 }}>{node}</span>
              {i < result.shortest_path.length - 1 && <span style={{ color:'#A89FBC' }}>→</span>}
            </React.Fragment>
          ))}
        </div>
      )}
      <details style={{ fontSize:'11px', color:'#A89FBC' }}>
        <summary style={{ cursor:'pointer' }}>Raw JSON</summary>
        <pre style={{ marginTop:'6px', background:'rgba(107,45,139,0.04)', padding:'10px', borderRadius:'8px', overflowX:'auto' }}>
          {JSON.stringify(result, null, 2)}
        </pre>
      </details>
    </div>
  )
}

// ── One numbered sub-test row (collapsed → expands into its own form) ───
function SubTestRow({ item, module, fileId, numericColumns, categoricalColumns, autoOpen, initialValues, recommendedReason }) {
  const [open, setOpen] = useState(!!autoOpen)
  const [rawValues, setRawValues] = useState(initialValues || {})
  const [running, setRunning] = useState(false)
  const [result, setResult] = useState(null)

  const handleRun = async () => {
    if (module.needs_dataframe && !fileId) {
      toast.error('This file must finish processing before running engineering analytics')
      return
    }
    setRunning(true)
    setResult(null)
    try {
      const parameters = buildParameters(item, rawValues)
      const payload = { analysis_type: item.analysis_id, parameters }
      if (module.needs_dataframe) payload.file_id = Number(fileId)
      const { data } = await api.post('/engineering/run', payload)
      setResult(data.result)
      toast.success('Analysis complete')
    } catch (err) {
      toast.error(err.response?.data?.error || 'Something went wrong running this analysis')
    } finally {
      setRunning(false)
    }
  }

  return (
    <div style={{ borderTop: `1px solid ${BORDER}` }}>
      <button
        onClick={() => setOpen(o => !o)}
        style={{
          width:'100%', display:'flex', alignItems:'center', gap:'10px',
          padding:'12px 16px', background:'none', border:'none', cursor:'pointer', textAlign:'left',
        }}
      >
        <span style={{
          minWidth:'28px', height:'20px', borderRadius:'999px', background:'rgba(107,45,139,0.10)',
          color: PURPLE, fontSize:'10px', fontWeight:700, display:'flex', alignItems:'center', justifyContent:'center', padding:'0 6px',
        }}>
          {item.number}
        </span>
        <span style={{ flex:1, fontSize:'13px', fontWeight:600, color:'#241B33', display:'flex', alignItems:'center', gap:'6px' }}>
          {item.label}
          {item.premium && <Lock size={11} style={{ color: GOLD }} />}
        </span>
        {open ? <ChevronUp size={15} style={{ color:'#A89FBC' }} /> : <ChevronDown size={15} style={{ color:'#A89FBC' }} />}
      </button>

      {open && (
        <div style={{ padding:'0 16px 16px 54px' }}>
          {recommendedReason && (
            <div style={{
              display:'flex', alignItems:'flex-start', gap:'6px', marginBottom:'12px',
              padding:'8px 10px', borderRadius:'8px', background:'rgba(200,134,11,0.08)',
              border:'1px solid rgba(200,134,11,0.18)', fontSize:'11px', color:'#8A6207',
            }}>
              <Sparkles size={12} style={{ marginTop:'1px', flexShrink:0 }} />
              {recommendedReason}
            </div>
          )}
          {item.inputs.map(field => (
            <InputField
              key={field.name}
              field={field}
              value={rawValues[field.name]}
              onChange={v => setRawValues(prev => ({ ...prev, [field.name]: v }))}
              numericColumns={numericColumns}
              categoricalColumns={categoricalColumns}
            />
          ))}
          <button
            onClick={handleRun}
            disabled={running}
            style={{
              display:'inline-flex', alignItems:'center', gap:'6px', padding:'8px 16px',
              borderRadius:'8px', border:'none', background: PURPLE, color:'#fff',
              fontSize:'12px', fontWeight:700, cursor: running ? 'wait' : 'pointer',
            }}
          >
            {running ? <RefreshCw size={13} className="animate-spin" /> : <PlayCircle size={13} />}
            Run
          </button>
          {result && <ResultView result={result} />}
        </div>
      )}
    </div>
  )
}

// ── Top-level suggestion card ────────────────────────────────────────────
export default function EngineeringSuggestionsPanel({ fileId, file }) {
  const [modules, setModules] = useState([])
  const [expanded, setExpanded] = useState(false)
  const [activeModuleKey, setActiveModuleKey] = useState(null)
  const [loading, setLoading] = useState(true)
  const [recommended, setRecommended] = useState([])
  const [suggestLoading, setSuggestLoading] = useState(true)
  const [highlight, setHighlight] = useState(null) // { itemKey, prefill, reason }

  useEffect(() => {
    api.get('/engineering/catalog')
      .then(r => {
        setModules(r.data.modules || [])
        if (r.data.modules?.length) setActiveModuleKey(r.data.modules[0].module_key)
      })
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => {
    if (!fileId) { setSuggestLoading(false); return }
    api.get(`/engineering/suggest/${fileId}`)
      .then(r => {
        const recs = r.data.recommended || []
        setRecommended(recs)
        if (recs.length > 0) setExpanded(true) // surface AI suggestions immediately
      })
      .catch(() => {})
      .finally(() => setSuggestLoading(false))
  }, [fileId])

  const numericColumns = useMemo(
    () => (file?.columns_meta || []).filter(c => ['integer','float'].includes(c.python_type)).map(c => c.name),
    [file]
  )
  const categoricalColumns = useMemo(
    () => (file?.columns_meta || []).filter(c => c.python_type === 'string').map(c => c.name),
    [file]
  )

  const activeModule = modules.find(m => m.module_key === activeModuleKey)
  const totalSubTests = modules.reduce((sum, m) => sum + m.items.length, 0)

  const jumpToRecommendation = (rec) => {
    setActiveModuleKey(rec.module_key)
    setHighlight({ itemKey: rec.item_key, prefill: rec.prefill, reason: rec.reason })
    setExpanded(true)
  }

  if (loading || modules.length === 0) return null

  return (
    <div className="card" style={{ marginBottom:'16px', overflow:'hidden' }}>
      {/* ── Collapsed summary row — same visual language as the "Detected: X Data" card ── */}
      <div style={{ display:'flex', alignItems:'center', gap:'14px', padding:'16px' }}>
        <div style={{
          width:'40px', height:'40px', borderRadius:'12px', flexShrink:0,
          background:'rgba(107,45,139,0.08)', display:'flex', alignItems:'center', justifyContent:'center',
        }}>
          <Wrench size={20} style={{ color: PURPLE }} />
        </div>
        <div style={{ flex:1, minWidth:0 }}>
          <div style={{ display:'flex', alignItems:'center', gap:'8px', flexWrap:'wrap' }}>
            <span style={{ fontWeight:700, color:'#241B33', fontSize:'14px' }}>
              {recommended.length > 0 ? `${recommended.length} Engineering Test${recommended.length > 1 ? 's' : ''} Recommended For This File` : 'Engineering Analytics Available'}
            </span>
            <span style={{
              fontSize:'10px', fontWeight:700, padding:'3px 9px', borderRadius:'999px',
              color: PURPLE, background:'rgba(107,45,139,0.10)',
            }}>
              {totalSubTests} Sub-Tests · 9 Modules
            </span>
          </div>
          <p style={{ fontSize:'12px', color:'#6B6280', marginTop:'3px' }}>
            {recommended.length > 0
              ? 'Based on this file\'s columns, these tests are likely relevant — or browse all 9 modules below.'
              : 'Reliability, Quality Control, DOE, Optimization and 5 more engineering modules can also be run — some use this file\'s columns, others take manual inputs (formulas, rates, constraints).'}
          </p>
        </div>
        <button
          onClick={() => setExpanded(e => !e)}
          style={{
            display:'inline-flex', alignItems:'center', gap:'6px', padding:'8px 14px',
            borderRadius:'8px', border:`1px solid ${BORDER}`, background: expanded ? 'rgba(107,45,139,0.08)' : '#fff',
            color: PURPLE, fontSize:'12px', fontWeight:700, cursor:'pointer', flexShrink:0,
          }}
        >
          {expanded ? 'Hide' : 'Explore'} {expanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
        </button>
      </div>

      {/* ── Expanded: AI-style recommendations + module pills + numbered sub-test list ── */}
      {expanded && (
        <div style={{ borderTop:`1px solid ${BORDER}` }}>
          {!suggestLoading && recommended.length > 0 && (
            <div style={{ padding:'14px 16px', borderBottom:`1px solid ${BORDER}`, background:'rgba(200,134,11,0.04)' }}>
              <div style={{ display:'flex', alignItems:'center', gap:'6px', marginBottom:'8px' }}>
                <Sparkles size={13} style={{ color: GOLD }} />
                <span style={{ fontSize:'11px', fontWeight:700, color: GOLD, textTransform:'uppercase', letterSpacing:'0.05em' }}>
                  Recommended for this file
                </span>
              </div>
              <div style={{ display:'flex', flexDirection:'column', gap:'6px' }}>
                {recommended.map(rec => (
                  <button
                    key={rec.item_key}
                    onClick={() => jumpToRecommendation(rec)}
                    style={{
                      display:'flex', alignItems:'center', gap:'10px', padding:'10px 12px',
                      borderRadius:'10px', border:`1px solid ${BORDER}`, background:'#fff',
                      textAlign:'left', cursor:'pointer', width:'100%',
                    }}
                  >
                    {React.createElement(MODULE_ICONS[rec.module_key] || Wrench, { size:15, style:{ color: PURPLE, flexShrink:0 } })}
                    <span style={{ flex:1, minWidth:0 }}>
                      <span style={{ fontSize:'13px', fontWeight:700, color:'#241B33' }}>{rec.label}</span>
                      <span style={{ display:'block', fontSize:'11px', color:'#6B6280', marginTop:'1px' }}>{rec.reason}</span>
                    </span>
                    <ChevronDown size={14} style={{ transform:'rotate(-90deg)', color:'#A89FBC', flexShrink:0 }} />
                  </button>
                ))}
              </div>
            </div>
          )}

          <div style={{ display:'flex', flexWrap:'wrap', gap:'6px', padding:'12px 16px', borderBottom:`1px solid ${BORDER}` }}>
            {modules.map(mod => {
              const Icon = MODULE_ICONS[mod.module_key] || Wrench
              const isActive = mod.module_key === activeModuleKey
              return (
                <button
                  key={mod.module_key}
                  onClick={() => { setActiveModuleKey(mod.module_key); setHighlight(null) }}
                  style={{
                    display:'flex', alignItems:'center', gap:'6px', padding:'6px 12px', borderRadius:'999px',
                    border: isActive ? `1.5px solid ${PURPLE}` : `1px solid ${BORDER}`,
                    background: isActive ? 'rgba(107,45,139,0.09)' : '#fff',
                    color: isActive ? PURPLE : '#6B6280',
                    fontSize:'12px', fontWeight: isActive ? 700 : 500, cursor:'pointer', whiteSpace:'nowrap',
                  }}
                >
                  <Icon size={13} /> {mod.label}
                </button>
              )
            })}
          </div>

          {activeModule && (
            <>
              {activeModule.needs_dataframe && (
                <div style={{ display:'flex', alignItems:'center', gap:'6px', padding:'10px 16px', fontSize:'11px', color:'#A89FBC', background:'rgba(107,45,139,0.03)' }}>
                  <FileSpreadsheet size={12} /> Uses columns from <strong style={{ color:'#6B6280' }}>{file?.original_name}</strong>
                </div>
              )}
              {activeModule.items.map(item => (
                <SubTestRow
                  key={item.key}
                  item={item}
                  module={activeModule}
                  fileId={fileId}
                  numericColumns={numericColumns}
                  categoricalColumns={categoricalColumns}
                  autoOpen={highlight?.itemKey === item.key}
                  initialValues={highlight?.itemKey === item.key ? highlight.prefill : undefined}
                  recommendedReason={highlight?.itemKey === item.key ? highlight.reason : null}
                />
              ))}
            </>
          )}
        </div>
      )}
    </div>
  )
}