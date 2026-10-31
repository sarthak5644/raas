import React, { useEffect, useState, useCallback, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import api from '../utils/api'
import useAuthStore from '../store/authStore'
import toast from 'react-hot-toast'
import {
  Calculator, ClipboardList, FlaskConical, GitBranch, Activity,
  Layers, BarChart3, Tag, ArrowUpDown, ToggleLeft, Hash, TrendingUp,
  LayoutGrid, Lock, RefreshCw, Play, CheckCircle2, AlertTriangle,
  Info, ChevronDown, ChevronRight, CheckSquare, Square, Sparkles,
  Download, FileSpreadsheet, Printer,
} from 'lucide-react'
import {
  BarChart, Bar, LineChart, Line, ScatterChart, Scatter,
  XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer,
} from 'recharts'

// ── Brand colors ──────────────────────────────────────────────────────────
const PURPLE  = '#6B2D8B'
const PURPLE2 = '#8B4DB0'
const GOLD    = '#C8860B'
const GREEN   = '#16A34A'
const RED     = '#DC2626'
const AMBER   = '#D97706'
const TEXT    = '#241B33'
const TEXT2   = '#6B6280'
const TEXT3   = '#A89FBC'
const BORDER  = 'rgba(107,45,139,0.10)'
const SURFACE = '#F7F2FB'

const TYPE_ICONS = {
  Nominal: Tag, Ordinal: ArrowUpDown, Binary: ToggleLeft,
  Continuous: TrendingUp, Discrete: Hash, TimeSeries: Activity,
  Panel: Layers, Mixed: LayoutGrid,
}

// ── Helpers ───────────────────────────────────────────────────────────────
function fmt(v, d = 4) {
  if (v === null || v === undefined) return '—'
  if (typeof v === 'number') {
    if (Number.isInteger(v)) return v.toLocaleString()
    return v.toLocaleString(undefined, { maximumFractionDigits: d })
  }
  return String(v)
}
function pColor(p) { return (!p && p !== 0) ? TEXT2 : p < 0.05 ? GREEN : AMBER }

const Tip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null
  return (
    <div style={{ background:'#fff', border:`1px solid ${BORDER}`, borderRadius:8, padding:'8px 12px', fontSize:12, boxShadow:'0 4px 12px rgba(107,45,139,0.10)' }}>
      <p style={{ color:TEXT2, margin:0, marginBottom:2 }}>{label}</p>
      {payload.map((p,i) => <p key={i} style={{ color:p.color||PURPLE, margin:'2px 0 0' }}>{p.name}: <strong>{typeof p.value==='number' ? p.value.toLocaleString() : p.value}</strong></p>)}
    </div>
  )
}

function StatCard({ label, value, color }) {
  return (
    <div style={{ padding:14, borderRadius:12, background:SURFACE, border:`1px solid ${BORDER}` }}>
      <p style={{ fontSize:11, color:TEXT3, textTransform:'uppercase', letterSpacing:'0.06em', margin:0 }}>{label}</p>
      <p style={{ fontSize:20, fontWeight:700, color:color||TEXT, margin:'6px 0 0' }}>{value}</p>
    </div>
  )
}
function Grid({ children }) {
  return <div style={{ display:'grid', gridTemplateColumns:'repeat(auto-fit,minmax(130px,1fr))', gap:12, marginBottom:16 }}>{children}</div>
}
function DTable({ columns, rows }) {
  if (!rows?.length) return <p style={{ textAlign:'center', padding:'24px 0', color:TEXT2, fontSize:13 }}>No data.</p>
  return (
    <div className="table-container">
      <table className="table">
        <thead><tr>{columns.map(c => <th key={c.key}>{c.label}</th>)}</tr></thead>
        <tbody>{rows.map((r,i) => <tr key={i}>{columns.map(c => <td key={c.key}>{c.render ? c.render(r[c.key],r) : fmt(r[c.key])}</td>)}</tr>)}</tbody>
      </table>
    </div>
  )
}
function ErrBox({ text }) {
  return (
    <div style={{ padding:'12px 14px', borderRadius:10, background:'rgba(220,38,38,0.05)', border:'1px solid rgba(220,38,38,0.15)', display:'flex', gap:8 }}>
      <AlertTriangle size={15} style={{ color:RED, flexShrink:0, marginTop:2 }} />
      <p style={{ fontSize:13, color:RED, margin:0 }}>{text}</p>
    </div>
  )
}
function Badge({ text, pValue }) {
  const sig = pValue !== null && pValue !== undefined && pValue < 0.05
  return <span className={sig ? 'badge-green' : 'badge-amber'} style={{ display:'inline-flex', alignItems:'center', gap:4 }}>{sig ? <CheckCircle2 size={11}/> : <Info size={11}/>} {text}</span>
}

