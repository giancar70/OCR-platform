'use client'
import { useState, useEffect, useRef } from 'react'
import { useRouter } from 'next/navigation'
import { api, API_URL, TERMINAL_STATUSES } from '@/lib/api'
import type { Document } from '@/lib/api'
import { StatusBadge } from '@/components/StatusBadge'

function fmtSize(b: number) {
  if (b < 1024) return `${b} B`
  if (b < 1024 ** 2) return `${(b / 1024).toFixed(1)} KB`
  return `${(b / 1024 ** 2).toFixed(1)} MB`
}

function fmtDate(iso: string) {
  return new Date(iso).toLocaleDateString('en-US', {
    month: 'short', day: 'numeric', year: 'numeric',
    hour: '2-digit', minute: '2-digit',
  })
}

export default function DocumentsPage() {
  const router = useRouter()
  const [docs, setDocs] = useState<Document[]>([])
  const [loading, setLoading] = useState(true)
  const [uploading, setUploading] = useState(false)
  const [error, setError] = useState('')
  const fileRef = useRef<HTMLInputElement>(null)
  const esMap = useRef<Map<string, EventSource>>(new Map())

  function watchDoc(docId: string, token: string) {
    if (esMap.current.has(docId)) return
    const es = new EventSource(`${API_URL}/v1/documents/${docId}/stream?token=${encodeURIComponent(token)}`)
    esMap.current.set(docId, es)
    es.onmessage = (event) => {
      const data = JSON.parse(event.data)
      setDocs(prev => prev.map(d => d.id === docId ? { ...d, ...data } : d))
      if (TERMINAL_STATUSES.has(data.status)) {
        es.close()
        esMap.current.delete(docId)
      }
    }
    es.onerror = () => { es.close(); esMap.current.delete(docId) }
  }

  useEffect(() => {
    const token = localStorage.getItem('token')
    if (!token) { router.replace('/login'); return }
    api.get('/documents/')
      .then(r => {
        setDocs(r.data)
        for (const doc of r.data) {
          if (!TERMINAL_STATUSES.has(doc.status)) watchDoc(doc.id, token)
        }
      })
      .catch(() => setError('Failed to load documents'))
      .finally(() => setLoading(false))
    return () => { esMap.current.forEach(es => es.close()); esMap.current.clear() }
  }, [router])

  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    setUploading(true)
    setError('')
    const form = new FormData()
    form.append('file', file)
    try {
      const res = await api.post('/documents/', form, { headers: { 'Content-Type': 'multipart/form-data' } })
      setDocs(prev => [res.data, ...prev])
      const token = localStorage.getItem('token')
      if (token && !TERMINAL_STATUSES.has(res.data.status)) watchDoc(res.data.id, token)
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Upload failed')
    } finally {
      setUploading(false)
      if (fileRef.current) fileRef.current.value = ''
    }
  }

  const handleDelete = async (id: string, e: React.MouseEvent) => {
    e.stopPropagation()
    if (!confirm('Delete this document?')) return
    try {
      await api.delete(`/documents/${id}`)
      setDocs(prev => prev.filter(d => d.id !== id))
    } catch {
      setError('Delete failed')
    }
  }

  return (
    <div className="min-h-screen bg-slate-50">
      <header className="bg-white border-b border-slate-200 px-6 py-4 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <h1 className="text-xl font-bold text-slate-800">OCR Platform</h1>
        </div>
        <button
          onClick={() => { localStorage.removeItem('token'); router.push('/login') }}
          className="text-sm text-slate-500 hover:text-slate-800 transition-colors"
        >
          Sign out
        </button>
      </header>

      <main className="max-w-4xl mx-auto px-6 py-8">
        <div className="flex items-center justify-between mb-6">
          <h2 className="text-lg font-semibold text-slate-700">Documents</h2>
          <div>
            <input ref={fileRef} type="file" accept=".jpg,.jpeg,.png,.pdf" onChange={handleUpload} className="hidden" />
            <button
              onClick={() => fileRef.current?.click()}
              disabled={uploading}
              className="inline-flex items-center gap-2 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white text-sm font-semibold px-4 py-2 rounded-lg transition-colors"
            >
              {uploading ? (
                <>
                  <svg className="animate-spin h-4 w-4" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                  </svg>
                  Uploading…
                </>
              ) : 'New Document'}
            </button>
          </div>
        </div>

        {error && (
          <div className="bg-red-50 border border-red-200 text-red-700 text-sm px-4 py-3 rounded-lg mb-4">
            {error}
          </div>
        )}

        {loading ? (
          <div className="text-center py-20 text-slate-400">Loading…</div>
        ) : docs.length === 0 ? (
          <div className="text-center py-20 text-slate-400">
            <div className="text-5xl mb-3">📂</div>
            <p className="font-medium text-lg">No documents yet</p>
            <p className="text-sm mt-1">Upload a JPG, PNG, or PDF to get started</p>
          </div>
        ) : (
          <div className="space-y-2">
            {docs.map(doc => (
              <div
                key={doc.id}
                onClick={() => router.push(`/documents/${doc.id}`)}
                className="bg-white border border-slate-200 rounded-xl px-5 py-4 flex items-center gap-4 cursor-pointer hover:border-blue-400 hover:shadow-sm transition-all"
              >
                
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-slate-800 truncate">{doc.original_filename}</p>
                  <p className="text-xs text-slate-400 mt-0.5">{fmtSize(doc.file_size)} · {fmtDate(doc.created_at)}</p>
                </div>
                <StatusBadge status={doc.status} />
                <button
                  onClick={(e) => handleDelete(doc.id, e)}
                  className="text-slate-300 hover:text-red-500 transition-colors ml-1 shrink-0"
                  title="Delete"
                >
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                      d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                  </svg>
                </button>
              </div>
            ))}
          </div>
        )}
      </main>
    </div>
  )
}
