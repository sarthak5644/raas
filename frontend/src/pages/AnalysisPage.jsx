import React, { useEffect, useState } from 'react'
import { useParams, useNavigate, useLocation } from 'react-router-dom'
import api from '../utils/api'
import { FileSpreadsheet, RefreshCw, Layers, ArrowLeft } from 'lucide-react'
import toast from 'react-hot-toast'
import AdvancedAnalyticsPanel from '../components/AdvancedAnalyticsPanel'
import EngineeringSuggestionsPanel from '../components/EngineeringSuggestionsPanel'
import ManagementSuggestionsPanel from '../components/ManagementSuggestionsPanel'
import EnvironmentalSuggestionsPanel from '../components/EnvironmentalSuggestionsPanel'
import HealthSuggestionsPanel from '../components/HealthSuggestionsPanel'

const PURPLE = '#6B2D8B'
const BORDER = 'rgba(107,45,139,0.12)'

function safe(val) {
  if (val === null || val === undefined) return '—'
  if (typeof val === 'number') return val.toLocaleString()
  return String(val)
}

// ── Statistical-type colour map + resolver (same as Upload page) ──────────
const STAT_COLOR_MAP = {
  'Identifier':      { color:'#A89FBC', bg:'rgba(168,159,188,0.12)' },
  'Nominal':         { color:'#6B2D8B', bg:'rgba(107,45,139,0.10)' },
  'Ordinal':         { color:'#8B5CF6', bg:'rgba(139,92,246,0.10)' },
  'Binary':          { color:'#D97706', bg:'rgba(217,119,6,0.10)'  },
  'Discrete':        { color:'#16A34A', bg:'rgba(22,163,74,0.10)'  },
  'Continuous':      { color:'#C8860B', bg:'rgba(200,134,11,0.10)' },
  'TimeSeries':      { color:'#0EA5E9', bg:'rgba(14,165,233,0.10)' },
  'Time Series':     { color:'#0EA5E9', bg:'rgba(14,165,233,0.10)' },
  'Panel (Entity)':  { color:'#7C3AED', bg:'rgba(124,58,237,0.10)' },
  'Panel (Time)':    { color:'#7C3AED', bg:'rgba(124,58,237,0.10)' },
  'Panel (Measure)': { color:'#7C3AED', bg:'rgba(124,58,237,0.10)' },
}

const ORDINAL_KW  = ['level','rating','rank','grade','satisfaction','performance','frequency','stage','priority','tier','category','class','scale','education','income_cat','income_category']
const TIME_KW     = ['month','date','week','quarter','period','time','month_year','year_month']
const BINARY_VALS = new Set(['yes','no','true','false','1','0','y','n','pass','fail','active','inactive','present','absent'])
const PANEL_KW    = ['state','country','region','district','province','city','entity']

function inferStatType(col, allCols) {
  const name    = (col.name || '').toLowerCase()
  const pyType  = col.python_type || col.dtype || ''
  const unique  = col.unique_values || 0
  const topVals = col.top_values || []
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
      if (tl.length>=2 && tl.every(v=>BINARY_VALS.has(v))) return { label:'Binary',color:'#D97706',bg:'rgba(217,119,6,0.10)' }
    }
    if (ORDINAL_KW.some(k=>name.includes(k))) return { label:'Ordinal',color:'#8B5CF6',bg:'rgba(139,92,246,0.10)' }
    return { label:'Nominal',color:'#6B2D8B',bg:'rgba(107,45,139,0.10)' }
  }
  if (pyType==='boolean') return { label:'Binary',color:'#D97706',bg:'rgba(217,119,6,0.10)' }
  if (pyType==='integer') return (name==='year'||name==='yr') ? { label:'Time Series',color:'#0EA5E9',bg:'rgba(14,165,233,0.10)' } : { label:'Discrete',color:'#16A34A',bg:'rgba(22,163,74,0.10)' }
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

