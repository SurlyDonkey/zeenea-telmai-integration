import { useEffect, useState, useCallback } from 'react'
import { fetchAssets, linkAsset, unlinkAsset, MappedAsset } from '../api/client'
import { QualityBadge, AlertBadge } from '../components/StatusBadge'

interface TelmaiItem {
  id: string
  name: string
  display_name: string
  quality_score: number | null
  alert_count: number
}

// Derive Telmai items from the assets list (mock data has all 5 Telmai datasets)
function deriveTelmaiItems(assets: MappedAsset[]): TelmaiItem[] {
  const seen = new Set<string>()
  const items: TelmaiItem[] = []
  for (const a of assets) {
    if (a.telmai_id && !seen.has(a.telmai_id)) {
      seen.add(a.telmai_id)
      items.push({
        id: a.telmai_id,
        name: a.telmai_name ?? a.telmai_id,
        display_name: a.telmai_name ?? a.telmai_id,
        quality_score: a.quality_score,
        alert_count: a.alert_count,
      })
    }
  }
  // Add unlinked telmai datasets from mock (they won't appear in assets unless linked)
  return items
}

export default function AssetBrowser() {
  const [assets, setAssets] = useState<MappedAsset[]>([])
  const [telmaiItems, setTelmaiItems] = useState<TelmaiItem[]>([])
  const [loading, setLoading] = useState(true)
  const [selectedZeneaId, setSelectedZeneaId] = useState<string | null>(null)
  const [busy, setBusy] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [flashMsg, setFlashMsg] = useState<string | null>(null)

  const load = useCallback(async () => {
    try {
      const data = await fetchAssets()
      setAssets(data)
      setTelmaiItems(deriveTelmaiItems(data))
      setError(null)
    } catch (e: any) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    load()
  }, [load])

  const selectedAsset = assets.find(a => a.zeenea_id === selectedZeneaId)

  async function handleLink(telmaiId: string) {
    if (!selectedZeneaId) return
    setBusy(telmaiId)
    try {
      await linkAsset(selectedZeneaId, telmaiId)
      setFlashMsg(`Linked successfully`)
      setSelectedZeneaId(null)
      await load()
    } catch (e: any) {
      setError(e.message)
    } finally {
      setBusy(null)
      setTimeout(() => setFlashMsg(null), 3000)
    }
  }

  async function handleUnlink(zeneaId: string) {
    setBusy(zeneaId)
    try {
      await unlinkAsset(zeneaId)
      setFlashMsg('Unlinked successfully')
      setSelectedZeneaId(null)
      await load()
    } catch (e: any) {
      setError(e.message)
    } finally {
      setBusy(null)
      setTimeout(() => setFlashMsg(null), 3000)
    }
  }

  const linkedTelmaiIds = new Set(assets.filter(a => a.telmai_id).map(a => a.telmai_id!))

  return (
    <div className="p-8">
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-slate-900">Asset Browser</h1>
        <p className="text-slate-500 text-sm mt-1">
          Select a Zeenea asset, then click a Telmai dataset to link them
        </p>
      </div>

      {error && (
        <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">
          {error}
        </div>
      )}

      {flashMsg && (
        <div className="mb-4 p-3 bg-emerald-50 border border-emerald-200 rounded-lg text-sm text-emerald-700">
          {flashMsg}
        </div>
      )}

      {selectedZeneaId && (
        <div className="mb-4 p-3 bg-blue-50 border border-blue-200 rounded-lg text-sm text-blue-800">
          Selected: <strong>{selectedAsset?.zeenea_name}</strong> — now click a Telmai dataset on the right to link it, or click elsewhere to deselect
        </div>
      )}

      <div className="grid grid-cols-2 gap-6">
        {/* Zeenea Panel */}
        <div className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
          <div className="px-5 py-4 border-b border-slate-100 flex items-center gap-2">
            <span className="text-lg">🌐</span>
            <div>
              <div className="font-semibold text-slate-800">Zeenea Assets</div>
              <div className="text-slate-400 text-xs">{assets.length} datasets in catalog</div>
            </div>
          </div>

          {loading ? (
            <div className="p-8 text-center text-slate-400">
              <div className="inline-block w-5 h-5 border-2 border-slate-300 border-t-blue-500 rounded-full animate-spin mb-2" />
              <div className="text-sm">Loading…</div>
            </div>
          ) : (
            <ul className="divide-y divide-slate-100">
              {assets.map(asset => {
                const isSelected = selectedZeneaId === asset.zeenea_id
                const isLinked = asset.status === 'linked'
                return (
                  <li
                    key={asset.zeenea_id}
                    onClick={() => setSelectedZeneaId(isSelected ? null : asset.zeenea_id)}
                    className={`px-5 py-4 cursor-pointer transition-colors ${
                      isSelected
                        ? 'bg-blue-50 border-l-4 border-blue-500'
                        : 'hover:bg-slate-50 border-l-4 border-transparent'
                    }`}
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0">
                        <div className="font-medium text-slate-900 text-sm truncate">
                          {asset.zeenea_name}
                        </div>
                        {isLinked && (
                          <div className="text-slate-400 text-xs mt-0.5">
                            → {asset.telmai_name}
                          </div>
                        )}
                      </div>
                      <div className="flex items-center gap-2 flex-shrink-0">
                        {isLinked && (
                          <span className="text-xs bg-blue-100 text-blue-700 px-2 py-0.5 rounded-full font-medium">
                            Linked
                          </span>
                        )}
                        {isLinked && (
                          <button
                            onClick={e => { e.stopPropagation(); handleUnlink(asset.zeenea_id) }}
                            disabled={busy === asset.zeenea_id}
                            className="text-xs text-red-600 hover:text-red-800 disabled:opacity-50 font-medium"
                          >
                            {busy === asset.zeenea_id ? '…' : 'Unlink'}
                          </button>
                        )}
                      </div>
                    </div>
                  </li>
                )
              })}
            </ul>
          )}
        </div>

        {/* Telmai Panel */}
        <div className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
          <div className="px-5 py-4 border-b border-slate-100 flex items-center gap-2">
            <span className="text-lg">🔍</span>
            <div>
              <div className="font-semibold text-slate-800">Telmai Datasets</div>
              <div className="text-slate-400 text-xs">
                {selectedZeneaId ? 'Click to link with selected Zeenea asset' : 'Select a Zeenea asset first'}
              </div>
            </div>
          </div>

          {loading ? (
            <div className="p-8 text-center text-slate-400">
              <div className="inline-block w-5 h-5 border-2 border-slate-300 border-t-blue-500 rounded-full animate-spin mb-2" />
              <div className="text-sm">Loading…</div>
            </div>
          ) : telmaiItems.length === 0 ? (
            <div className="p-8 text-center text-slate-400 text-sm">
              No Telmai datasets available. Run a push sync first.
            </div>
          ) : (
            <ul className="divide-y divide-slate-100">
              {telmaiItems.map(item => {
                const isLinked = linkedTelmaiIds.has(item.id)
                const isBusy = busy === item.id
                return (
                  <li
                    key={item.id}
                    onClick={() => {
                      if (selectedZeneaId && !isLinked) handleLink(item.id)
                    }}
                    className={`px-5 py-4 transition-colors ${
                      selectedZeneaId && !isLinked
                        ? 'cursor-pointer hover:bg-emerald-50'
                        : isLinked
                        ? 'opacity-60 cursor-not-allowed'
                        : 'cursor-default'
                    }`}
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0">
                        <div className="font-medium text-slate-900 text-sm truncate">
                          {item.display_name}
                        </div>
                        <div className="text-slate-400 text-xs mt-0.5">{item.id}</div>
                      </div>
                      <div className="flex items-center gap-2 flex-shrink-0">
                        <QualityBadge score={item.quality_score} size="sm" />
                        <AlertBadge count={item.alert_count} size="sm" />
                        {isLinked && (
                          <span className="text-xs bg-blue-100 text-blue-700 px-2 py-0.5 rounded-full font-medium">
                            Linked
                          </span>
                        )}
                        {isBusy && (
                          <span className="inline-block w-3 h-3 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
                        )}
                      </div>
                    </div>
                  </li>
                )
              })}
            </ul>
          )}
        </div>
      </div>
    </div>
  )
}
