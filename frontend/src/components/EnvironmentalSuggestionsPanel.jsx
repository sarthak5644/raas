import React, { useEffect, useState, useMemo } from 'react'
import api from '../utils/api'
import toast from 'react-hot-toast'
import {
  Leaf, CloudSun, Factory, Droplets, Bug, Satellite,
  Waves, Recycle, ShieldAlert, ChevronDown, ChevronUp,
  PlayCircle, Lock, RefreshCw, FileSpreadsheet, Sparkles
} from 'lucide-react'
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend,
} from 'recharts'

const PURPLE = '#6B2D8B'
const BORDER = 'rgba(107,45,139,0.12)'
const GOLD   = '#C8860B'

const MODULE_ICONS = {
  Climate: CloudSun,
  CarbonEnergy: Factory,
  EnvQuality: Droplets,
  Biodiversity: Bug,
  RemoteSensing: Satellite,
  Hydrology: Waves,
  Sustainability: Recycle,
  RiskScenario: ShieldAlert,
}

// ── Field renderer for the inline parameter form ────────────────────────
function InputField({ field, value, onChange, numericColumns, categoricalColumns, dateColumns }) {
  const label = (
    <label style={{ display:'block', fontSize:'12px', fontWeight:600, color:'#6B6280', marginBottom:'6px' }}>
      {field.label}{field.required === false && <span style={{ color:'#A89FBC' }}> (optional)</span>}
    </label>
  )
  const inputStyle = {
    width:'100%', boxSizing:'border-box', padding:'9px 12px', fontSize:'13px',
    border: `1px solid ${BORDER}`, borderRadius:'8px', outline:'none',
  }

  if (['column_numeric', 'column_categorical', 'column_date'].includes(field.type)) {
    const options = field.type === 'column_numeric' ? numericColumns
      : field.type === 'column_date' ? dateColumns : categoricalColumns
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
  if (field.type === 'column_list') {
    return (
      <div style={{ marginBottom:'12px' }}>
        {label}
        <input type="text" placeholder="e.g. Emissions, WaterUse, Waste" style={inputStyle}
          value={value || ''} onChange={e => onChange(e.target.value)} />
        {(numericColumns?.length > 0) && (
          <p style={{ fontSize:'11px', color:'#A89FBC', marginTop:'4px' }}>
            Available: {numericColumns.slice(0, 8).join(', ')}{numericColumns.length > 8 ? '…' : ''}
          </p>
        )}
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
  if (field.type === 'number_array') {
    return (
      <div style={{ marginBottom:'12px' }}>
        {label}
        <input type="text" placeholder="e.g. 10, 20, 5, 30" style={inputStyle}
          value={value || ''} onChange={e => onChange(e.target.value)} />
        <p style={{ fontSize:'11px', color:'#A89FBC', marginTop:'4px' }}>Comma-separated numbers</p>
      </div>
    )
  }
  if (field.type === 'scenario_list') {
    return (
      <div style={{ marginBottom:'12px' }}>
        {label}
        <textarea rows={3} placeholder={'e.g.\nlow_reduction, -0.10\nhigh_reduction, -0.50'}
          style={{ ...inputStyle, fontFamily:'monospace', resize:'vertical' }}
          value={value || ''} onChange={e => onChange(e.target.value)} />
        <p style={{ fontSize:'11px', color:'#A89FBC', marginTop:'4px' }}>
          One scenario per line: name, % change as a fraction (-0.10 = -10%)
        </p>
      </div>
    )
  }
  if (field.type === 'aqi_pollutant_list') {
    return (
      <div style={{ marginBottom:'12px' }}>
        {label}
        <textarea rows={3} placeholder={'e.g.\nPM2.5, 85, 61, 90, 101, 200\nNO2, 40, 0, 40, 0, 50'}
          style={{ ...inputStyle, fontFamily:'monospace', resize:'vertical' }}
          value={value || ''} onChange={e => onChange(e.target.value)} />
        <p style={{ fontSize:'11px', color:'#A89FBC', marginTop:'4px' }}>
          One pollutant per line: name, concentration, C_low, C_high, I_low, I_high
        </p>
      </div>
    )
  }
  if (field.type === 'point_value_list') {
    return (
      <div style={{ marginBottom:'12px' }}>
        {label}
        <textarea rows={3} placeholder={'e.g.\n28.7, 77.1, 35\n28.5, 77.3, 42'}
          style={{ ...inputStyle, fontFamily:'monospace', resize:'vertical' }}
          value={value || ''} onChange={e => onChange(e.target.value)} />
        <p style={{ fontSize:'11px', color:'#A89FBC', marginTop:'4px' }}>
          One known point per line: latitude, longitude, value
        </p>
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
      case 'column_list':
        params[field.name] = String(raw).split(',').map(s => s.trim()).filter(Boolean); break
      case 'scenario_list':
        params[field.name] = String(raw).split('\n').filter(Boolean).map(line => {
          const [name, change] = line.split(',').map(s => s.trim())
          return { name, change: Number(change) }
        }); break
      case 'aqi_pollutant_list':
        params[field.name] = String(raw).split('\n').filter(Boolean).map(line => {
          const [name, concentration, c_low, c_high, i_low, i_high] = line.split(',').map(s => s.trim())
          return { name, concentration: Number(concentration), c_low: Number(c_low), c_high: Number(c_high),
                   i_low: Number(i_low), i_high: Number(i_high) }
        }); break
      case 'point_value_list':
        params[field.name] = String(raw).split('\n').filter(Boolean).map(line => {
          const [lat, lon, value] = line.split(',').map(s => Number(s.trim()))
          return { lat, lon, value }
        }); break
      default:
        params[field.name] = raw
    }
  }
  return params
}

function ResultView({ result }) {
  if (!result) return null
  const curveKey = ['curve', 'histogram'].find(k => Array.isArray(result[k]))
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
              {Object.keys(result[curveKey][0]).filter(k => typeof result[curveKey][0][k] === 'number').map((k, i) => (
                <Line key={k} type="monotone" dataKey={k} stroke={i === 0 ? PURPLE : (i === 1 ? '#16A34A' : GOLD)} dot={false} strokeWidth={2} />
              ))}
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}
      {(Array.isArray(result.table) || Array.isArray(result.breakdown) || Array.isArray(result.breakdown_by_activity) || Array.isArray(result.points) || Array.isArray(result.top_rows) || Array.isArray(result.scenarios)) && (
        <div style={{ marginBottom:'10px' }}>
          {['table', 'breakdown', 'breakdown_by_activity', 'points', 'top_rows', 'scenarios'].filter(k => Array.isArray(result[k]) && result[k].length > 0).map(k => (
            <div key={k} style={{ marginBottom:'10px' }}>
              <p style={{ fontSize:'11px', fontWeight:700, color:'#A89FBC', textTransform:'uppercase', letterSpacing:'0.06em', marginBottom:'6px' }}>
                {k.replace(/_/g,' ')}
              </p>
              <div style={{ overflowX:'auto' }}>
                <table style={{ width:'100%', fontSize:'12px', borderCollapse:'collapse' }}>
                  <thead>
                    <tr>{Object.keys(result[k][0]).map(col => (
                      <th key={col} style={{ textAlign:'left', padding:'6px 8px', color:'#A89FBC', borderBottom:`1px solid ${BORDER}` }}>{col}</th>
                    ))}</tr>
                  </thead>
                  <tbody>
                    {result[k].slice(0, 20).map((row, i) => (
                      <tr key={i}>
                        {Object.values(row).map((v, j) => (
                          <td key={j} style={{ padding:'6px 8px', borderBottom:`1px solid ${BORDER}`, color:'#241B33' }}>{v === null ? '—' : String(v)}</td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
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

// ── One numbered sub-test row ─────────────────────────────────────────────
function SubTestRow({ item, fileId, fileName, numericColumns, categoricalColumns, dateColumns, autoOpen, initialValues, recommendedReason }) {
  const [open, setOpen] = useState(!!autoOpen)
  const [rawValues, setRawValues] = useState(initialValues || {})
  const [running, setRunning] = useState(false)
  const [result, setResult] = useState(null)

  const handleRun = async () => {
    if (item.needs_dataframe && !fileId) {
      toast.error('This file must finish processing before running this analysis')
      return
    }
    setRunning(true)
    setResult(null)
    try {
      const parameters = buildParameters(item, rawValues)
      const payload = { analysis_type: item.analysis_id, parameters }
      if (item.needs_dataframe) payload.file_id = Number(fileId)
      const { data } = await api.post('/environmental/run', payload)
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
          {item.needs_dataframe && <FileSpreadsheet size={11} style={{ color:'#A89FBC' }} />}
        </span>
        {open ? <ChevronUp size={15} style={{ color:'#A89FBC' }} /> : <ChevronDown size={15} style={{ color:'#A89FBC' }} />}
      </button>

      {open && (
        <div style={{ padding:'0 16px 16px 54px' }}>
          {item.needs_dataframe && (
            <div style={{ display:'flex', alignItems:'center', gap:'6px', marginBottom:'12px', fontSize:'11px', color:'#A89FBC' }}>
              <FileSpreadsheet size={12} /> Uses columns from <strong style={{ color:'#6B6280' }}>{fileName}</strong>
            </div>
          )}
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
              dateColumns={dateColumns}
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
export default function EnvironmentalSuggestionsPanel({ fileId, file }) {
  const [modules, setModules] = useState([])
  const [expanded, setExpanded] = useState(false)
  const [activeModuleKey, setActiveModuleKey] = useState(null)
  const [loading, setLoading] = useState(true)
  const [recommended, setRecommended] = useState([])
  const [suggestLoading, setSuggestLoading] = useState(true)
  const [highlight, setHighlight] = useState(null)

  useEffect(() => {
    api.get('/environmental/catalog')
      .then(r => {
        setModules(r.data.modules || [])
        if (r.data.modules?.length) setActiveModuleKey(r.data.modules[0].module_key)
      })
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => {
    if (!fileId) { setSuggestLoading(false); return }
    api.get(`/environmental/suggest/${fileId}`)
      .then(r => {
        const recs = r.data.recommended || []
        setRecommended(recs)
        if (recs.length > 0) setExpanded(true)
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
  const dateColumns = useMemo(
    () => (file?.columns_meta || []).filter(c => ['datetime','date_string'].includes(c.python_type)).map(c => c.name),
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
      <div style={{ display:'flex', alignItems:'center', gap:'14px', padding:'16px' }}>
        <div style={{
          width:'40px', height:'40px', borderRadius:'12px', flexShrink:0,
          background:'rgba(107,45,139,0.08)', display:'flex', alignItems:'center', justifyContent:'center',
        }}>
          <Leaf size={20} style={{ color: PURPLE }} />
        </div>
        <div style={{ flex:1, minWidth:0 }}>
          <div style={{ display:'flex', alignItems:'center', gap:'8px', flexWrap:'wrap' }}>
            <span style={{ fontWeight:700, color:'#241B33', fontSize:'14px' }}>
              {recommended.length > 0 ? `${recommended.length} Environmental Test${recommended.length > 1 ? 's' : ''} Recommended For This File` : 'Environmental & Sustainability Analytics Available'}
            </span>
            <span style={{
              fontSize:'10px', fontWeight:700, padding:'3px 9px', borderRadius:'999px',
              color: PURPLE, background:'rgba(107,45,139,0.10)',
            }}>
              {totalSubTests} Sub-Tests · 8 Modules
            </span>
          </div>
          <p style={{ fontSize:'12px', color:'#6B6280', marginTop:'3px' }}>
            {recommended.length > 0
              ? 'Based on this file\'s columns, these tests are likely relevant — or browse all 8 modules below.'
              : 'Climate, Carbon & Energy, Environmental Quality, Biodiversity, Remote Sensing, Hydrology, Sustainability/ESG and Risk analytics — some use this file\'s columns, others take manual inputs.'}
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
                    {React.createElement(MODULE_ICONS[rec.module_key] || Leaf, { size:15, style:{ color: PURPLE, flexShrink:0 } })}
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
              const Icon = MODULE_ICONS[mod.module_key] || Leaf
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
              <div style={{ padding:'10px 16px', fontSize:'11px', color:'#A89FBC', background:'rgba(107,45,139,0.03)' }}>
                {activeModule.description}
              </div>
              {activeModule.items.map(item => (
                <SubTestRow
                  key={item.key}
                  item={item}
                  fileId={fileId}
                  fileName={file?.original_name}
                  numericColumns={numericColumns}
                  categoricalColumns={categoricalColumns}
                  dateColumns={dateColumns}
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