// ── Collapsible Column Analysis table ─────────────────────────────────────
function ColumnAnalysisTable({ columns }) {
  const [open, setOpen] = useState(false)
  if (!columns || columns.length === 0) return null
  return (
    <div className="card" style={{ marginBottom:'16px', overflow:'hidden' }}>
      <button
        onClick={() => setOpen(o => !o)}
        style={{
          width:'100%', display:'flex', alignItems:'center', justifyContent:'space-between',
          padding:'12px 16px', background:'none', border:'none', cursor:'pointer',
        }}
      >
        <span style={{ fontWeight:700, color:'#241B33', fontSize:'14px' }}>
          Column Analysis ({columns.length})
        </span>
        <span style={{ fontSize:'12px', color: PURPLE, fontWeight:600 }}>
          {open ? 'Hide ▲' : 'Show ▼'}
        </span>
      </button>
      {open && (
        <div style={{ overflowX:'auto' }}>
          <table className="table">
            <thead>
              <tr><th>Column</th><th>Type</th><th>Unique</th><th>Missing %</th><th>Bar</th></tr>
            </thead>
            <tbody>
              {columns.slice(0, 40).map((col, i) => {
                const pct = Number(col.missing_pct) || 0
                const st  = getStatBadge(col, columns)
                return (
                  <tr key={i}>
                    <td style={{ color:'#241B33', fontWeight:500, maxWidth:'200px', overflow:'hidden', textOverflow:'ellipsis', whiteSpace:'nowrap' }}>{col.name}</td>
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
          {columns.length > 40 && (
            <p style={{ fontSize:'12px', color:'#A89FBC', padding:'8px 16px' }}>
              Showing 40 of {columns.length} columns
            </p>
          )}
        </div>
      )}
    </div>
  )
}

export default function AnalysisPage() {
  const { fileId }  = useParams()
  const navigate    = useNavigate()
  const location    = useLocation()

  const [file, setFile]           = useState(null)
  const [fileLoading, setFileLoading] = useState(true)

  // Active sheet — read from URL ?sheet= initially, then controlled by tab clicks
  const urlSheet = new URLSearchParams(location.search).get('sheet') || null
  const [activeSheet, setActiveSheet] = useState(urlSheet)

  useEffect(() => {
    api.get(`/excel/files/${fileId}`)
      .then(r => {
        const f = r.data.file
        setFile(f)
        // If no sheet in URL, default to first sheet
        if (!urlSheet) {
          const sheets = f?.sheets_meta || []
          if (sheets.length > 0) setActiveSheet(sheets[0].name)
        }
        setFileLoading(false)
      })
      .catch(() => { toast.error('File not found'); navigate('/files') })
  }, [fileId])

  if (fileLoading) return (
    <div style={{ display:'flex', alignItems:'center', justifyContent:'center', height:'256px' }}>
      <RefreshCw size={24} style={{ color: PURPLE, animation:'spin 1s linear infinite' }} />
      <style>{`@keyframes spin{from{transform:rotate(0deg)}to{transform:rotate(360deg)}}`}</style>
    </div>
  )

  const sheets      = file?.sheets_meta || []
  const isMulti     = sheets.length > 1

  return (
    <div style={{ maxWidth:'1200px', margin:'0 auto' }}>

      {/* ── Back to Upload button ── */}
      <button
        onClick={() => navigate('/upload')}
        style={{
          display:'inline-flex', alignItems:'center', gap:'6px',
          background:'none', border:'none', cursor:'pointer',
          color: PURPLE, fontSize:'13px', fontWeight:600,
          padding:'6px 0', marginBottom:'12px',
        }}
      >
        <ArrowLeft size={16} /> Back to Upload
      </button>

      {/* ── File header ── */}
      <div className="card" style={{ padding:'14px 16px', display:'flex', alignItems:'center', gap:'12px', marginBottom:'16px' }}>
        <div style={{ width:'40px', height:'40px', borderRadius:'10px', background:'rgba(22,163,74,0.08)', display:'flex', alignItems:'center', justifyContent:'center', flexShrink:0 }}>
          <FileSpreadsheet size={20} style={{ color:'#16A34A' }} />
        </div>
        <div style={{ flex:1, minWidth:0 }}>
          <p style={{ fontWeight:600, color:'#241B33', fontSize:'14px', overflow:'hidden', textOverflow:'ellipsis', whiteSpace:'nowrap' }}>
            {file?.original_name || 'Unknown file'}
          </p>
          <div style={{ display:'flex', flexWrap:'wrap', gap:'8px 14px', marginTop:'2px', fontSize:'12px', color:'#A89FBC' }}>
            <span>{safe(file?.total_rows)} rows</span>
            <span>·</span>
            <span>{safe(file?.total_cols)} columns</span>
            {isMulti && (
              <>
                <span>·</span>
                <span style={{ color: PURPLE, fontWeight:600 }}>
                  <Layers size={11} style={{ verticalAlign:'middle', marginRight:3 }}/>
                  {sheets.length} sheets
                </span>
              </>
            )}
          </div>
        </div>
      </div>

      {/* ── Sheet selector tabs (only for multi-sheet files) ── */}
      {isMulti && (
        <div style={{ marginBottom:'16px' }}>
          <p style={{ fontSize:'11px', fontWeight:600, color:'#A89FBC', textTransform:'uppercase', letterSpacing:'0.08em', marginBottom:'8px' }}>
            Select Sheet to Analyse
          </p>
          <div style={{ display:'flex', flexWrap:'wrap', gap:'6px' }}>
            {sheets.map((sheet, idx) => {
              const isActive = activeSheet === sheet.name
              return (
                <button
                  key={sheet.name}
                  onClick={() => setActiveSheet(sheet.name)}
                  style={{
                    display:'flex', alignItems:'center', gap:'6px',
                    padding:'8px 14px', borderRadius:'10px',
                    border: isActive ? `1.5px solid ${PURPLE}` : `1px solid ${BORDER}`,
                    background: isActive ? 'rgba(107,45,139,0.09)' : '#fff',
                    color: isActive ? PURPLE : '#6B6280',
                    fontSize:'12px', fontWeight: isActive ? 700 : 400,
                    cursor:'pointer', transition:'all 0.15s', whiteSpace:'nowrap',
                  }}
                >
                  <span style={{
                    width:'20px', height:'20px', borderRadius:'6px',
                    background: isActive ? PURPLE : 'rgba(107,45,139,0.08)',
                    color: isActive ? '#fff' : '#A89FBC',
                    display:'flex', alignItems:'center', justifyContent:'center',
                    fontSize:'9px', fontWeight:700, flexShrink:0,
                  }}>
                    {idx + 1}
                  </span>
                  {sheet.name}
                  {sheet.rows > 0 && (
                    <span style={{ fontSize:'10px', color: isActive ? 'rgba(107,45,139,0.6)' : '#A89FBC' }}>
                      {sheet.rows.toLocaleString()} rows
                    </span>
                  )}
                </button>
              )
            })}
          </div>
        </div>
      )}

      {/* ── Column Analysis table (same look as Upload page) ── */}
      {(() => {
        // For multi-sheet: use the active sheet's columns; else the file's columns_meta
        let cols = file?.columns_meta || []
        if (isMulti) {
          const sm = sheets.find(s => s.name === activeSheet)
          cols = (sm?.columns || []).filter(c =>
            !String(c.name || '').toLowerCase().startsWith('unnamed'))
        }
        return <ColumnAnalysisTable columns={cols} />
      })()}

      {/* ── Analytics Panel — key forces full remount when sheet changes ── */}
      <AdvancedAnalyticsPanel
        key={`${fileId}-${activeSheet}`}
        fileId={fileId}
        file={file}
        sheetName={activeSheet}
      />

      {/* ── Engineering Analytics (RaaS Stage 2) — suggested as a secondary,
             also-available option for this uploaded file ── */}
      {file?.status === 'ready' && (
        <EngineeringSuggestionsPanel fileId={fileId} file={file} sheetName={activeSheet} />
      )}

      {/* ── Management & Business Analytics (RaaS Stage 2, Component 4) ── */}
      {file?.status === 'ready' && (
        <ManagementSuggestionsPanel fileId={fileId} file={file} sheetName={activeSheet} />
      )}

      {/* ── Environmental, Climate & Sustainability Analytics (RaaS Stage 2, Component 6) ── */}
      {file?.status === 'ready' && (
        <EnvironmentalSuggestionsPanel fileId={fileId} file={file} sheetName={activeSheet} />
      )}

      {/* ── Health, Medical, Pharmaceutical & Life Sciences Analytics (RaaS Stage 2, Component 3) ── */}
      {file?.status === 'ready' && (
        <HealthSuggestionsPanel fileId={fileId} file={file} sheetName={activeSheet} />
      )}

      <style>{`@keyframes spin{from{transform:rotate(0deg)}to{transform:rotate(360deg)}}`}</style>
    </div>
  )
}