import React, { useCallback, useState } from 'react'
import { useDropzone } from 'react-dropzone'
import { useNavigate } from 'react-router-dom'
import api from '../utils/api'
import {
  Upload, FileSpreadsheet, CheckCircle2, AlertTriangle,
  Info, BarChart2, ArrowRight, X, RefreshCw, Layers
} from 'lucide-react'
import toast from 'react-hot-toast'

function safe(val) {
  if (val === null || val === undefined) return '—'
  if (typeof val === 'number') return val.toLocaleString()
  return String(val)
}

const STAT_COLOR_MAP = {
  'Identifier':      { color:'#A89FBC', bg:'rgba(168,159,188,0.12)' },
  'Nominal':         { color:'#6B2D8B', bg:'rgba(107,45,139,0.10)' },
  'Ordinal':         { color:'#8B5CF6', bg:'rgba(139,92,246,0.10)' },
  'Binary':          { color:'#D97706', bg:'rgba(217,119,6,0.10)'  },
  'Discrete':        { color:'#16A34A', bg:'rgba(22,163,74,0.10)'  },
  'Continuous':      { color:'#C8860B', bg:'rgba(200,134,11,0.10)' },
  'TimeSeries':      { color:'#0EA5E9', bg:'rgba(14,165,233,0.10)' },
  'Panel (Entity)':  { color:'#7C3AED', bg:'rgba(124,58,237,0.10)' },
  'Panel (Time)':    { color:'#7C3AED', bg:'rgba(124,58,237,0.10)' },
  'Panel (Measure)': { color:'#7C3AED', bg:'rgba(124,58,237,0.10)' },
}

const ORDINAL_KW = ['level','rating','rank','grade','satisfaction','performance',
                    'frequency','stage','priority','tier','category','class','scale',
                    'education','income_cat','income_category']
const TIME_KW    = ['month','date','week','quarter','period','time','month_year','year_month']
const BINARY_VALS = new Set(['yes','no','true','false','1','0','y','n',
                              'pass','fail','active','inactive','present','absent'])
const PANEL_KW   = ['state','country','region','district','province','city','entity']

function inferStatType(col, allCols) {
  const name      = (col.name || '').toLowerCase()
  const pyType    = col.python_type || col.dtype || ''
  const unique    = col.unique_values || 0
  const topVals   = col.top_values || []
  if (name.includes('_id') || name === 'id' || name === 'respondent_id')
    return { label:'Identifier', color:'#A89FBC', bg:'rgba(168,159,188,0.12)' }
  const hasYear   = allCols.some(c => ['year','yr'].includes((c.name||'').toLowerCase()))
  const hasEntity = allCols.some(c => PANEL_KW.some(k => (c.name||'').toLowerCase().includes(k)))
  if (hasEntity && hasYear) {
    if (name==='year'||name==='yr') return { label:'Panel (Time)',color:'#7C3AED',bg:'rgba(124,58,237,0.10)' }
    if (PANEL_KW.some(k=>name.includes(k))) return { label:'Panel (Entity)',color:'#7C3AED',bg:'rgba(124,58,237,0.10)' }
    if (pyType==='float'||pyType==='integer') return { label:'Panel (Measure)',color:'#7C3AED',bg:'rgba(124,58,237,0.10)' }
  }
  const isTimeCol = k => name === k || (name.startsWith(k) && name.length > k.length && ['_','-',' '].includes(name[k.length]))
  if (TIME_KW.some(isTimeCol)) return { label:'Time Series',color:'#0EA5E9',bg:'rgba(14,165,233,0.10)' }
  if (pyType==='string'||pyType==='object') {
    if (unique===2) {
      const tl = topVals.map(v=>String(v.value||v).toLowerCase())
      if (tl.length>=2 && tl.every(v=>BINARY_VALS.has(v)))
        return { label:'Binary',color:'#D97706',bg:'rgba(217,119,6,0.10)' }
    }
    if (ORDINAL_KW.some(k=>name.includes(k))) return { label:'Ordinal',color:'#8B5CF6',bg:'rgba(139,92,246,0.10)' }
    return { label:'Nominal',color:'#6B2D8B',bg:'rgba(107,45,139,0.10)' }
  }
  if (pyType==='boolean') return { label:'Binary',color:'#D97706',bg:'rgba(217,119,6,0.10)' }
  if (pyType==='integer') return name==='year'||name==='yr' ? { label:'Time Series',color:'#0EA5E9',bg:'rgba(14,165,233,0.10)' } : { label:'Discrete',color:'#16A34A',bg:'rgba(22,163,74,0.10)' }
  if (pyType==='float') return { label:'Continuous',color:'#C8860B',bg:'rgba(200,134,11,0.10)' }
  if (pyType==='datetime'||pyType==='date_string') return { label:'Time Series',color:'#0EA5E9',bg:'rgba(14,165,233,0.10)' }
  return { label:pyType||'Unknown',color:'#6B6280',bg:'rgba(107,98,128,0.10)' }
}

