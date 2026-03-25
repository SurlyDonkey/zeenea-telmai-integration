import { useEffect, useState, useCallback } from 'react'
import { fetchQuality, triggerSync, MappedAsset, SyncResult } from '../api/client'
import { QualityBadge, AlertBadge } from '../components/StatusBadge'
import SyncButton from '../components/SyncButton'

function formatDate(iso: string | null): string {
  if (!iso) return '—'
  return new Date(iso).toLocaleString(undefined, {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

export default function Dashboard() {
  const [assets, setAssets] = useState<MappedAsset[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [syncResult, setSyncResult] = useState<SyncResult | null>(null)

  const load = useCallback(async () => {
    try {
      const data = await fetchQuality()
      setAssets(data)
      setError(null)
    } catch (e: any) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    load()
    const id = setInterval(load, 30_000)
    return () => clearInterval(id)
  }, [load])

  const linked = assets.filter(a => a.status === 'linked')
  const totalAlerts = linked.reduce((sum, a) => sum + a.alert_count, 0)
  const avgScore =
    linked.length > 0
      ? linked
          .filter(a => a.quality_score !== null)
          .reduce((sum, a) => sum + (a.quality_score ?? 0), 0) /
        (linked.filter(a => a.quality_score !== null).length || 1)
      : null

  function handleSyncAll(result: SyncResult) {
    setSyncResult(result)
    load()
    setTimeout(() => setSyncResult(null), 5000)
  }

  return (
    <div className="p-8">
      {/* Header */}
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Dashboard</h1>
          <p className="text-slate-500 text-sm mt-1">Quality overview across all integrated assets</p>
        </div>
        <SyncButton direction="full" label="Sync All" onComplete={handleSyncAll} />
      </div>

      {/* Sync result flash */}
      {syncResult && (
        <div className="mb-6 p-4 bg-blue-50 border border-blue-200 rounded-lg text-sm text-blue-800">
          Sync complete — {syncResult.synced} synced, {syncResult.failed} failed, {syncResult.skipped} skipped
        </div>
      )}

      {/* Stat cards */}
      <div className="grid grid-cols-3 gap-6 mb-8">
        <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6">
          <div className="text-slate-500 text-sm font-medium mb-1">Total Assets</div>
          <div className="text-3xl font-bold text-slate-900">{assets.length}</div>
          <div className="text-slate-400 text-xs mt-1">{linked.length} linked to Telmai</div>
        </div>
        <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6">
          <div className="text-slate-500 text-sm font-medium mb-1">Open Alerts</div>
          <div className={`text-3xl font-bold ${totalAlerts > 5 ? 'text-red-600' : totalAlerts > 0 ? 'text-yellow-600' : 'text-emerald-600'}`}>
            {totalAlerts}
          </div>
          <div className="text-slate-400 text-xs mt-1">across all monitored datasets</div>
        </div>
        <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6">
          <div className="text-slate-500 text-sm font-medium mb-1">Avg Quality Score</div>
          <div className={`text-3xl font-bold ${avgScore === null ? 'text-slate-400' : avgScore >= 80 ? 'text-emerald-600' : avgScore >= 60 ? 'text-yellow-600' : 'text-red-600'}`}>
            {avgScore !== null ? `${avgScore.toFixed(1)}%` : '—'}
          </div>
          <div className="text-slate-400 text-xs mt-1">weighted average</div>
        </div>
      </div>

      {/* Error state */}
      {error && (
        <div className="mb-6 p-4 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">
          Failed to load assets: {error}
        </div>
      )}

      {/* Asset table */}
      <div className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
        <div className="px-6 py-4 border-b border-slate-100">
          <h2 className="font-semibold text-slate-800">Asset Quality Overview</h2>
        </div>

        {loading ? (
          <div className="p-12 text-center text-slate-400">
            <div className="inline-block w-6 h-6 border-2 border-slate-300 border-t-blue-500 rounded-full animate-spin mb-3" />
            <div>Loading assets…</div>
          </div>
        ) : assets.length === 0 ? (
          <div className="p-12 text-center text-slate-400">
            No assets found. Configure your connections in Settings.
          </div>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-slate-50 border-b border-slate-100">
                <th className="text-left px-6 py-3 font-medium text-slate-600">Asset Name</th>
                <th className="text-left px-6 py-3 font-medium text-slate-600">Telmai Dataset</th>
                <th className="text-left px-6 py-3 font-medium text-slate-600">Quality Score</th>
                <th className="text-left px-6 py-3 font-medium text-slate-600">Open Alerts</th>
                <th className="text-left px-6 py-3 font-medium text-slate-600">Last Synced</th>
                <th className="text-left px-6 py-3 font-medium text-slate-600">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {assets.map(asset => (
                <tr key={asset.zeenea_id} className="hover:bg-slate-50 transition-colors">
                  <td className="px-6 py-4">
                    <div className="font-medium text-slate-900">{asset.zeenea_name}</div>
                    <div className="text-slate-400 text-xs">{asset.zeenea_id}</div>
                  </td>
                  <td className="px-6 py-4">
                    {asset.telmai_name ? (
                      <div>
                        <div className="text-slate-700">{asset.telmai_name}</div>
                        <div className="text-slate-400 text-xs">{asset.telmai_id}</div>
                      </div>
                    ) : (
                      <span className="text-slate-400 italic">Not linked</span>
                    )}
                  </td>
                  <td className="px-6 py-4">
                    <QualityBadge score={asset.quality_score} />
                  </td>
                  <td className="px-6 py-4">
                    <AlertBadge count={asset.alert_count} />
                  </td>
                  <td className="px-6 py-4 text-slate-500">
                    {formatDate(asset.last_synced)}
                  </td>
                  <td className="px-6 py-4">
                    {asset.status === 'linked' ? (
                      <SyncButton
                        direction="pull"
                        label="Sync"
                        size="sm"
                        variant="secondary"
                        onComplete={() => load()}
                      />
                    ) : (
                      <span className="text-slate-400 text-xs italic">Link first</span>
                    )}
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
