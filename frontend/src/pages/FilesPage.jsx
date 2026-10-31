import React, { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import api from '../utils/api'
import {
  FileSpreadsheet, BarChart2, Trash2, Upload, Search,
  AlertCircle, RefreshCw, Calendar, Layers
} from 'lucide-react'
import { formatDistanceToNow } from 'date-fns'
import toast from 'react-hot-toast'

function QualityBadge({ score }) {
  if (!score) return null
  const s = Math.round(score)
  if (s >= 80) return <span className="badge badge-green">{s}</span>
  if (s >= 50) return <span className="badge badge-amber">{s}</span>
  return <span className="badge badge-red">{s}</span>
}

export default function FilesPage() {
  const [files, setFiles] = useState([])
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')
  const [deleting, setDeleting] = useState(null)
  const [page, setPage] = useState(1)
  const [totalPages, setTotalPages] = useState(1)

  const fetchFiles = async (pg = 1) => {
    setLoading(true)
    try {
      const res = await api.get(`/excel/files?page=${pg}&per_page=12`)
      setFiles(res.data.files)
      setTotalPages(res.data.pages)
      setPage(pg)
    } catch {
      toast.error('Failed to load files')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { fetchFiles() }, [])

  const handleDelete = async (fileId, name) => {
    if (!confirm(`Delete "${name}"? This cannot be undone.`)) return
    setDeleting(fileId)
    try {
      await api.delete(`/excel/files/${fileId}`)
      setFiles(f => f.filter(x => x.id !== fileId))
      toast.success('File deleted')
    } catch {
      toast.error('Failed to delete')
    } finally {
      setDeleting(null)
    }
  }

  const filtered = files.filter(f => f.original_name.toLowerCase().includes(search.toLowerCase()))
  const statusColor = { ready: 'badge-green', processing: 'badge-amber', error: 'badge-red' }

  return (
    <div className="space-y-5 stagger">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-[var(--text)]">My Files</h1>
          <p className="text-sm text-[var(--text2)] mt-0.5">{files.length} file{files.length !== 1 ? 's' : ''} uploaded</p>
        </div>
        <Link to="/upload" className="btn btn-primary btn-md">
          <Upload size={16} /> Upload File
        </Link>
      </div>

      {/* Search */}
      <div className="relative">
        <Search size={16} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-[var(--text3)]" />
        <input
          type="text"
          className="input pl-10"
          placeholder="Search files…"
          value={search}
          onChange={e => setSearch(e.target.value)}
        />
      </div>

      {loading ? (
        <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {[...Array(6)].map((_, i) => <div key={i} className="skeleton h-44 rounded-2xl" />)}
        </div>
      ) : !filtered.length ? (
        <div className="card p-12 text-center">
          {search ? (
            <>
              <Search size={40} className="text-[var(--text3)] mx-auto mb-3" />
              <p className="text-[var(--text2)]">No files matching "{search}"</p>
            </>
          ) : (
            <>
              <FileSpreadsheet size={40} className="text-[var(--text3)] mx-auto mb-3" />
              <p className="font-semibold text-[var(--text)] mb-1">No files yet</p>
              <p className="text-sm text-[var(--text2)] mb-4">Upload your first Excel or CSV file to get started</p>
              <Link to="/upload" className="btn btn-primary btn-md inline-flex">
                <Upload size={16} /> Upload Now
              </Link>
            </>
          )}
        </div>
      ) : (
        <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {filtered.map(file => (
            <div key={file.id} className="card-hover p-5 flex flex-col group">
              {/* File header */}
              <div className="flex items-start gap-3 mb-4">
                <div className="w-10 h-10 rounded-xl bg-green-500/10 flex items-center justify-center flex-shrink-0">
                  <FileSpreadsheet size={20} className="text-green-400" />
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-semibold text-[var(--text)] truncate" title={file.original_name}>
                    {file.original_name}
                  </p>
                  <div className="flex items-center gap-2 mt-1">
                    <span className={`badge ${statusColor[file.status] || 'badge-gray'}`}>{file.status}</span>
                    <span className="text-[10px] text-[var(--text3)] font-mono uppercase">.{file.file_type}</span>
                  </div>
                </div>
              </div>

              {/* Stats */}
              {file.status === 'ready' && (
                <div className="grid grid-cols-3 gap-2 mb-4">
                  <div className="text-center">
                    <div className="text-sm font-bold text-[var(--text)]">{file.total_rows?.toLocaleString() || '—'}</div>
                    <div className="text-[10px] text-[var(--text3)]">Rows</div>
                  </div>
                  <div className="text-center">
                    <div className="text-sm font-bold text-[var(--text)]">{file.total_cols || '—'}</div>
                    <div className="text-[10px] text-[var(--text3)]">Cols</div>
                  </div>
                  <div className="text-center">
                    <div className="text-sm font-bold text-[var(--text)]">
                      <QualityBadge score={file.data_quality_score} />
                    </div>
                    <div className="text-[10px] text-[var(--text3)]">Quality</div>
                  </div>
                </div>
              )}

              {file.status === 'error' && (
                <div className="flex items-center gap-2 text-xs text-red-400 mb-4 bg-red-500/10 rounded-lg px-3 py-2">
                  <AlertCircle size={13} />
                  <span className="truncate">{file.error_message || 'Processing failed'}</span>
                </div>
              )}

              <div className="mt-auto flex items-center justify-between text-[11px] text-[var(--text3)] mb-3">
                <span className="flex items-center gap-1">
                  <Calendar size={11} />
                  {formatDistanceToNow(new Date(file.created_at), { addSuffix: true })}
                </span>
                {file.sheet_count > 1 && (
                  <span className="flex items-center gap-1">
                    <Layers size={11} /> {file.sheet_count} sheets
                  </span>
                )}
              </div>

              {/* Actions */}
              <div className="flex gap-2">
                {file.status === 'ready' ? (
                  <Link to={`/analysis/${file.id}`} className="btn btn-secondary btn-sm flex-1">
                    <BarChart2 size={14} /> Analyze
                  </Link>
                ) : (
                  <button disabled className="btn btn-ghost btn-sm flex-1 opacity-50">
                    <RefreshCw size={14} /> {file.status}
                  </button>
                )}
                <button
                  onClick={() => handleDelete(file.id, file.original_name)}
                  disabled={deleting === file.id}
                  className="btn btn-danger btn-sm"
                >
                  {deleting === file.id
                    ? <RefreshCw size={14} className="animate-spin" />
                    : <Trash2 size={14} />}
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex justify-center gap-2 pt-2">
          <button disabled={page <= 1} onClick={() => fetchFiles(page - 1)}
            className="btn btn-secondary btn-sm">Previous</button>
          <span className="flex items-center px-4 text-sm text-[var(--text2)]">
            Page {page} of {totalPages}
          </span>
          <button disabled={page >= totalPages} onClick={() => fetchFiles(page + 1)}
            className="btn btn-secondary btn-sm">Next</button>
        </div>
      )}
    </div>
  )
}