function getStatBadge(col, allCols) {
  if (col.stat_type) {
    const m = STAT_COLOR_MAP[col.stat_type] || { color:'#6B6280', bg:'rgba(107,98,128,0.10)' }
    return { label: col.stat_type, ...m }
  }
  return inferStatType(col, allCols)
}

// ── Column table for a given list of columns ──────────────────────────────
function ColumnTable({ columns }) {
  if (!columns || columns.length === 0) return null
  return (
    <div className="table-container">
      <table className="table">
        <thead>
          <tr><th>Column</th><th>Type</th><th>Unique</th><th>Missing %</th><th>Bar</th></tr>
        </thead>
        <tbody>
          {columns.slice(0, 30).map((col, i) => {
            const pct = Number(col.missing_pct) || 0
            const st  = getStatBadge(col, columns)
            return (
              <tr key={i}>
                <td style={{ color:'#241B33', fontWeight:500, maxWidth:'180px', overflow:'hidden', textOverflow:'ellipsis', whiteSpace:'nowrap' }}>{col.name}</td>
                <td>
                  <span style={{ display:'inline-flex', alignItems:'center', fontSize:'10px', fontWeight:700, padding:'3px 9px', borderRadius:'999px', color:st.color, background:st.bg, whiteSpace:'nowrap' }}>
                    {st.label}
                  </span>
                </td>
                <td style={{ fontFamily:'monospace', color:'#A89FBC' }}>{safe(col.unique_values)}</td>
                <td style={{ color: pct>30?'#DC2626':pct>0?'#D97706':'#16A34A' }}>{pct}%</td>
                <td style={{ width:'120px' }}>
                  <div className="progress-bar">
                    <div className="progress-fill" style={{ width:`${pct}%`, background:pct>30?'#DC2626':pct>0?'#D97706':'#16A34A' }} />
                  </div>
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
      {columns.length > 30 && (
        <p style={{ fontSize:'12px', color:'#A89FBC', padding:'8px 16px' }}>
          Showing 30 of {columns.length} columns
        </p>
      )}
    </div>
  )
}

export default function UploadPage() {
  const [uploading, setUploading]     = useState(false)
  const [progress,  setProgress]      = useState(0)
  const [result,    setResult]        = useState(null)
  const [error,     setError]         = useState(null)
  // activeSheet: index of the selected sheet tab (0-based)
  const [activeSheet, setActiveSheet] = useState(0)
  const navigate = useNavigate()

  const onDrop = useCallback(async (accepted, rejected) => {
    if (rejected?.length > 0) {
      const err = rejected[0]?.errors?.[0]
      if (err?.code==='file-too-large') toast.error('File too large. Max 50MB.')
      else if (err?.code==='file-invalid-type') toast.error('Unsupported file type.')
      else toast.error('File rejected.')
      return
    }
    if (!accepted?.length) return
    setError(null); setResult(null); setUploading(true); setProgress(0); setActiveSheet(0)
    const fd = new FormData()
    fd.append('file', accepted[0])
    try {
      const res = await api.post('/excel/upload', fd, {
        headers: { 'Content-Type': 'multipart/form-data' },
        onUploadProgress: e => { if (e.total) setProgress(Math.round((e.loaded/e.total)*100)) },
      })
      setResult(res.data.file)
      toast.success('File uploaded and analyzed!')
    } catch (err) {
      const msg = err.response?.data?.error || 'Upload failed'
      setError(msg)
      toast.error(err.response?.data?.upgrade_required ? msg + ' — Upgrade your plan.' : msg)
    } finally {
      setUploading(false)
    }
  }, [])

  const { getRootProps, getInputProps, isDragActive, isDragReject } = useDropzone({
    onDrop,
    accept: {
      'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': ['.xlsx'],
      'application/vnd.ms-excel': ['.xls'],
      'text/csv': ['.csv'],
      'application/vnd.ms-excel.sheet.macroEnabled.12': ['.xlsm'],
    },
    maxFiles: 1,
    maxSize: 50 * 1024 * 1024,
  })

  const reset = () => { setResult(null); setError(null); setProgress(0); setActiveSheet(0) }

  const boxStyle = {
    border: `2px dashed ${isDragActive&&!isDragReject?'#6B2D8B':isDragReject?'#DC2626':'rgba(107,45,139,0.18)'}`,
    borderRadius:'16px', padding:'48px 24px', textAlign:'center', cursor:'pointer', transition:'all 0.2s',
    background: isDragActive&&!isDragReject?'rgba(107,45,139,0.04)':isDragReject?'rgba(220,38,38,0.05)':'transparent',
  }

  // ── Derive the currently-selected sheet's column data ──────────────────
  const sheets     = result?.sheets_meta || []
  const multiSheet = sheets.length > 1

  const activeSheetMeta = multiSheet ? sheets[activeSheet] : null
  const activeSheetName = multiSheet ? (activeSheetMeta?.name || `Sheet ${activeSheet+1}`) : null
  const activeSheetRows = multiSheet ? (activeSheetMeta?.rows || 0) : result?.total_rows
  const activeSheetCols = multiSheet ? (activeSheetMeta?.cols || activeSheetMeta?.columns?.length || 0) : result?.total_cols

  // For multi-sheet: use that sheet's columns (with stat_type fallback via inferStatType)
  // For single-sheet: use result.columns_meta (already has stat_type from backend)
  const activeColsMeta = multiSheet
    ? (activeSheetMeta?.columns || [])
    : (result?.columns_meta || [])

  return (
    <div className="stagger" style={{ maxWidth:'800px', margin:'0 auto' }}>
      <div style={{ marginBottom:'24px' }}>
        <h1 style={{ fontSize:'1.25rem', fontWeight:700, color:'#241B33', margin:0 }}>Upload File</h1>
        <p style={{ fontSize:'14px', color:'#6B6280', marginTop:'4px' }}>Upload an Excel or CSV file for instant automated analysis</p>
      </div>

      {!result && (
        <div {...getRootProps()} style={boxStyle}>
          <input {...getInputProps()} />
          {uploading ? (
            <div>
              <RefreshCw size={32} style={{ color:'#6B2D8B', margin:'0 auto 16px', display:'block', animation:'spin 1s linear infinite' }} />
              <p style={{ color:'#241B33', fontWeight:600, marginBottom:'12px' }}>Uploading & analyzing…</p>
              <div style={{ maxWidth:'240px', margin:'0 auto' }}>
                <div className="progress-bar">
                  <div className="progress-fill" style={{ width:`${progress}%`, background:'#6B2D8B' }} />
                </div>
                <p style={{ fontSize:'12px', color:'#A89FBC', marginTop:'4px' }}>{progress}%</p>
              </div>
            </div>
          ) : (
            <div>
              <Upload size={32} style={{ color:isDragActive?'#6B2D8B':'#A89FBC', margin:'0 auto 16px', display:'block' }} />
              <p style={{ color:'#241B33', fontWeight:600, fontSize:'16px', marginBottom:'8px' }}>
                {isDragActive ? 'Drop it here!' : 'Drag & drop your file'}
              </p>
              <p style={{ color:'#6B6280', fontSize:'14px', marginBottom:'16px' }}>
                or <span style={{ color:'#6B2D8B' }}>browse files</span>
              </p>
              <div style={{ display:'flex', flexWrap:'wrap', justifyContent:'center', gap:'8px', marginBottom:'12px' }}>
                {['.xlsx','.xls','.csv','.xlsm'].map(ext => (
                  <span key={ext} className="info-chip" style={{ fontFamily:'monospace' }}>{ext}</span>
                ))}
              </div>
              <p style={{ fontSize:'12px', color:'#A89FBC' }}>Maximum file size: 50MB</p>
            </div>
          )}
        </div>
      )}

      {error && (
        <div className="card" style={{ padding:'16px', border:'1px solid rgba(220,38,38,0.25)', background:'rgba(220,38,38,0.05)', display:'flex', alignItems:'flex-start', gap:'12px', marginTop:'16px' }}>
          <AlertTriangle size={18} style={{ color:'#DC2626', flexShrink:0, marginTop:'2px' }} />
          <p style={{ fontSize:'14px', color:'#DC2626', flex:1 }}>{error}</p>
          <button onClick={reset} style={{ background:'none', border:'none', cursor:'pointer', color:'#A89FBC' }}><X size={16} /></button>
        </div>
      )}

      {result && (
        <div className="anim-fade-up" style={{ marginTop:'24px' }}>

          {/* Success banner */}
          <div className="card" style={{ padding:'16px', border:'1px solid rgba(22,163,74,0.15)', background:'rgba(22,163,74,0.05)', display:'flex', alignItems:'center', gap:'12px', marginBottom:'16px' }}>
            <CheckCircle2 size={22} style={{ color:'#16A34A', flexShrink:0 }} />
            <div style={{ flex:1 }}>
              <p style={{ fontWeight:600, color:'#241B33', fontSize:'14px' }}>{result.original_name || 'File uploaded'}</p>
              <p style={{ fontSize:'12px', color:'#6B6280', marginTop:'2px' }}>Analysis complete</p>
            </div>
            <button onClick={reset} className="btn btn-ghost btn-sm">
              <RefreshCw size={14} /> Upload another
            </button>
          </div>

          {/* Stats */}
          <div className="card" style={{ padding:'20px', display:'grid', gridTemplateColumns:'repeat(auto-fit,minmax(150px,1fr))', gap:'16px', marginBottom:'16px' }}>
            {[
              { label:'Total Rows',     value:safe(result.total_rows) },
              { label:'Total Columns',  value:safe(result.total_cols) },
              { label:'Total Cells',    value:safe(result.total_cells) },
              { label:'Sheets',         value:safe(result.sheet_count) },
              { label:'Missing Values', value:safe(result.missing_values), warn:result.missing_values>0 },
              { label:'Duplicate Rows', value:safe(result.duplicate_rows), warn:result.duplicate_rows>0 },
            ].map(m => (
              <div key={m.label}>
                <p style={{ fontSize:'11px', color:'#A89FBC', textTransform:'uppercase', letterSpacing:'0.05em', fontWeight:600 }}>{m.label}</p>
                <p style={{ fontSize:'1.25rem', fontWeight:700, marginTop:'2px', color:m.warn?'#D97706':'#241B33' }}>{m.value}</p>
              </div>
            ))}
          </div>

          {/* ── Sheet selector tabs (only for multi-sheet files) ── */}
          {multiSheet && (
            <div className="card" style={{ padding:'16px 20px', marginBottom:'16px' }}>
              <div style={{ display:'flex', alignItems:'center', gap:'8px', marginBottom:'12px' }}>
                <Layers size={15} style={{ color:'#6B2D8B' }} />
                <p style={{ fontSize:'12px', fontWeight:700, color:'#6B2D8B', textTransform:'uppercase', letterSpacing:'0.06em', margin:0 }}>
                  Select Sheet to View
                </p>
              </div>
              <div style={{ display:'flex', flexWrap:'wrap', gap:'8px' }}>
                {sheets.map((sheet, idx) => {
                  const isActive = activeSheet === idx
                  return (
                    <button
                      key={idx}
                      onClick={() => setActiveSheet(idx)}
                      style={{
                        display:'flex', alignItems:'center', gap:'6px',
                        padding:'8px 14px', borderRadius:'10px', cursor:'pointer',
                        border: isActive ? '1.5px solid #6B2D8B' : '1px solid rgba(107,45,139,0.15)',
                        background: isActive ? 'rgba(107,45,139,0.09)' : '#fff',
                        color: isActive ? '#6B2D8B' : '#6B6280',
                        fontSize:'12px', fontWeight: isActive ? 700 : 400,
                        transition:'all 0.15s',
                      }}
                    >
                      <span style={{
                        width:'20px', height:'20px', borderRadius:'6px', fontSize:'9px', fontWeight:700,
                        display:'flex', alignItems:'center', justifyContent:'center', flexShrink:0,
                        background: isActive ? '#6B2D8B' : 'rgba(107,45,139,0.08)',
                        color: isActive ? '#fff' : '#A89FBC',
                      }}>
                        {idx + 1}
                      </span>
                      {sheet.name || `Sheet ${idx+1}`}
                      <span style={{ fontSize:'10px', color: isActive ? 'rgba(107,45,139,0.6)' : '#A89FBC' }}>
                        {safe(sheet.rows)} rows
                      </span>
                    </button>
                  )
                })}
              </div>
            </div>
          )}

          {/* Column analysis — shows ONLY the selected sheet's columns */}
          <div className="card" style={{ padding:'20px', marginBottom:'16px' }}>
            <div style={{ display:'flex', alignItems:'center', justifyContent:'space-between', marginBottom:'12px' }}>
              <h3 className="section-title" style={{ margin:0 }}>
                Column Analysis
                {multiSheet && activeSheetName && (
                  <span style={{ fontWeight:400, color:'#6B6280', fontSize:'13px' }}> — {activeSheetName}</span>
                )}
                {' '}({activeColsMeta.length})
              </h3>
              {multiSheet && (
                <span style={{ fontSize:'11px', color:'#A89FBC' }}>
                  {safe(activeSheetRows)} rows × {safe(activeSheetCols)} cols
                </span>
              )}
            </div>
            <ColumnTable columns={activeColsMeta} />
          </div>

          {/* Warnings */}
          {result.file_insights?.warnings?.length > 0 && (
            <div className="card" style={{ padding:'20px', border:'1px solid rgba(217,119,6,0.15)', background:'rgba(217,119,6,0.05)', marginBottom:'16px' }}>
              <h3 style={{ color:'#D97706', display:'flex', alignItems:'center', gap:'8px', marginBottom:'12px', fontSize:'1rem', fontWeight:600 }}>
                <AlertTriangle size={16} /> Data Warnings ({result.file_insights.warnings.length})
              </h3>
              <ul style={{ margin:0, padding:0, listStyle:'none' }}>
                {result.file_insights.warnings.map((w,i) => (
                  <li key={i} style={{ fontSize:'14px', color:'#6B6280', marginBottom:'6px', display:'flex', gap:'8px' }}>
                    <span style={{ color:'#D97706' }}>•</span> {w}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Recommended analyses */}
          {result.recommended_analyses?.length > 0 && (
            <div className="card" style={{ padding:'20px', marginBottom:'16px' }}>
              <h3 style={{ display:'flex', alignItems:'center', gap:'8px', marginBottom:'8px', fontSize:'1rem', fontWeight:600, color:'#241B33' }}>
                <Info size={16} style={{ color:'#6B2D8B' }} /> Recommended Analyses
              </h3>
              <p style={{ fontSize:'14px', color:'#6B6280', marginBottom:'12px' }}>Based on your data structure:</p>
              <div style={{ display:'flex', flexWrap:'wrap', gap:'8px' }}>
                {result.recommended_analyses.map((a,i) => (
                  <span key={i} className="info-chip" style={{ color:'#6B2D8B' }}>✓ {String(a).replace(/_/g,' ')}</span>
                ))}
              </div>
            </div>
          )}

          {/* Analyse button */}
          <button
            onClick={() => {
              const sheetParam = multiSheet && activeSheetName
                ? `?sheet=${encodeURIComponent(activeSheetName)}`
                : ''
              navigate(`/analysis/${result.id}${sheetParam}`)
            }}
            className="btn btn-primary btn-lg" style={{ width:'100%' }}>
            <BarChart2 size={18} />
            Run Analysis{multiSheet && activeSheetName ? ` on "${activeSheetName}"` : ' on this File'}
            <ArrowRight size={16} />
          </button>
        </div>
      )}
      <style>{`@keyframes spin{from{transform:rotate(0deg)}to{transform:rotate(360deg)}}`}</style>
    </div>
  )
}