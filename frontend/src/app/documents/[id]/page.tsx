'use client'
import { useState, useEffect, useRef } from 'react'
import { useRouter, useParams } from 'next/navigation'
import { api, API_URL, TERMINAL_STATUSES } from '@/lib/api'
import type { Document } from '@/lib/api'
import { StatusBadge } from '@/components/StatusBadge'

function fmtSize(b: number) {
  if (b < 1024) return `${b} B`
  if (b < 1024 ** 2) return `${(b / 1024).toFixed(1)} KB`
  return `${(b / 1024 ** 2).toFixed(1)} MB`
}

export default function DocumentDetailPage() {
  const router = useRouter()
  const { id: docId } = useParams<{ id: string }>()
  const [doc, setDoc] = useState<Document | null>(null)
  const [loading, setLoading] = useState(true)
  const [notFound, setNotFound] = useState(false)
  const [cancelling, setCancelling] = useState(false)
  const esRef = useRef<EventSource | null>(null)

  useEffect(() => {
    const token = localStorage.getItem('token')
    if (!token) { router.replace('/login'); return }

    api.get<Document>(`/documents/${docId}`)
      .then(res => {
        setDoc(res.data)
        if (!TERMINAL_STATUSES.has(res.data.status)) openSSE(docId, token)
      })
      .catch(() => setNotFound(true))
      .finally(() => setLoading(false))

    return () => esRef.current?.close()
  }, [docId, router])

  function openSSE(id: string, token: string) {
    const url = `${API_URL}/v1/documents/${id}/stream?token=${encodeURIComponent(token)}`
    const es = new EventSource(url)
    esRef.current = es

    es.onmessage = (event) => {
      const data = JSON.parse(event.data)
      setDoc(prev => prev ? { ...prev, ...data } : prev)
      if (TERMINAL_STATUSES.has(data.status)) {
        es.close()
        esRef.current = null
      }
    }

    es.onerror = () => { es.close(); esRef.current = null }
  }

  const handleCancel = async () => {
    if (!doc || !confirm('Cancel processing for this document?')) return
    setCancelling(true)
    try {
      const res = await api.post<Document>(`/documents/${doc.id}/cancel`)
      setDoc(res.data)
      esRef.current?.close()
      esRef.current = null
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Could not cancel')
    } finally {
      setCancelling(false)
    }
  }

  if (loading) return <Centered>Loading…</Centered>
  if (notFound) return <Centered>Document not found.</Centered>
  if (!doc) return null

  const canCancel = doc.status === 'uploaded' || doc.status === 'queued'

  return (
    <div className="min-h-screen bg-slate-50">
      <header className="bg-white border-b border-slate-200 px-6 py-4 flex items-center gap-3">
        <button
          onClick={() => router.push('/documents')}
          className="text-slate-500 hover:text-slate-800 text-sm flex items-center gap-1"
        >
          ← Back
        </button>
        <h1 className="text-lg font-semibold text-slate-800 flex-1">Document Detail</h1>
        {canCancel && (
          <button
            onClick={handleCancel}
            disabled={cancelling}
            className="text-sm text-red-500 hover:text-red-700 disabled:opacity-50 border border-red-200 hover:border-red-400 px-3 py-1.5 rounded-lg transition-colors"
          >
            {cancelling ? 'Cancelling…' : 'Cancel processing'}
          </button>
        )}
      </header>

      <main className="max-w-3xl mx-auto px-6 py-8 space-y-5">
        {/* Metadata card */}
        <div className="bg-white border border-slate-200 rounded-xl p-5">
          <div className="flex items-start justify-between gap-4">
            <div className="flex items-center gap-3">
              <div>
                <h2 className="font-semibold text-slate-800 break-all">{doc.original_filename}</h2>
                <p className="text-xs text-slate-400 mt-0.5">{fmtSize(doc.file_size)} · {doc.mime_type}</p>
              </div>
            </div>
            <StatusBadge status={doc.status} />
          </div>
          <div className="mt-4 grid grid-cols-2 gap-3 text-xs text-slate-500 border-t border-slate-100 pt-4">
            <div>
              <span className="block font-medium text-slate-600 mb-0.5">Uploaded</span>
              {new Date(doc.created_at).toLocaleString()}
            </div>
            <div>
              <span className="block font-medium text-slate-600 mb-0.5">Last updated</span>
              {new Date(doc.updated_at).toLocaleString()}
            </div>
          </div>
        </div>

        {/* Status-specific panels */}
        {(doc.status === 'uploaded' || doc.status === 'queued') && (
          <div className="bg-blue-50 border border-blue-200 rounded-xl p-5 flex items-center gap-3">
            <svg className="w-5 h-5 text-blue-400 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            <div>
              <p className="font-medium text-blue-800">
                {doc.status === 'queued' ? 'Waiting in queue' : 'Preparing…'}
              </p>
              <p className="text-sm text-blue-600 mt-0.5">Updates arrive automatically via Server-Sent Events.</p>
            </div>
          </div>
        )}

        {doc.status === 'processing' && (
          <div className="bg-amber-50 border border-amber-200 rounded-xl p-5 flex items-center gap-3">
            <svg className="animate-spin h-5 w-5 text-amber-600 shrink-0" fill="none" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
            </svg>
            <div>
              <p className="font-medium text-amber-800">Running OCR…</p>
              <p className="text-sm text-amber-600 mt-0.5">This page updates automatically.</p>
            </div>
          </div>
        )}

        {doc.status === 'cancelled' && (
          <div className="bg-slate-100 border border-slate-300 rounded-xl p-5">
            <p className="font-medium text-slate-600">Processing was cancelled</p>
            <p className="text-sm text-slate-500 mt-1">No OCR result is available for this document.</p>
          </div>
        )}

        {doc.status === 'failed' && (
          <div className="bg-red-50 border border-red-200 rounded-xl p-5">
            <p className="font-semibold text-red-800 mb-2">Processing failed</p>
            <pre className="text-sm text-red-600 whitespace-pre-wrap font-mono bg-red-100 rounded p-3">
              {doc.error_message || 'Unknown error'}
            </pre>
          </div>
        )}

        {doc.status === 'completed' && (
          <div className="bg-white border border-slate-200 rounded-xl p-5">
            <h3 className="font-semibold text-slate-700 mb-3">Extracted Text</h3>
            {doc.ocr_text?.trim() ? (
              <pre className="whitespace-pre-wrap text-sm text-slate-700 bg-slate-50 border border-slate-200 rounded-lg p-4 max-h-[28rem] overflow-y-auto font-mono leading-relaxed">
                {doc.ocr_text}
              </pre>
            ) : (
              <p className="text-slate-400 text-sm">No text was detected in this document.</p>
            )}
          </div>
        )}
      </main>
    </div>
  )
}

function Centered({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen bg-slate-50 flex items-center justify-center text-slate-400">
      {children}
    </div>
  )
}
