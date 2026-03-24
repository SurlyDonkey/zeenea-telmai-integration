const BASE = ''

export interface MappedAsset {
  zeenea_id: string
  zeenea_name: string
  telmai_id: string | null
  telmai_name: string | null
  quality_score: number | null
  alert_count: number
  last_synced: string | null
  status: 'linked' | 'unlinked' | 'syncing' | 'error'
}

export interface ZeneaDataset {
  id: string
  name: string
  technical_name: string
  description: string | null
}

export interface TelmaiDataset {
  id: string
  name: string
  display_name: string
  external_id: string | null
  quality_score: number | null
  alert_count: number
}

export interface SyncLogEntry {
  id: string
  timestamp: string
  direction: 'push' | 'pull' | 'full'
  asset_name: string
  status: 'success' | 'failed' | 'skipped'
  message: string
}

export interface SyncResult {
  synced: number
  failed: number
  skipped: number
  log_entries: SyncLogEntry[]
}

export interface SyncStatus {
  last_push: string | null
  last_pull: string | null
  last_full: string | null
  push_synced: number
  push_failed: number
  pull_synced: number
  pull_failed: number
  mapped_assets: number
  log_entries: number
}

export interface ConnectionTestResult {
  service: string
  success: boolean
  message: string
  dataset_count: number | null
}

export interface QualityDetail {
  zeenea_id: string
  zeenea_name: string
  zeenea_description: string | null
  telmai_id: string
  telmai_name: string
  quality_score: number | null
  alert_count: number
  alerts: Alert[]
  metrics: Record<string, number>
  last_synced: string | null
}

export interface Alert {
  id: string
  dataset_id: string
  rule: string
  column: string | null
  severity: 'warning' | 'error' | 'critical'
  message: string
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json', ...options?.headers },
    ...options,
  })
  if (!res.ok) {
    const text = await res.text()
    throw new Error(`${res.status} ${res.statusText}: ${text}`)
  }
  return res.json()
}

export async function fetchAssets(): Promise<MappedAsset[]> {
  return request('/api/assets')
}

export async function fetchZeneaDatasets(): Promise<ZeneaDataset[]> {
  // Re-derive from assets endpoint for now — backend can expose separately if needed
  const assets = await fetchAssets()
  return assets.map(a => ({
    id: a.zeenea_id,
    name: a.zeenea_name,
    technical_name: a.zeenea_name,
    description: null,
  }))
}

export async function fetchTelmaiDatasets(): Promise<TelmaiDataset[]> {
  // Fetch via quality endpoint which includes telmai details
  return request('/api/assets').then((assets: MappedAsset[]) => {
    // Return empty list — we'll use AssetBrowser-specific logic
    return []
  })
}

export async function fetchQuality(): Promise<MappedAsset[]> {
  return request('/api/assets')
}

export async function fetchQualityDetail(zeneaId: string): Promise<QualityDetail> {
  return request(`/api/quality/${zeneaId}`)
}

export async function fetchSyncLog(): Promise<SyncLogEntry[]> {
  return request('/api/sync/log')
}

export async function clearSyncLog(): Promise<void> {
  await request('/api/sync/log', { method: 'DELETE' })
}

export async function fetchSyncStatus(): Promise<SyncStatus> {
  return request('/api/sync/status')
}

export async function triggerSync(direction: 'push' | 'pull' | 'full'): Promise<SyncResult> {
  return request(`/api/sync/${direction}`, { method: 'POST' })
}

export async function linkAsset(zeneaId: string, telmaiId: string): Promise<MappedAsset> {
  return request(`/api/assets/${zeneaId}/link`, {
    method: 'POST',
    body: JSON.stringify({ telmai_id: telmaiId }),
  })
}

export async function unlinkAsset(zeneaId: string): Promise<void> {
  await request(`/api/assets/${zeneaId}/link`, { method: 'DELETE' })
}

export async function fetchSettings(): Promise<Record<string, string>> {
  return request('/api/settings')
}

export async function saveSettings(settings: Record<string, string>): Promise<void> {
  await request('/api/settings', {
    method: 'POST',
    body: JSON.stringify(settings),
  })
}

export async function testConnection(service: 'zeenea' | 'telmai'): Promise<ConnectionTestResult> {
  return request(`/api/settings/test/${service}`, { method: 'POST' })
}
