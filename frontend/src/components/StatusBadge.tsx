type Status = 'uploaded' | 'queued' | 'processing' | 'completed' | 'failed' | 'cancelled'

const CONFIG: Record<Status, { label: string; cls: string; spin?: boolean }> = {
  uploaded:   { label: 'Uploaded',   cls: 'bg-slate-100 text-slate-600' },
  queued:     { label: 'Queued',     cls: 'bg-blue-100 text-blue-700' },
  processing: { label: 'Processing', cls: 'bg-amber-100 text-amber-700', spin: true },
  completed:  { label: 'Completed',  cls: 'bg-emerald-100 text-emerald-700' },
  failed:     { label: 'Failed',     cls: 'bg-red-100 text-red-700' },
  cancelled:  { label: 'Cancelled',  cls: 'bg-slate-200 text-slate-500' },
}

export function StatusBadge({ status }: { status: string }) {
  const cfg = CONFIG[status as Status] ?? { label: status, cls: 'bg-slate-100 text-slate-600' }
  return (
    <span className={`inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium ${cfg.cls}`}>
      {cfg.spin && (
        <svg className="animate-spin h-3 w-3 shrink-0" fill="none" viewBox="0 0 24 24">
          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
        </svg>
      )}
      {cfg.label}
    </span>
  )
}