// ── Result renderers ──────────────────────────────────────────────────────
function DescResult({ r }) {
  const rows = r.results || []
  if (!rows.length) return <p style={{ color:TEXT2, fontSize:13 }}>No numeric columns found.</p>
  return <DTable columns={['column','count','mean','median','mode','min','max','range','std_dev','coefficient_of_variation_pct','skewness','kurtosis'].map(k => ({
    key:k, label:k.replace(/_pct$/,' %').replace(/_/g,' ').replace(/\b\w/g,c=>c.toUpperCase())
  }))} rows={rows} />
}
function SummaryResult({ r }) {
  const num = r.numeric_summary || [], cat = r.categorical_summary || []
  return (
    <div>
      <Grid><StatCard label="Rows" value={fmt(r.row_count)}/><StatCard label="Columns" value={fmt(r.column_count)}/><StatCard label="Numeric" value={num.length}/><StatCard label="Categorical" value={cat.length}/></Grid>
      {num.length > 0 && <DTable columns={['column','count','mean','std','min','q25','median','q75','max','missing_values','unique_values'].map(k=>({key:k,label:k.replace(/_/g,' ')}))} rows={num}/>}
      {cat.map(c => (
        <div key={c.column} style={{ marginTop:16 }}>
          <p style={{ fontSize:13, fontWeight:600, color:TEXT, margin:'0 0 8px' }}>{c.column} — {c.unique_categories} categories</p>
          <DTable columns={[{key:'value',label:'Value'},{key:'count',label:'Count'},{key:'percentage',label:'%',render:v=>`${fmt(v,1)}%`}]} rows={c.frequency_table||[]}/>
        </div>
      ))}
    </div>
  )
}
function HypResult({ r }) {
  const statKey = r.t_statistic !== undefined ? 't_statistic' : r.f_statistic !== undefined ? 'f_statistic' : r.chi_square_statistic !== undefined ? 'chi_square_statistic' : null
  const statLabel = statKey === 't_statistic' ? 't-statistic' : statKey === 'f_statistic' ? 'F-statistic' : 'χ² statistic'
  return (
    <div>
      {r.test && <p style={{ fontSize:13, color:TEXT2, marginBottom:12 }}>{r.test}</p>}
      <Grid>
        {statKey && <StatCard label={statLabel} value={fmt(r[statKey])}/>}
        <StatCard label="p-value" value={fmt(r.p_value,6)} color={pColor(r.p_value)}/>
        {r.sample_size !== undefined && <StatCard label="n" value={r.sample_size}/>}
        {r.degrees_of_freedom !== undefined && <StatCard label="df" value={r.degrees_of_freedom}/>}
      </Grid>
      {r.interpretation && <Badge text={r.interpretation} pValue={r.p_value}/>}
      {r.type === 'anova' && r.groups && (
        <div style={{ marginTop:14 }}><DTable columns={['group','n','mean','std'].map(k=>({key:k,label:k}))} rows={r.groups}/></div>
      )}
      {r.type === 'chi_square' && r.observed_table && (
        <div style={{ marginTop:14 }}>
          <div className="table-container">
            <table className="table">
              <thead><tr><th></th>{r.observed_table.columns.map(c=><th key={c}>{c}</th>)}</tr></thead>
              <tbody>{r.observed_table.index.map((idx,i)=><tr key={idx}><td style={{fontWeight:600,color:TEXT}}>{idx}</td>{r.observed_table.values[i].map((v,j)=><td key={j}>{fmt(v,1)}</td>)}</tr>)}</tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}
function RegResult({ r }) {
  const coefs = r.coefficients || []
  const hasOdds = coefs[0]?.odds_ratio !== undefined
  return (
    <div>
      <Grid>
        {r.observations !== undefined && <StatCard label="N" value={fmt(r.observations)}/>}
        {r.r_squared !== undefined && <StatCard label="R²" value={fmt(r.r_squared)}/>}
        {r.adj_r_squared !== undefined && <StatCard label="Adj R²" value={fmt(r.adj_r_squared)}/>}
        {r.pseudo_r_squared !== undefined && <StatCard label="Pseudo R²" value={fmt(r.pseudo_r_squared)}/>}
        {r.f_pvalue !== undefined && <StatCard label="F p-val" value={fmt(r.f_pvalue,6)} color={pColor(r.f_pvalue)}/>}
      </Grid>
      {r.equation && <p style={{ fontFamily:'monospace', fontSize:12, background:SURFACE, padding:'10px 14px', borderRadius:10, marginBottom:14, overflowX:'auto', whiteSpace:'nowrap', color:TEXT }}>{r.equation}</p>}
      {r.results_by_quantile ? (
        r.results_by_quantile.map(q => (
          <div key={q.quantile} style={{ marginBottom:16 }}>
            <p style={{ fontSize:13, fontWeight:600, color:TEXT, margin:'0 0 8px' }}>Quantile τ = {q.quantile}</p>
            {q.error ? <ErrBox text={q.error}/> : <DTable columns={[{key:'variable',label:'Variable'},{key:'coefficient',label:'Coefficient'}]} rows={q.coefficients||[]}/>}
          </div>
        ))
      ) : (
        <DTable columns={[
          {key:'variable',label:'Variable'},
          {key:'coefficient',label:'Coefficient'},
          ...(hasOdds ? [{key:'odds_ratio',label:'Odds Ratio'}] : []),
          {key:'std_error',label:'Std Err'},
          {key:'p_value',label:'p-value',render:v=>v===undefined?'—':<span style={{color:pColor(v)}}>{fmt(v,6)}</span>},
        ]} rows={coefs}/>
      )}
    </div>
  )
}
function TSResult({ r }) {
  if (r.type === 'moving_average') return (
    <div>
      <p style={{ fontSize:13, color:TEXT2, marginBottom:12 }}>{r.points} points · window={r.window}</p>
      <ResponsiveContainer width="100%" height={240}>
        <LineChart data={r.series}><CartesianGrid strokeDasharray="3 3" stroke={BORDER}/><XAxis dataKey="date" tick={{fontSize:10,fill:TEXT3}}/><YAxis tick={{fontSize:10,fill:TEXT3}}/><Tooltip content={<Tip/>}/><Legend wrapperStyle={{fontSize:12}}/><Line type="monotone" dataKey="value" stroke={PURPLE2} dot={false} name={r.value_col}/><Line type="monotone" dataKey="moving_average" stroke={GOLD} dot={false} strokeWidth={2} name={`MA(${r.window})`}/></LineChart>
      </ResponsiveContainer>
    </div>
  )
  if (r.type === 'time_series_adf') return (
    <div>
      <Grid><StatCard label="ADF stat" value={fmt(r.adf_statistic)}/><StatCard label="p-value" value={fmt(r.p_value,6)} color={pColor(r.p_value)}/><StatCard label="Lags" value={r.lags_used}/><StatCard label="n" value={r.observations}/></Grid>
      <Badge text={r.interpretation} pValue={r.p_value}/>
      <div style={{ marginTop:14 }}><DTable columns={[{key:'level',label:'Significance'},{key:'value',label:'Critical Value'}]} rows={Object.entries(r.critical_values||{}).map(([level,value])=>({level,value}))}/></div>
    </div>
  )
  if (r.type === 'time_series_arima') return (
    <div>
      <Grid><StatCard label="Order" value={`(${r.order?.join(',')})`}/><StatCard label="AIC" value={fmt(r.aic)}/><StatCard label="BIC" value={fmt(r.bic)}/></Grid>
      <ResponsiveContainer width="100%" height={200}><LineChart data={r.forecast}><CartesianGrid strokeDasharray="3 3" stroke={BORDER}/><XAxis dataKey="date" tick={{fontSize:10,fill:TEXT3}}/><YAxis tick={{fontSize:10,fill:TEXT3}}/><Tooltip content={<Tip/>}/><Line type="monotone" dataKey="forecast" stroke={PURPLE} strokeWidth={2} dot={{r:3}} name="Forecast"/></LineChart></ResponsiveContainer>
      <div style={{ marginTop:12 }}><DTable columns={[{key:'date',label:'Date'},{key:'forecast',label:'Forecast'}]} rows={r.forecast||[]}/></div>
    </div>
  )
  if (r.type === 'seasonal_decomposition') {
    return <div>{[{key:'trend',label:'Trend',color:PURPLE},{key:'seasonal',label:'Seasonal',color:GOLD},{key:'residual',label:'Residual',color:PURPLE2}].map(p => (
      <div key={p.key} style={{ marginBottom:20 }}>
        <p style={{ fontSize:13, fontWeight:600, color:TEXT, marginBottom:8 }}>{p.label}</p>
        <ResponsiveContainer width="100%" height={130}><LineChart data={r[p.key]}><CartesianGrid strokeDasharray="3 3" stroke={BORDER}/><XAxis dataKey="date" tick={{fontSize:9,fill:TEXT3}}/><YAxis tick={{fontSize:9,fill:TEXT3}}/><Tooltip content={<Tip/>}/><Line type="monotone" dataKey="value" stroke={p.color} dot={false} strokeWidth={2}/></LineChart></ResponsiveContainer>
      </div>
    ))}</div>
  }
  return <pre style={{ fontSize:11, overflow:'auto' }}>{JSON.stringify(r,null,2)}</pre>
}
function PanelResult({ r }) {
  return (
    <div>
      <Grid><StatCard label="Model" value={r.model}/><StatCard label="n" value={fmt(r.observations)}/>{r.r_squared!=null&&<StatCard label="R²" value={fmt(r.r_squared)}/>}</Grid>
      <DTable columns={[{key:'variable',label:'Variable'},{key:'coefficient',label:'Coefficient'},{key:'p_value',label:'p-value',render:v=>v===undefined?'—':<span style={{color:pColor(v)}}>{fmt(v,6)}</span>}]} rows={r.coefficients||[]}/>
    </div>
  )
}
function VizResult({ r }) {
  if (r.type === 'histogram') return <ResponsiveContainer width="100%" height={260}><BarChart data={r.data}><CartesianGrid strokeDasharray="3 3" stroke={BORDER}/><XAxis dataKey="bin" tick={{fontSize:9,fill:TEXT3}} angle={-30} textAnchor="end" height={60}/><YAxis tick={{fontSize:10,fill:TEXT3}}/><Tooltip content={<Tip/>}/><Bar dataKey="count" fill={PURPLE} radius={[4,4,0,0]}/></BarChart></ResponsiveContainer>
  if (r.type === 'bar_chart') return <ResponsiveContainer width="100%" height={260}><BarChart data={r.data}><CartesianGrid strokeDasharray="3 3" stroke={BORDER}/><XAxis dataKey="category" tick={{fontSize:10,fill:TEXT3}} angle={-30} textAnchor="end" height={60}/><YAxis tick={{fontSize:10,fill:TEXT3}}/><Tooltip content={<Tip/>}/><Bar dataKey="count" fill={GOLD} radius={[4,4,0,0]}/></BarChart></ResponsiveContainer>
  if (r.type === 'line_chart') return <ResponsiveContainer width="100%" height={260}><LineChart data={r.data}><CartesianGrid strokeDasharray="3 3" stroke={BORDER}/><XAxis dataKey="date" tick={{fontSize:10,fill:TEXT3}}/><YAxis tick={{fontSize:10,fill:TEXT3}}/><Tooltip content={<Tip/>}/><Line type="monotone" dataKey="value" stroke={PURPLE} dot={false} strokeWidth={2}/></LineChart></ResponsiveContainer>
  if (r.type === 'scatter') return (
    <div>
      <p style={{ fontSize:13, color:TEXT2, marginBottom:10 }}>Correlation (r) = <strong style={{ color:TEXT }}>{fmt(r.correlation)}</strong></p>
      <ResponsiveContainer width="100%" height={280}><ScatterChart><CartesianGrid strokeDasharray="3 3" stroke={BORDER}/><XAxis dataKey="x" name={r.x_col} tick={{fontSize:10,fill:TEXT3}}/><YAxis dataKey="y" name={r.y_col} tick={{fontSize:10,fill:TEXT3}}/><Tooltip content={<Tip/>}/><Scatter data={r.points} fill={PURPLE} fillOpacity={0.6}/></ScatterChart></ResponsiveContainer>
    </div>
  )
  if (r.type === 'boxplot') {
    const { min, q1, median, q3, max, outliers, outliers_count } = r
    const lo = Math.min(min, ...(outliers||[])), hi = Math.max(max, ...(outliers||[]))
    const range = (hi-lo)||1, sc = v => 20+((v-lo)/range)*360
    return (
      <div>
        <svg viewBox="0 0 400 110" style={{ width:'100%', height:150 }}>
          <line x1={sc(min)} y1={55} x2={sc(q1)} y2={55} stroke={TEXT2} strokeWidth={2}/>
          <line x1={sc(q3)} y1={55} x2={sc(max)} y2={55} stroke={TEXT2} strokeWidth={2}/>
          <line x1={sc(min)} y1={42} x2={sc(min)} y2={68} stroke={TEXT2} strokeWidth={2}/>
          <line x1={sc(max)} y1={42} x2={sc(max)} y2={68} stroke={TEXT2} strokeWidth={2}/>
          <rect x={sc(q1)} y={32} width={Math.max(sc(q3)-sc(q1),1)} height={46} fill="rgba(107,45,139,0.12)" stroke={PURPLE} strokeWidth={2} rx={4}/>
          <line x1={sc(median)} y1={32} x2={sc(median)} y2={78} stroke={PURPLE} strokeWidth={3}/>
          {(outliers||[]).map((o,i)=><circle key={i} cx={sc(o)} cy={55} r={3} fill={RED} opacity={0.7}/>)}
          <text x={sc(min)} y={98} fontSize="11" fill={TEXT3} textAnchor="middle">{fmt(min,1)}</text>
          <text x={sc(median)} y={20} fontSize="11" fill={PURPLE} fontWeight="700" textAnchor="middle">{fmt(median,1)}</text>
          <text x={sc(max)} y={98} fontSize="11" fill={TEXT3} textAnchor="middle">{fmt(max,1)}</text>
        </svg>
        <Grid><StatCard label="Min" value={fmt(min)}/><StatCard label="Q1" value={fmt(q1)}/><StatCard label="Median" value={fmt(median)}/><StatCard label="Q3" value={fmt(q3)}/><StatCard label="Max" value={fmt(max)}/><StatCard label="Outliers" value={outliers_count} color={outliers_count>0?AMBER:GREEN}/></Grid>
      </div>
    )
  }
  if (r.type === 'correlation_heatmap') {
    const colorFor = v => { const abs=Math.abs(v); return v>=0?`rgba(107,45,139,${(0.06+abs*0.7).toFixed(2)})`:`rgba(220,38,38,${(0.06+abs*0.7).toFixed(2)})` }
    return (
      <div className="table-container">
        <table className="table"><thead><tr><th></th>{r.columns.map(c=><th key={c} style={{fontSize:10}}>{c}</th>)}</tr></thead>
        <tbody>{r.columns.map((row,i)=><tr key={row}><td style={{fontWeight:600,fontSize:11,color:TEXT}}>{row}</td>{r.matrix[i].map((v,j)=><td key={j} style={{background:colorFor(v),textAlign:'center',fontSize:11,color:Math.abs(v)>0.5?'#fff':TEXT,fontWeight:i===j?700:400}}>{fmt(v,2)}</td>)}</tr>)}</tbody></table>
      </div>
    )
  }
  return <pre style={{ fontSize:11, overflow:'auto' }}>{JSON.stringify(r,null,2)}</pre>
}

function ResultRenderer({ result }) {
  if (!result) return null
  if (result.error) return <ErrBox text={result.error}/>
  switch (result.category) {
    case 'Descriptive Statistics': return result.type === 'descriptive_statistics' ? <DescResult r={result}/> : <SummaryResult r={result}/>
    case 'Summary Statistics': return <SummaryResult r={result}/>
    case 'Hypothesis Testing': return <HypResult r={result}/>
    case 'Regression Analysis': return <RegResult r={result}/>
    case 'Time Series Analysis': return <TSResult r={result}/>
    case 'Panel Data Analysis': return <PanelResult r={result}/>
    case 'Data Visualization': return <VizResult r={result}/>
    default: return <SummaryResult r={result}/>
  }
}

// ── Mini param form ───────────────────────────────────────────────────────
function MiniParamForm({ paramDefs, params, onChange, numericCols, categoricalCols, dateCols, allCols }) {
  if (!paramDefs?.length) return null
  function getOpts(type) {
    if (type === 'numeric_column' || type === 'numeric_column_multi') return numericCols
    if (type === 'categorical_column') return categoricalCols
    if (type === 'date_column') return dateCols
    return allCols
  }
  return (
    <div style={{ display:'grid', gridTemplateColumns:'repeat(auto-fit,minmax(min(100%,170px),1fr))', gap:10, marginTop:10, padding:'12px', background:SURFACE, borderRadius:10, border:`1px solid ${BORDER}` }}>
      {paramDefs.filter(p => p.type !== 'numeric_column_multi' && p.type !== 'any_column_multi').map(p => (
        <div key={p.name}>
          <label style={{ fontSize:11, fontWeight:600, color:TEXT2, display:'block', marginBottom:4 }}>{p.label}{p.required&&<span style={{color:RED}}>*</span>}</label>
          {p.type === 'number' ? (
            <input className="input" type="number" style={{fontSize:12,padding:'6px 10px'}} value={params[p.name]??''} onChange={e=>onChange(p.name,e.target.value)} placeholder={String(p.default??'')}/>
          ) : p.type === 'group_value' ? (
            <input className="input" type="text" style={{fontSize:12,padding:'6px 10px'}} value={params[p.name]??''} onChange={e=>onChange(p.name,e.target.value)} placeholder="auto-detect"/>
          ) : (
            <select className="input" style={{fontSize:12,padding:'6px 10px'}} value={params[p.name]??''} onChange={e=>onChange(p.name,e.target.value)}>
              {getOpts(p.type).length === 0 && <option value="">No columns</option>}
              {getOpts(p.type).map(c=><option key={c} value={c}>{c}</option>)}
            </select>
          )}
        </div>
      ))}
      {paramDefs.filter(p=>p.type==='numeric_column_multi'||p.type==='any_column_multi').map(p => {
        const opts = getOpts(p.type), sel = params[p.name]||[]
        return (
          <div key={p.name} style={{ gridColumn:'1/-1' }}>
            <label style={{ fontSize:11, fontWeight:600, color:TEXT2, display:'block', marginBottom:4 }}>{p.label}{p.required&&<span style={{color:RED}}>*</span>}</label>
            <div style={{ display:'flex', flexWrap:'wrap', gap:6 }}>
              {opts.map(c => {
                const chk = sel.includes(c)
                return (
                  <label key={c} style={{ display:'inline-flex', alignItems:'center', gap:5, fontSize:12, cursor:'pointer', padding:'4px 10px', borderRadius:8, background:chk?'rgba(107,45,139,0.10)':'transparent', border:`1px solid ${chk?PURPLE:BORDER}`, color:chk?PURPLE:TEXT2, fontWeight:chk?600:400 }}>
                    <input type="checkbox" checked={chk} style={{accentColor:PURPLE}} onChange={()=>onChange(p.name, chk?sel.filter(x=>x!==c):[...sel,c])}/>
                    {c}
                  </label>
                )
              })}
            </div>
          </div>
        )
      })}
    </div>
  )
}

// ── Download helpers — server-side PDF & Excel ────────────────────────────

async function dlServerReport(fmt, entries, fileName, dataType) {
  // entries: [{label, number, result}]
  const validEntries = entries.filter(e => e.result && !e.result.error)
  if (!validEntries.length) { toast.error('No completed results to export.'); return }
  try {
    const res = await fetch('/api/universal/download-report', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${localStorage.getItem('access_token') || ''}`
      },
      body: JSON.stringify({ format: fmt, file_name: fileName || 'analysis', data_type: dataType || '', results: validEntries })
    })
    if (!res.ok) { const e = await res.json(); toast.error(e.error || 'Download failed'); return }
    const blob = await res.blob()
    const url  = URL.createObjectURL(blob)
    const a    = document.createElement('a')
    const ext  = fmt === 'pdf' ? 'pdf' : 'xlsx'
    a.href     = url
    a.download = `RaaS_${(fileName||'report').replace(/\.[^.]+$/,'').replace(/[^a-z0-9_]+/gi,'_')}.${ext}`
    a.click()
    URL.revokeObjectURL(url)
    toast.success(`Report downloaded as ${ext.toUpperCase()}!`)
  } catch (err) {
    toast.error('Download failed: ' + err.message)
  }
}

function printResult(label, el) {
  if (!el) return
  const w = window.open('','_blank')
  w.document.write(`<html><head><title>${label}</title><style>
    body{font-family:Arial,sans-serif;padding:24px;color:#241B33;font-size:13px}
    h2{color:#6B2D8B;border-bottom:2px solid #6B2D8B;padding-bottom:6px}
    table{border-collapse:collapse;width:100%;margin-top:12px}
    td,th{border:1px solid #D0C8E0;padding:7px 10px;font-size:12px}
    th{background:#6B2D8B;color:white;font-weight:600}
    tr:nth-child(even){background:#F7F2FB}
    @media print{button{display:none}}
  </style></head><body>
    <h2>${label}</h2>
    ${el.innerHTML}
    <hr style="margin-top:32px;border-color:#D0C8E0"/>
    <p style="font-size:10px;color:#A89FBC;text-align:center">Generated by RaaS — VP Research Company</p>
  </body></html>`)
  w.document.close(); w.print()
}

// ── Single sub-test row ───────────────────────────────────────────────────
function SubTestRow({ item, isChecked, onToggle, isExpanded, onExpand,
  params, onParamChange, paramDefs,
  numericCols, categoricalCols, dateCols, allCols,
  result, loading, onRun, canRun, fileName, dataType, notRecommended }) {

  const resultRef = useRef(null)
  const done = !!result && !result?.error
  const hasErr = !!result?.error
  const needsParams = paramDefs?.some(p => p.required)

  return (
    <div style={{
      borderRadius:10,
      border:`1px solid ${isChecked ? 'rgba(107,45,139,0.22)' : BORDER}`,
      marginBottom:5,
      background: isChecked ? 'rgba(107,45,139,0.025)' : '#fff',
      overflow:'hidden',
      transition:'border-color 0.15s, background 0.15s',
    }}>
      {/* Row header */}
      <div style={{ display:'flex', alignItems:'center', gap:8, padding:'10px 14px', flexWrap:'wrap' }}>
        {/* Number badge */}
        {item.number && (
          <span style={{ fontSize:10, fontWeight:700, color:PURPLE, background:'rgba(107,45,139,0.10)', borderRadius:6, padding:'2px 7px', flexShrink:0, minWidth:34, textAlign:'center' }}>
            {item.number}
          </span>
        )}

        {/* Checkbox */}
        <button onClick={onToggle} style={{ background:'none', border:'none', cursor:'pointer', padding:0, flexShrink:0 }}>
          {isChecked ? <CheckSquare size={17} style={{color:PURPLE}}/> : <Square size={17} style={{color:TEXT3}}/>}
        </button>

        {/* Label */}
        <span style={{ flex:1, minWidth:'100px', fontSize:13, fontWeight:isChecked?600:400, color:isChecked?TEXT:TEXT2 }}>
          {item.label}
          {notRecommended && (
            <span title="Not ideal for this data type" style={{ marginLeft:8, fontSize:9, fontWeight:700, color:'#D97706', background:'rgba(217,119,6,0.10)', borderRadius:6, padding:'2px 6px', whiteSpace:'nowrap' }}>
              not ideal
            </span>
          )}
        </span>

        {/* Status + controls */}
        <div style={{ display:'flex', alignItems:'center', gap:5, flexShrink:0 }}>
          {done && <CheckCircle2 size={12} style={{color:GREEN}}/>}
          {hasErr && <AlertTriangle size={12} style={{color:RED}}/>}

          {/* Individual download buttons — PDF, Excel, Print */}
          {done && (
            <>
              <button
                onClick={()=>dlServerReport('pdf',[{label:item.label,number:item.number||'',result}],fileName,dataType)}
                title="Download this result as PDF"
                style={{display:'flex',alignItems:'center',gap:3,padding:'3px 8px',borderRadius:6,border:`1px solid rgba(107,45,139,0.25)`,background:'rgba(107,45,139,0.06)',color:PURPLE,fontSize:10,fontWeight:700,cursor:'pointer',whiteSpace:'nowrap'}}>
                PDF
              </button>
              <button
                onClick={()=>dlServerReport('excel',[{label:item.label,number:item.number||'',result}],fileName,dataType)}
                title="Download this result as Excel"
                style={{display:'flex',alignItems:'center',gap:3,padding:'3px 8px',borderRadius:6,border:`1px solid rgba(22,163,74,0.3)`,background:'rgba(22,163,74,0.06)',color:'#16A34A',fontSize:10,fontWeight:700,cursor:'pointer',whiteSpace:'nowrap'}}>
                Excel
              </button>
              <button
                onClick={()=>printResult(item.label,resultRef.current)}
                title="Print this result"
                style={{display:'flex',alignItems:'center',gap:3,padding:'3px 8px',borderRadius:6,border:`1px solid ${BORDER}`,background:'#fff',color:TEXT2,fontSize:10,fontWeight:600,cursor:'pointer'}}>
                <Printer size={10}/>
              </button>
            </>
          )}

          {/* Expand */}
          {(needsParams || result) && (
            <button onClick={onExpand} style={{background:'none',border:'none',cursor:'pointer',padding:'2px',color:TEXT3}}>
              {isExpanded ? <ChevronDown size={13}/> : <ChevronRight size={13}/>}
            </button>
          )}

          {/* Run button */}
          {isChecked && canRun && (
            <button onClick={onRun} disabled={loading}
              style={{display:'flex',alignItems:'center',gap:3,padding:'6px 12px',borderRadius:8,border:'none',cursor:loading?'wait':'pointer',background:PURPLE,color:'#fff',fontSize:12,fontWeight:600,whiteSpace:'nowrap'}}>
              {loading ? <RefreshCw size={11} style={{animation:'spin 1s linear infinite'}}/> : <Play size={11}/>}
              {loading ? 'Running…' : 'Run'}
            </button>
          )}
        </div>
      </div>

      {/* Expanded: params form + result */}
      {isExpanded && (
        <div style={{ padding:'0 14px 14px', borderTop:`1px solid ${BORDER}` }}>
          {needsParams && isChecked && (
            <MiniParamForm paramDefs={paramDefs} params={params} onChange={onParamChange}
              numericCols={numericCols} categoricalCols={categoricalCols} dateCols={dateCols} allCols={allCols}/>
          )}
          {result && (
            <div style={{ marginTop:12 }} ref={resultRef}>
              <ResultRenderer result={result}/>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

// ── Download all — handled via dlServerReport in the banner ──────────────
// (No client-side downloadAll needed; server generates proper PDF/Excel)

// ── Main Panel ────────────────────────────────────────────────────────────
export default function AdvancedAnalyticsPanel({ fileId, file, sheetName }) {
  const { user, updateUser } = useAuthStore()

  const [smartData,    setSmartData]    = useState(null)   // from /smart-catalog
  const [fullCatalog,  setFullCatalog]  = useState(null)   // from /catalog (param defs)
  const [pageLoading,  setPageLoading]  = useState(true)

  // checked: Set of item.key strings
  const [checked, setChecked] = useState(new Set())
  // expanded: Set of item.key strings  
  const [expanded, setExpanded] = useState(new Set())
  // params: { [key]: { paramName: value } }
  const [params, setParams] = useState({})
  // results: { [key]: resultObj }
  const [results, setResults] = useState({})
  // loading: Set of keys currently running
  const [loadingSet, setLoadingSet] = useState(new Set())
  const [runAllLoading, setRunAllLoading] = useState(false)

  useEffect(() => {
    // Reset all state when sheet changes so old results don't bleed through
    setSmartData(null)
    setChecked(new Set())
    setExpanded(new Set())
    setParams({})
    setResults({})
    setLoadingSet(new Set())
    setPageLoading(true)

    let mounted = true
    Promise.all([
      api.get(`/universal/smart-catalog/${fileId}${sheetName ? '?sheet=' + encodeURIComponent(sheetName) : ''}`),
      api.get('/universal/catalog'),
    ]).then(([smart, cat]) => {
      if (!mounted) return
      const sd = smart.data
      setSmartData(sd)
      setFullCatalog(cat.data)

      // Pre-check defaults
      const defChecked = new Set()
      const initParams = {}
      const catMap = {}
      ;(cat.data.analyses || []).forEach(a => { catMap[a.id] = a })

      ;(sd.items || []).forEach(item => {
        if (item.is_parent) return
        if (item.default) defChecked.add(item.key)

        // Init params from catalog
        const paramDefs = catMap[item.analysis_id]?.params || []
        const ip = {}
        paramDefs.forEach(p => {
          if (p.type === 'numeric_column_multi' || p.type === 'any_column_multi') ip[p.name] = []
          else if (p.type === 'number') ip[p.name] = p.default ?? ''
          else if (p.type === 'group_value') ip[p.name] = ''
          else {
            const opts = p.type === 'numeric_column' ? sd.numeric_columns
                       : p.type === 'categorical_column' ? sd.categorical_columns
                       : p.type === 'date_column' ? sd.date_columns
                       : sd.all_columns
            ip[p.name] = opts?.[0] || ''
          }
        })
        initParams[item.key] = ip
      })

      setChecked(defChecked)
      setParams(initParams)
      setPageLoading(false)
    }).catch(() => {
      if (!mounted) return
      toast.error('Failed to load analytics engine')
      setPageLoading(false)
    })
    return () => { mounted = false }
  }, [fileId, sheetName])  // re-fetch when sheet changes

  // Build analysis_id → catalog entry map for param lookups
  const catalogMap = {}
  ;(fullCatalog?.analyses || []).forEach(a => { catalogMap[a.id] = a })

  const canRunPremium = (user?.plan || 'free') !== 'free' || (user?.download_credits || 0) > 0

  const toggleCheck = useCallback((key) => {
    setChecked(prev => { const n = new Set(prev); n.has(key) ? n.delete(key) : n.add(key); return n })
  }, [])

  const toggleExpand = useCallback((key) => {
    setExpanded(prev => { const n = new Set(prev); n.has(key) ? n.delete(key) : n.add(key); return n })
  }, [])

  const updateParam = useCallback((key, pname, val) => {
    setParams(prev => ({ ...prev, [key]: { ...prev[key], [pname]: val } }))
  }, [])

  const runSingle = useCallback(async (key, analysisId, paramVals, paramDefs) => {
    const parameters = {}
    for (const p of (paramDefs || [])) {
      let val = paramVals?.[p.name]
      if (p.type === 'number') val = (val === '' || val === undefined) ? p.default : Number(val)
      if (p.type === 'group_value' && !val) continue
      if (p.required && (val === '' || val === undefined || val === null || (Array.isArray(val) && val.length === 0))) {
        setExpanded(prev => { const n = new Set(prev); n.add(key); return n })
        toast.error(`Please fill required fields for "${catalogMap[analysisId]?.label || analysisId}"`)
        return false
      }
      parameters[p.name] = val
    }

    setLoadingSet(prev => new Set([...prev, key]))
    try {
      const res = await api.post('/universal/run', {
        file_id: parseInt(fileId),
        analysis_type: analysisId,
        parameters,
        sheet_name: sheetName || null,
      })
      setResults(prev => ({ ...prev, [key]: res.data.result }))
      setExpanded(prev => { const n = new Set(prev); n.add(key); return n })
      // Sync the live credit count into the auth store so the sidebar/topbar
      // reflect the real remaining balance immediately after this run.
      if (res.data.credits_remaining !== undefined) {
        updateUser({ download_credits: res.data.credits_remaining })
      }
      return true
    } catch (err) {
      const e = err.response?.data || {}
      setResults(prev => ({ ...prev, [key]: { error: e.error || 'Analysis failed', category:'Error' } }))
      setExpanded(prev => { const n = new Set(prev); n.add(key); return n })
      // Even a blocked/failed run may carry the true credit count (e.g. 0) —
      // sync it so the UI never shows a stale non-zero number.
      if (e.credits_remaining !== undefined) {
        updateUser({ download_credits: e.credits_remaining })
      }
      if (e.upgrade_required) toast.error(e.error || 'Requires a paid plan or credits.')
      else toast.error(e.error || `Failed: ${analysisId}`)
      return false
    } finally {
      setLoadingSet(prev => { const n = new Set(prev); n.delete(key); return n })
    }
  }, [fileId, catalogMap, updateUser])

  const runAllChecked = useCallback(async () => {
    if (checked.size === 0) { toast.error('Select at least one analysis first'); return }
    setRunAllLoading(true)
    let ok = 0, fail = 0
    const items = (smartData?.items || []).filter(i => !i.is_parent && checked.has(i.key))
    for (const item of items) {
      const paramDefs = catalogMap[item.analysis_id]?.params || []
      const success = await runSingle(item.key, item.analysis_id, params[item.key] || {}, paramDefs)
      success ? ok++ : fail++
    }
    setRunAllLoading(false)
    toast.success(`Done — ${ok} complete${fail > 0 ? `, ${fail} failed` : ''}`)
  }, [checked, smartData, catalogMap, params, runSingle])

  if (pageLoading) return (
    <div style={{ display:'flex', alignItems:'center', justifyContent:'center', height:200 }}>
      <RefreshCw size={24} style={{ color:PURPLE, animation:'spin 1s linear infinite' }}/>
    </div>
  )
  if (!smartData) return <p style={{ color:TEXT2, textAlign:'center', padding:40 }}>Analytics engine unavailable.</p>

  const TypeIcon    = TYPE_ICONS[smartData.detected_type] || LayoutGrid
  const numCols     = smartData.numeric_columns || []
  const catCols     = smartData.categorical_columns || []
  const dateCols    = smartData.date_columns || []
  const allCols     = smartData.all_columns || []
  const items       = smartData.items || []
  const totalChecked = checked.size
  const totalDone   = Object.values(results).filter(r => r && !r.error).length

  // Select/clear all non-parent items
  const allSubKeys  = items.filter(i => !i.is_parent).map(i => i.key)

  return (
    <div>
      {/* ── Top banner ── */}
      <div className="card" style={{ padding:'14px 18px', marginBottom:16, background:'linear-gradient(135deg,rgba(107,45,139,0.06) 0%,rgba(107,45,139,0.02) 100%)' }}>
        <div style={{ display:'flex', alignItems:'flex-start', gap:12, flexWrap:'wrap' }}>
          <div style={{ display:'flex', alignItems:'center', gap:12, flex:1, minWidth:'180px' }}>
            <div style={{ width:40, height:40, borderRadius:12, background:'rgba(107,45,139,0.12)', display:'flex', alignItems:'center', justifyContent:'center', flexShrink:0 }}>
              <TypeIcon size={20} style={{color:PURPLE}}/>
            </div>
            <div style={{ flex:1, minWidth:0 }}>
              <div style={{ display:'flex', alignItems:'center', gap:8, flexWrap:'wrap', marginBottom:2 }}>
                <p style={{ fontSize:14, fontWeight:700, color:TEXT, margin:0 }}>Detected: {smartData.type_label}</p>
                <span className="badge badge-purple" style={{fontSize:10}}>Auto-detected</span>
              </div>
              <p style={{ fontSize:12, color:TEXT2, margin:0 }}>{smartData.type_description}</p>
              <div style={{ display:'flex', flexWrap:'wrap', gap:'6px 14px', marginTop:4, fontSize:11, color:TEXT3 }}>
                {numCols.length > 0 && <span>📊 {numCols.length} numeric</span>}
                {catCols.length > 0 && <span>🏷 {catCols.length} categorical</span>}
                {dateCols.length > 0 && <span>📅 {dateCols.length} date</span>}
              </div>
            </div>
          </div>
          <div style={{ display:'flex', gap:8, flexWrap:'wrap', marginLeft:'auto', alignItems:'center' }}>
            {totalDone > 0 && (
              <>
                <button
                  onClick={() => {
                    const entries = items
                      .filter(i => !i.is_parent && results[i.key] && !results[i.key].error)
                      .map(i => ({ label: i.label, number: i.number || '', result: results[i.key] }))
                    dlServerReport('pdf', entries, file?.original_name, smartData?.type_label)
                  }}
                  title="Download all completed analyses as PDF"
                  style={{ display:'flex', alignItems:'center', gap:6, padding:'9px 14px', borderRadius:10, border:'1px solid rgba(107,45,139,0.3)', background:'rgba(107,45,139,0.07)', color:PURPLE, fontSize:12, fontWeight:700, cursor:'pointer', whiteSpace:'nowrap' }}>
                  <Download size={13}/> All PDF ({totalDone})
                </button>
                <button
                  onClick={() => {
                    const entries = items
                      .filter(i => !i.is_parent && results[i.key] && !results[i.key].error)
                      .map(i => ({ label: i.label, number: i.number || '', result: results[i.key] }))
                    dlServerReport('excel', entries, file?.original_name, smartData?.type_label)
                  }}
                  title="Download all completed analyses as Excel"
                  style={{ display:'flex', alignItems:'center', gap:6, padding:'9px 14px', borderRadius:10, border:'1px solid rgba(22,163,74,0.3)', background:'rgba(22,163,74,0.07)', color:'#16A34A', fontSize:12, fontWeight:700, cursor:'pointer', whiteSpace:'nowrap' }}>
                  <FileSpreadsheet size={13}/> All Excel ({totalDone})
                </button>
              </>
            )}
            <button onClick={runAllChecked} disabled={runAllLoading || totalChecked === 0}
              style={{ display:'flex', alignItems:'center', gap:6, padding:'9px 16px', borderRadius:10, border:'none', cursor:totalChecked===0?'not-allowed':'pointer', background:totalChecked===0?'rgba(107,45,139,0.12)':PURPLE, color:totalChecked===0?TEXT3:'#fff', fontSize:13, fontWeight:600 }}>
              {runAllLoading ? <RefreshCw size={14} style={{animation:'spin 1s linear infinite'}}/> : <Sparkles size={14}/>}
              {runAllLoading ? 'Running…' : `Run Selected (${totalChecked})`}
            </button>
          </div>
        </div>
      </div>

      {/* ── AI Domain Insight banner ── */}
      {smartData.ai_domain && (
        <div className="card" style={{ padding:'12px 16px', marginBottom:14, borderLeft:`3px solid ${PURPLE}` }}>
          <div style={{ display:'flex', alignItems:'center', gap:8, flexWrap:'wrap', marginBottom:4 }}>
            <Sparkles size={14} style={{ color:PURPLE }}/>
            <span style={{ fontSize:13, fontWeight:700, color:TEXT }}>
              AI detected: {smartData.ai_domain}
            </span>
            <span className="badge badge-purple" style={{ fontSize:9 }}>
              {smartData.ai_method === 'ai' ? 'Gemini AI' : 'Smart rules'}
            </span>
          </div>
          {smartData.ai_summary && (
            <p style={{ fontSize:12, color:TEXT2, margin:'0 0 6px' }}>{smartData.ai_summary}</p>
          )}
          {smartData.ai_reasoning && (
            <p style={{ fontSize:11, color:TEXT3, margin:0 }}>💡 {smartData.ai_reasoning}</p>
          )}
          {smartData.ai_not_recommended?.length > 0 && (
            <p style={{ fontSize:11, color:'#D97706', margin:'6px 0 0' }}>
              ⚠ Not ideal for this data: {smartData.ai_not_recommended.map(t => t.replace(/_/g,' ')).join(', ')}
            </p>
          )}
        </div>
      )}

      {/* ── Select / Clear all + instruction ── */}
      <div style={{ display:'flex', alignItems:'center', gap:16, marginBottom:14 }}>
        <button onClick={() => setChecked(new Set(allSubKeys))}
          style={{ background:'none', border:'none', cursor:'pointer', fontSize:12, fontWeight:600, color:PURPLE, padding:0 }}>
          Select All
        </button>
        <button onClick={() => setChecked(new Set())}
          style={{ background:'none', border:'none', cursor:'pointer', fontSize:12, fontWeight:600, color:TEXT3, padding:0 }}>
          Clear All
        </button>
        <p style={{ fontSize:12, color:TEXT3, margin:0 }}>
          ☑ Tick the sub-tests you want → <strong>Run</strong> next to each, or <strong>Run Selected</strong> above to run all at once.
        </p>
      </div>

      {/* ── Flat list: parent headers + sub-test rows ── */}
      <div className="card" style={{ padding:'4px 16px 16px' }}>
        {items.map(item => {
          if (item.is_parent) {
            // ── Section header ──
            return (
              <div key={item.key} style={{
                padding:'14px 4px 6px',
                fontSize:13,
                fontWeight:700,
                color:PURPLE,
                borderBottom:`2px solid rgba(107,45,139,0.12)`,
                marginTop:12,
                marginBottom:6,
                letterSpacing:'0.02em',
              }}>
                {item.label}
              </div>
            )
          }

          // ── Sub-test row ──
          const paramDefs = catalogMap[item.analysis_id]?.params || []
          return (
            <SubTestRow
              key={item.key}
              item={item}
              isChecked={checked.has(item.key)}
              onToggle={() => toggleCheck(item.key)}
              isExpanded={expanded.has(item.key)}
              onExpand={() => toggleExpand(item.key)}
              params={params[item.key] || {}}
              onParamChange={(pname, val) => updateParam(item.key, pname, val)}
              paramDefs={paramDefs}
              numericCols={numCols}
              categoricalCols={catCols}
              dateCols={dateCols}
              allCols={allCols}
              result={results[item.key]}
              loading={loadingSet.has(item.key)}
              onRun={() => runSingle(item.key, item.analysis_id, params[item.key]||{}, paramDefs)}
              canRun={canRunPremium}
              fileName={file?.original_name}
              dataType={smartData?.type_label}
              notRecommended={(smartData?.ai_not_recommended || []).includes(item.analysis_id)}
            />
          )
        })}
      </div>

      <style>{`@keyframes spin{from{transform:rotate(0deg)}to{transform:rotate(360deg)}}`}</style>
    </div>
  )
}