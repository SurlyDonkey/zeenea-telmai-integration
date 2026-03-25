import { useEffect, useState, useCallback } from 'react'
import { fetchSyncLog, clearSyncLog, SyncLogEntry } from '../api/client'

function formatDate(iso: string): string {
  return new Date(iso).toLocaleString(undefined, {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  })
}

const statusColors: Record<string, string> = {
  success: 'bg-emerald-50 border-l-emerald-400',
  failed: 'bg-red-50 border-l-red-400',
  skipped: 'bg-slate-50 border-l-slate-300',
}

const statusBadge: Record<string, string> = {
  success: 'bg-emerald-100 text-emerald-700',
  failed: 'bg-red-100 text-red-700',
  skipped: 'bg-slate-100 text-slate-500',
}

const directionLabel: Record<string, string> = {
  push:    '→ Push',
  pull:    '← Pull',
  full:    '⇄ Full',
  webhook: '⚡ Webhook',
}

const directionBadge: Record<string, string> = {
  push:    'bg-violet-100 text-violet-700',
  pull:    'bg-cyan-100 text-cyan-700',
  full:    'bg-indigo-100 text-indigo-700',
  webhook: 'bg-amber-100 text-amber-700',
}

export default function SyncLog() {
  const [log, setLog] = useState<SyncLogEntry[]>([])
  const [loading, setLoading] = useState(true)
  const [clearing, setClearing] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async () => {
    try {
      const entries = await fetchSyncLog()
      setLog(entries)
      setError(null)
    } catch (e: any) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    load()
    const id = setInterval(load, 10_000)
    return () => clearInterval(id)
  }, [load])

  async function handleClear() {
    setClearing(true)
    try {
      await clearSyncLog()
      setLog([])
    } catch (e: any) {
      setError(e.message)
    } finally {
      setClearing(false)
    }
  }

  return (
    <div className="p-8">
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Sync Log</h1>
          <p className="text-slate-500 text-sm mt-1">
            History of all sync events — auto-refreshes every 10 seconds
          </p>
        </div>
        <button
          onClick={handleClear}
          disabled={clearing || log.length === 0}
          className="px-4 py-2 text-sm rounded-lg border border-slate-300 bg-white text-slate-700 hover:bg-slate-50 disabled:opacity-50 disabled:cursor-not-allowed font-medium transition-colors"
        >
          {clearing ? 'Clearing…' : 'Clear Log'}
        </button>
      </div>

      {error && (
        <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">
          {error}
        </div>
      )}

      <div className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
        <div className="px-6 py-4 border-b border-slate-100 flex items-center justify-between">
          <h2 className="font-semibold text-slate-800">Events</h2>
          <span className="text-slate-400 text-sm">{log.length} entries</span>
        </div>

        {loading ? (
          <div className="p-12 text-center text-slate-400">
            <div className="inline-block w-6 h-6 border-2 border-slate-300 border-t-blue-500 rounded-full animate-spin mb-3" />
            <div>Loading log…</div>
          </div>
        ) : log.length === 0 ? (
          <div className="p-12 text-center text-slate-400">
            <div className="text-4xl mb-3">📋</div>
            <div className="font-medium text-slate-600">No sync events yet</div>
            <div className="text-sm mt-1">Trigger a sync from the Dashboard to see entries here</div>
          </div>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-slate-50 border-b border-slate-100">
                <th className="text-left px-6 py-3 font-medium text-slate-600">Timestamp</th>
                <th className="text-left px-6 py-3 font-medium text-slate-600">Direction</th>
                <th className="text-left px-6 py-3 font-medium text-slate-600">Asset</th>
                <th className="text-left px-6 py-3 font-medium text-slate-600">Status</th>
                <th className="text-left px-6 py-3 font-medium text-slate-600">Message</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {log.map(entry => (
                <tr
                  key={entry.id}
                  className={`border-l-4 ${statusColors[entry.status] ?? 'bg-white border-l-transparent'}`}
                >
                  <td className="px-6 py-3 text-slate-500 whitespace-nowrap font-mono text-xs">
                    {formatDate(entry.timestamp)}
                  </td>
                  <td className="px-6 py-3">
                    <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${directionBadge[entry.direction] ?? 'bg-slate-100 text-slate-600'}`}>
                      {directionLabel[entry.direction] ?? entry.direction}
                    </span>
                  </td>
                  <td className="px-6 py-3 font-medium text-slate-800">{entry.asset_name}</td>
                  <td className="px-6 py-3">
                    <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${statusBadge[entry.status] ?? 'bg-slate-100 text-slate-600'}`}>
                      {entry.status.charAt(0).toUpperCase() + entry.status.slice(1)}
                    </span>
                  </td>
                  <td className="px-6 py-3 text-slate-600 max-w-xs truncate" title={entry.message}>
                    {entry.message}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}
