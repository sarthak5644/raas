import React, { useEffect, useState, useMemo } from 'react'
import api from '../utils/api'
import toast from 'react-hot-toast'
import {
  HeartPulse, Calculator, Bug, Target, ClipboardList, Activity, Gauge,
  FlaskConical, Layers, Landmark, Leaf, Users2, TrendingUp,
  ChevronDown, ChevronUp, PlayCircle, Lock, RefreshCw, FileSpreadsheet, Sparkles
} from 'lucide-react'
import {
  LineChart, Line, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend,
} from 'recharts'

const PURPLE = '#6B2D8B'
const BORDER = 'rgba(107,45,139,0.12)'
const GOLD   = '#C8860B'
const SERIES_COLORS = [PURPLE, '#16A34A', GOLD, '#0EA5E9', '#DC2626', '#8B5CF6']

const MODULE_ICONS = {
  Biostatistics: Calculator,
  Epidemiology: Bug,
  Diagnostic: Target,
  ClinicalTrials: ClipboardList,
  Survival: Activity,
  CountModels: Gauge,
  Pharma: FlaskConical,
  MetaAnalysis: Layers,
  HealthEconomics: Landmark,
  LifeSciences: Leaf,
  Hospital: Users2,
  Advanced: TrendingUp,
}

// ── Field renderer for the inline parameter form ────────────────────────
function InputField({ field, value, onChange, numericColumns, categoricalColumns, allColumns }) {
  const label = (
    <label style={{ display:'block', fontSize:'12px', fontWeight:600, color:'#6B6280', marginBottom:'6px' }}>
      {field.label}{field.required === false && <span style={{ color:'#A89FBC' }}> (optional)</span>}
    </label>
  )
  const inputStyle = {
    width:'100%', boxSizing:'border-box', padding:'9px 12px', fontSize:'13px',
    border: `1px solid ${BORDER}`, borderRadius:'8px', outline:'none',
  }

  if (['column_numeric', 'column_categorical', 'column_any'].includes(field.type)) {
    const options = field.type === 'column_numeric' ? numericColumns
      : field.type === 'column_categorical' ? categoricalColumns : allColumns
    return (
      <div style={{ marginBottom:'12px' }}>
        {label}
        <select style={inputStyle} value={value || ''} onChange={e => onChange(e.target.value)}>
          <option value="">{field.required === false ? 'None' : 'Select a column…'}</option>
          {(options || []).map(c => <option key={c} value={c}>{c}</option>)}
        </select>
      </div>
    )
  }
  if (field.type === 'column_list') {
    return (
      <div style={{ marginBottom:'12px' }}>
        {label}
        <input type="text" placeholder="e.g. Age, BMI, Systolic_BP" style={inputStyle}
          value={Array.isArray(value) ? value.join(', ') : (value || '')} onChange={e => onChange(e.target.value)} />
        {(numericColumns?.length > 0) && (
          <p style={{ fontSize:'11px', color:'#A89FBC', marginTop:'4px' }}>
            Numeric columns: {numericColumns.slice(0, 8).join(', ')}{numericColumns.length > 8 ? '…' : ''}
          </p>
        )}
      </div>
    )
  }
  if (field.type === 'number') {
    return (
      <div style={{ marginBottom:'12px' }}>
        {label}
        <input type="number" step="any" style={inputStyle} value={value ?? ''}
          onChange={e => onChange(e.target.value === '' ? '' : Number(e.target.value))} />
      </div>
    )
  }
  if (field.type === 'text') {
    return (
      <div style={{ marginBottom:'12px' }}>
        {label}
        <input type="text" style={inputStyle} value={value || ''} onChange={e => onChange(e.target.value)} />
      </div>
    )
  }
  if (field.type === 'number_array') {
    return (
      <div style={{ marginBottom:'12px' }}>
        {label}
        <input type="text" placeholder="e.g. 0.30, 0.45, 0.12"  style={inputStyle}
          value={Array.isArray(value) ? value.join(', ') : (value || '')} onChange={e => onChange(e.target.value)} />
        <p style={{ fontSize:'11px', color:'#A89FBC', marginTop:'4px' }}>Comma-separated numbers</p>
      </div>
    )
  }
  if (field.type === 'number_matrix') {
    return (
      <div style={{ marginBottom:'12px' }}>
        {label}
        <textarea rows={4} placeholder={'e.g.\n0.80, 0.15, 0.05\n0.00, 0.70, 0.30\n0.00, 0.00, 1.00'}
          style={{ ...inputStyle, fontFamily:'monospace', resize:'vertical' }}
          value={value || ''} onChange={e => onChange(e.target.value)} />
        <p style={{ fontSize:'11px', color:'#A89FBC', marginTop:'4px' }}>
          One row per line, comma-separated. Each row must sum to 1.
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
    if (raw === undefined || raw === '' || (Array.isArray(raw) && raw.length === 0)) continue
    switch (field.type) {
      case 'number':
        params[field.name] = Number(raw); break
      case 'number_array':
        params[field.name] = (Array.isArray(raw) ? raw : String(raw).split(',')).map(s => Number(String(s).trim())).filter(n => !isNaN(n)); break
      case 'column_list':
        params[field.name] = (Array.isArray(raw) ? raw : String(raw).split(',')).map(s => String(s).trim()).filter(Boolean); break
      case 'number_matrix':
        params[field.name] = String(raw).split('\n').map(l => l.trim()).filter(Boolean)
          .map(line => line.split(',').map(s => Number(s.trim()))); break
      default:
        params[field.name] = raw
    }
  }
  return params
}

const prettyKey = k => k.replace(/_/g, ' ')
const showVal = v => v === true ? 'Yes' : v === false ? 'No' : String(v)

// ── Result renderer: scalar tiles + text callouts + chart + generic tables ──
function ResultView({ result }) {
  if (!result) return null
  const chartKey = ['curve', 'histogram'].find(k => Array.isArray(result[k]) && result[k].length > 0)
  const scalars = Object.entries(result).filter(([k, v]) => v !== null && typeof v !== 'object' && k !== 'type')
  const tiles = scalars.filter(([, v]) => String(v).length <= 34)
  const notes = scalars.filter(([, v]) => String(v).length > 34)
  const tables = Object.entries(result).filter(([k, v]) =>
    k !== chartKey && Array.isArray(v) && v.length > 0 && v[0] !== null && typeof v[0] === 'object')

  const rows = chartKey ? result[chartKey] : []
  const keys = rows.length ? Object.keys(rows[0]) : []
  const isHist = chartKey === 'histogram'
  const xKey = keys[0]
  const numericX = rows.length > 0 && rows.every(r => typeof r[xKey] === 'number')
  const seriesKeys = keys.slice(1).filter(k => typeof rows[0][k] === 'number')
  const lineType = result.type === 'kaplan_meier_survival' ? 'stepAfter' : (result.type === 'roc_auc_analysis' ? 'linear' : 'monotone')

  return (
    <div style={{ marginTop:'16px' }}>
      {tiles.length > 0 && (
        <div style={{ display:'grid', gridTemplateColumns:'repeat(auto-fit, minmax(120px, 1fr))', gap:'10px', marginBottom:'14px' }}>
          {tiles.map(([k, v]) => (
            <div key={k} style={{ textAlign:'center', padding:'10px', borderRadius:'10px', background:'rgba(107,45,139,0.04)', border:`1px solid ${BORDER}` }}>
              <div style={{ fontSize:'15px', fontWeight:700, color:'#241B33', wordBreak:'break-word' }}>{showVal(v)}</div>
              <div style={{ fontSize:'10px', color:'#A89FBC', textTransform:'capitalize' }}>{prettyKey(k)}</div>
            </div>
          ))}
        </div>
      )}

      {notes.map(([k, v]) => (
        <div key={k} style={{
          marginBottom:'10px', padding:'9px 12px', borderRadius:'8px', fontSize:'12px', lineHeight:1.5,
          background:'rgba(107,45,139,0.05)', border:`1px solid ${BORDER}`, color:'#4B3F5E',
        }}>
          <strong style={{ textTransform:'capitalize', color: PURPLE }}>{prettyKey(k)}: </strong>{showVal(v)}
        </div>
      ))}

      {chartKey && seriesKeys.length > 0 && (
        <div style={{ marginBottom:'14px' }}>
          <p style={{ fontSize:'11px', fontWeight:700, color:'#A89FBC', textTransform:'uppercase', letterSpacing:'0.06em', marginBottom:'6px' }}>
            {isHist ? 'Distribution' : prettyKey(result.type || chartKey)}
          </p>
          <ResponsiveContainer width="100%" height={240}>
            {isHist ? (
              <BarChart data={rows}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(107,45,139,0.08)" />
                <XAxis dataKey={xKey} stroke="#A89FBC" fontSize={11} />
                <YAxis stroke="#A89FBC" fontSize={11} />
                <Tooltip contentStyle={{ background:'#fff', border:`1px solid ${BORDER}`, borderRadius:'8px', fontSize:'12px' }} />
                <Bar dataKey="count" fill={PURPLE} radius={[3, 3, 0, 0]} />
              </BarChart>
            ) : (
              <LineChart data={rows}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(107,45,139,0.08)" />
                <XAxis dataKey={xKey} stroke="#A89FBC" fontSize={11}
                  {...(numericX ? { type:'number', domain:['dataMin', 'dataMax'] } : {})} />
                <YAxis stroke="#A89FBC" fontSize={11} />
                <Tooltip contentStyle={{ background:'#fff', border:`1px solid ${BORDER}`, borderRadius:'8px', fontSize:'12px' }} />
                <Legend wrapperStyle={{ fontSize:'11px' }} />
                {seriesKeys.map((k, i) => (
                  <Line key={k} type={lineType} dataKey={k} stroke={SERIES_COLORS[i % SERIES_COLORS.length]}
                        dot={false} strokeWidth={2} connectNulls />
                ))}
              </LineChart>
            )}
          </ResponsiveContainer>
        </div>
      )}

      {tables.map(([k, arr]) => (
        <div key={k} style={{ marginBottom:'12px' }}>
          <p style={{ fontSize:'11px', fontWeight:700, color:'#A89FBC', textTransform:'uppercase', letterSpacing:'0.06em', marginBottom:'6px' }}>
            {prettyKey(k)}
          </p>
          <div style={{ overflowX:'auto' }}>
            <table style={{ width:'100%', fontSize:'12px', borderCollapse:'collapse' }}>
              <thead>
                <tr>{Object.keys(arr[0]).map(col => (
                  <th key={col} style={{ textAlign:'left', padding:'6px 8px', color:'#A89FBC', borderBottom:`1px solid ${BORDER}`, whiteSpace:'nowrap' }}>{prettyKey(col)}</th>
                ))}</tr>
              </thead>
              <tbody>
                {arr.slice(0, 25).map((row, i) => (
                  <tr key={i}>
                    {Object.values(row).map((v, j) => (
                      <td key={j} style={{ padding:'6px 8px', borderBottom:`1px solid ${BORDER}`, color:'#241B33' }}>
                        {v === null || v === undefined ? '—' : showVal(v)}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ))}

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
function SubTestRow({ item, fileId, fileName, sheetName, numericColumns, categoricalColumns, allColumns, autoOpen, initialValues, recommendedReason }) {
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
      if (item.needs_dataframe) {
        payload.file_id = Number(fileId)
        if (sheetName) payload.sheet_name = sheetName
      }
      const { data } = await api.post('/healthcare/run', payload)
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
          minWidth:'30px', height:'20px', borderRadius:'999px', background:'rgba(107,45,139,0.10)',
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
              {sheetName ? <span>· sheet <strong style={{ color:'#6B6280' }}>{sheetName}</strong></span> : null}
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
              allColumns={allColumns}
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
export default function HealthSuggestionsPanel({ fileId, file, sheetName }) {
  const [modules, setModules] = useState([])
  const [expanded, setExpanded] = useState(false)
  const [activeModuleKey, setActiveModuleKey] = useState(null)
  const [loading, setLoading] = useState(true)
  const [recommended, setRecommended] = useState([])
  const [suggestLoading, setSuggestLoading] = useState(true)
  const [highlight, setHighlight] = useState(null)

  useEffect(() => {
    api.get('/healthcare/catalog')
      .then(r => {
        setModules(r.data.modules || [])
        if (r.data.modules?.length) setActiveModuleKey(r.data.modules[0].module_key)
      })
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => {
    if (!fileId) { setSuggestLoading(false); return }
    const url = sheetName ? `/healthcare/suggest/${fileId}?sheet=${encodeURIComponent(sheetName)}` : `/healthcare/suggest/${fileId}`
    setSuggestLoading(true)
    api.get(url)
      .then(r => {
        const recs = r.data.recommended || []
        setRecommended(recs)
        setHighlight(null)
        if (recs.length > 0) setExpanded(true)
      })
      .catch(() => setRecommended([]))
      .finally(() => setSuggestLoading(false))
  }, [fileId, sheetName])

  // Resolve columns from whichever sheet is active — file.columns_meta only
  // reflects the PRIMARY (largest) sheet, which may not be the one in view.
  const activeColumnsMeta = useMemo(() => {
    const sheets = file?.sheets_meta || []
    if (sheetName && sheets.length > 1) {
      const match = sheets.find(s => s.name === sheetName)
      if (match?.columns) return match.columns
    }
    return file?.columns_meta || []
  }, [file, sheetName])

  const numericColumns = useMemo(
    () => activeColumnsMeta.filter(c => ['integer','float'].includes(c.python_type)).map(c => c.name),
    [activeColumnsMeta]
  )
  const categoricalColumns = useMemo(
    () => activeColumnsMeta.filter(c => c.python_type === 'string').map(c => c.name),
    [activeColumnsMeta]
  )
  const allColumns = useMemo(() => activeColumnsMeta.map(c => c.name), [activeColumnsMeta])

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
          <HeartPulse size={20} style={{ color: PURPLE }} />
        </div>
        <div style={{ flex:1, minWidth:0 }}>
          <div style={{ display:'flex', alignItems:'center', gap:'8px', flexWrap:'wrap' }}>
            <span style={{ fontWeight:700, color:'#241B33', fontSize:'14px' }}>
              {recommended.length > 0
                ? `${recommended.length} Health Test${recommended.length > 1 ? 's' : ''} Recommended For This File`
                : 'Health, Medical & Life Sciences Analytics Available'}
            </span>
            <span style={{
              fontSize:'10px', fontWeight:700, padding:'3px 9px', borderRadius:'999px',
              color: PURPLE, background:'rgba(107,45,139,0.10)',
            }}>
              {totalSubTests} Sub-Tests · {modules.length} Modules
            </span>
          </div>
          <p style={{ fontSize:'12px', color:'#6B6280', marginTop:'3px' }}>
            {recommended.length > 0
              ? 'Based on this sheet\'s columns, these tests are likely relevant — or browse all modules below.'
              : 'Biostatistics, epidemiology, diagnostics, clinical trials, survival, pharma, genetics, health economics and hospital analytics — some use this file\'s columns, others take manual inputs.'}
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
                    {React.createElement(MODULE_ICONS[rec.module_key] || HeartPulse, { size:15, style:{ color: PURPLE, flexShrink:0 } })}
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
              const Icon = MODULE_ICONS[mod.module_key] || HeartPulse
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
                  key={`${item.key}-${highlight?.itemKey === item.key ? 'rec' : 'std'}`}
                  item={item}
                  fileId={fileId}
                  fileName={file?.original_name}
                  sheetName={sheetName}
                  numericColumns={numericColumns}
                  categoricalColumns={categoricalColumns}
                  allColumns={allColumns}
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
