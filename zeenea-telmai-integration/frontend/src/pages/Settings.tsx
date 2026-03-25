import { useEffect, useState } from 'react'
import { fetchSettings, saveSettings, testConnection, ConnectionTestResult, fetchSchedulerConfig, saveSchedulerConfig, SchedulerConfig } from '../api/client'

interface FormState {
  zeenea_url: string
  zeenea_api_key: string
  telmai_endpoint: string
  telmai_tenant: string
  telmai_username: string
  telmai_password: string
  telmai_client_id: string
  telmai_auth_endpoint: string
}

interface WebhookConfig {
  webhook_url: string
  signature_header: string
  signature_format: string
  secret_configured: boolean
  payload_example: Record<string, string>
}

interface TestState {
  zeenea: ConnectionTestResult | null
  telmai: ConnectionTestResult | null
}

function Field({
  label, value, onChange, placeholder, type = 'text', hint,
}: {
  label: string
  value: string
  onChange: (v: string) => void
  placeholder?: string
  type?: string
  hint?: string
}) {
  return (
    <div>
      <label className="block text-sm font-medium text-slate-700 mb-1">{label}</label>
      {hint && <p className="text-xs text-slate-400 mb-1">{hint}</p>}
      <input
        type={type}
        value={value}
        onChange={e => onChange(e.target.value)}
        placeholder={placeholder}
        className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
      />
    </div>
  )
}

export default function Settings() {
  const [form, setForm] = useState<FormState>({
    zeenea_url: '',
    zeenea_api_key: '',
    telmai_endpoint: '',
    telmai_tenant: '',
    telmai_username: '',
    telmai_password: '',
    telmai_client_id: '',
    telmai_auth_endpoint: '',
  })
  const [webhookConfig, setWebhookConfig] = useState<WebhookConfig | null>(null)
  const [copied, setCopied] = useState(false)
  const [schedulerConfig, setSchedulerConfig] = useState<SchedulerConfig | null>(null)
  const [intervalHours, setIntervalHours] = useState<number>(4)
  const [savingScheduler, setSavingScheduler] = useState(false)
  const [schedulerSaved, setSchedulerSaved] = useState(false)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)
  const [testing, setTesting] = useState({ zeenea: false, telmai: false })
  const [testResults, setTestResults] = useState<TestState>({ zeenea: null, telmai: null })
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    async function load() {
      try {
        const [settings, wh, sched] = await Promise.all([
          fetchSettings(),
          fetch('/api/webhooks/telmai/config').then(r => r.json()).catch(() => null),
          fetchSchedulerConfig().catch(() => null),
        ])
        setForm({
          zeenea_url:           settings.zeenea_url          ?? '',
          zeenea_api_key:       settings.zeenea_api_key      ?? '',
          telmai_endpoint:      settings.telmai_endpoint      ?? '',
          telmai_tenant:        settings.telmai_tenant        ?? '',
          telmai_username:      settings.telmai_username      ?? '',
          telmai_password:      settings.telmai_password      ?? '',
          telmai_client_id:     settings.telmai_client_id     ?? '',
          telmai_auth_endpoint: settings.telmai_auth_endpoint ?? '',
        })
        if (wh) setWebhookConfig(wh)
        if (sched) { setSchedulerConfig(sched); setIntervalHours(sched.interval_hours) }
      } catch (e: any) {
        setError(e.message)
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [])

  function handleChange(key: keyof FormState, value: string) {
    setForm(prev => ({ ...prev, [key]: value }))
    setSaved(false)
    setTestResults({ zeenea: null, telmai: null })
  }

  async function handleSave() {
    setSaving(true)
    setError(null)
    try {
      await saveSettings(form as any)
      setSaved(true)
      setTimeout(() => setSaved(false), 3000)
    } catch (e: any) {
      setError(e.message)
    } finally {
      setSaving(false)
    }
  }

  async function handleTest(service: 'zeenea' | 'telmai') {
    setTesting(prev => ({ ...prev, [service]: true }))
    setTestResults(prev => ({ ...prev, [service]: null }))
    try {
      const result = await testConnection(service)
      setTestResults(prev => ({ ...prev, [service]: result }))
    } catch (e: any) {
      setTestResults(prev => ({
        ...prev,
        [service]: { service, success: false, message: e.message, dataset_count: null },
      }))
    } finally {
      setTesting(prev => ({ ...prev, [service]: false }))
    }
  }

  async function handleSaveScheduler() {
    setSavingScheduler(true)
    try {
      const updated = await saveSchedulerConfig(intervalHours)
      setSchedulerConfig(updated)
      setSchedulerSaved(true)
      setTimeout(() => setSchedulerSaved(false), 3000)
    } catch (e: any) {
      setError(e.message)
    } finally {
      setSavingScheduler(false)
    }
  }

  function copyWebhookUrl() {
    if (webhookConfig?.webhook_url) {
      navigator.clipboard.writeText(webhookConfig.webhook_url)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    }
  }

  if (loading) {
    return (
      <div className="p-8 flex items-center justify-center">
        <div className="inline-block w-6 h-6 border-2 border-slate-300 border-t-blue-500 rounded-full animate-spin" />
      </div>
    )
  }

  return (
    <div className="p-8 max-w-2xl">
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-slate-900">Settings</h1>
        <p className="text-slate-500 text-sm mt-1">
          Configure your Zeenea and Telmai API connections
        </p>
      </div>

      <div className="mb-4 p-3 bg-blue-50 border border-blue-200 rounded-lg text-sm text-blue-800">
        Config is loaded from <code className="font-mono bg-blue-100 px-1 rounded">.env</code> — changes here override environment variables for the current session only.
      </div>

      {error && (
        <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">
          {error}
        </div>
      )}

      {/* Zeenea */}
      <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6 mb-6">
        <div className="flex items-center gap-2 mb-5">
          <span className="text-xl">🌐</span>
          <h2 className="font-semibold text-slate-800 text-lg">Zeenea Data Catalog</h2>
        </div>
        <div className="space-y-4">
          <Field label="GraphQL URL" value={form.zeenea_url}
            onChange={v => handleChange('zeenea_url', v)}
            placeholder="https://your-tenant.zeenea.app/api/catalog/graphql" type="url" />
          <Field label="API Key" value={form.zeenea_api_key}
            onChange={v => handleChange('zeenea_api_key', v)}
            placeholder="your_zeenea_api_key" type="password"
            hint="Sent as X-API-SECRET header" />
        </div>
        <div className="mt-4 flex items-center gap-3">
          <button onClick={() => handleTest('zeenea')} disabled={testing.zeenea}
            className="px-4 py-2 text-sm rounded-lg border border-slate-300 bg-white text-slate-700 hover:bg-slate-50 disabled:opacity-50 font-medium transition-colors">
            {testing.zeenea ? 'Testing…' : 'Test Connection'}
          </button>
          {testResults.zeenea && (
            <span className={`flex items-center gap-1.5 text-sm ${testResults.zeenea.success ? 'text-emerald-700' : 'text-red-700'}`}>
              {testResults.zeenea.success ? '✓' : '✗'} {testResults.zeenea.message}
              {testResults.zeenea.dataset_count != null && (
                <span className="text-slate-500">({testResults.zeenea.dataset_count} datasets)</span>
              )}
            </span>
          )}
        </div>
      </div>

      {/* Telmai */}
      <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6 mb-6">
        <div className="flex items-center gap-2 mb-5">
          <span className="text-xl">🔍</span>
          <h2 className="font-semibold text-slate-800 text-lg">Telmai Data Quality</h2>
        </div>
        <div className="space-y-4">
          <Field label="Endpoint" value={form.telmai_endpoint}
            onChange={v => handleChange('telmai_endpoint', v)}
            placeholder="https://app.telm.ai" type="url"
            hint="Base URL of your Telmai deployment" />
          <Field label="Tenant" value={form.telmai_tenant}
            onChange={v => handleChange('telmai_tenant', v)}
            placeholder="your_tenant_name"
            hint="Your Telmai tenant identifier" />
          <div className="grid grid-cols-2 gap-4">
            <Field label="Username" value={form.telmai_username}
              onChange={v => handleChange('telmai_username', v)}
              placeholder="your@email.com" />
            <Field label="Password" value={form.telmai_password}
              onChange={v => handleChange('telmai_password', v)}
              placeholder="••••••••" type="password" />
          </div>
          <div className="grid grid-cols-2 gap-4">
            <Field label="Client ID" value={form.telmai_client_id}
              onChange={v => handleChange('telmai_client_id', v)}
              placeholder="telmai"
              hint="OAuth2 client ID (default: telmai)" />
            <Field label="Auth Endpoint" value={form.telmai_auth_endpoint}
              onChange={v => handleChange('telmai_auth_endpoint', v)}
              placeholder="(same as endpoint)"
              hint="Leave blank to use Endpoint" />
          </div>
        </div>
        <div className="mt-4 flex items-center gap-3">
          <button onClick={() => handleTest('telmai')} disabled={testing.telmai}
            className="px-4 py-2 text-sm rounded-lg border border-slate-300 bg-white text-slate-700 hover:bg-slate-50 disabled:opacity-50 font-medium transition-colors">
            {testing.telmai ? 'Testing…' : 'Test Connection'}
          </button>
          {testResults.telmai && (
            <span className={`flex items-center gap-1.5 text-sm ${testResults.telmai.success ? 'text-emerald-700' : 'text-red-700'}`}>
              {testResults.telmai.success ? '✓' : '✗'} {testResults.telmai.message}
              {testResults.telmai.dataset_count != null && (
                <span className="text-slate-500">({testResults.telmai.dataset_count} datasets)</span>
              )}
            </span>
          )}
        </div>
      </div>

      {/* Webhook */}
      <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6 mb-6">
        <div className="flex items-center gap-2 mb-1">
          <span className="text-xl">⚡</span>
          <h2 className="font-semibold text-slate-800 text-lg">Telmai Webhook</h2>
          {webhookConfig && (
            <span className={`ml-auto text-xs px-2 py-0.5 rounded-full font-medium ${webhookConfig.secret_configured ? 'bg-emerald-100 text-emerald-700' : 'bg-amber-100 text-amber-700'}`}>
              {webhookConfig.secret_configured ? '🔒 Secret configured' : '⚠ No secret (open)'}
            </span>
          )}
        </div>
        <p className="text-sm text-slate-500 mb-5">
          Point Telmai's webhook at this URL. When a scan completes, alerts are immediately fetched and written back to Zeenea — no waiting for the 4-hour scheduled sync.
        </p>

        {webhookConfig ? (
          <div className="space-y-4">
            {/* Webhook URL */}
            <div>
              <label className="block text-xs font-medium text-slate-500 uppercase tracking-wide mb-1">
                Webhook URL — paste this into Telmai
              </label>
              <div className="flex items-center gap-2">
                <code className="flex-1 px-3 py-2 bg-slate-50 border border-slate-200 rounded-lg text-sm font-mono text-slate-700 truncate">
                  {webhookConfig.webhook_url}
                </code>
                <button onClick={copyWebhookUrl}
                  className="px-3 py-2 text-xs rounded-lg border border-slate-300 bg-white text-slate-600 hover:bg-slate-50 font-medium transition-colors whitespace-nowrap">
                  {copied ? '✓ Copied' : 'Copy'}
                </button>
              </div>
            </div>

            {/* Signature */}
            <div className="grid grid-cols-2 gap-4 text-sm">
              <div>
                <span className="text-xs font-medium text-slate-500 uppercase tracking-wide">Signature Header</span>
                <code className="block mt-1 px-2 py-1 bg-slate-50 rounded text-xs font-mono">
                  {webhookConfig.signature_header}
                </code>
              </div>
              <div>
                <span className="text-xs font-medium text-slate-500 uppercase tracking-wide">Format</span>
                <code className="block mt-1 px-2 py-1 bg-slate-50 rounded text-xs font-mono">
                  {webhookConfig.signature_format}
                </code>
              </div>
            </div>

            {/* Payload example */}
            <div>
              <span className="text-xs font-medium text-slate-500 uppercase tracking-wide">Expected Payload</span>
              <pre className="mt-1 px-3 py-2 bg-slate-900 text-emerald-400 rounded-lg text-xs overflow-auto">
                {JSON.stringify(webhookConfig.payload_example, null, 2)}
              </pre>
            </div>

            {/* Secret instructions */}
            <div className={`p-3 rounded-lg text-sm border ${webhookConfig.secret_configured ? 'bg-emerald-50 border-emerald-200 text-emerald-800' : 'bg-amber-50 border-amber-200 text-amber-800'}`}>
              {webhookConfig.secret_configured
                ? '✓ HMAC-SHA256 signature verification is active. Requests without a valid X-Telmai-Signature header will be rejected.'
                : '⚠ Set TELMAI_WEBHOOK_SECRET in your .env file to enable signature verification. Without it, anyone can call this endpoint.'}
            </div>
          </div>
        ) : (
          <div className="text-sm text-slate-400">Loading webhook configuration…</div>
        )}
      </div>

      {/* Scheduler */}
      <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6 mb-6">
        <div className="flex items-center gap-2 mb-1">
          <span className="text-xl">⏱</span>
          <h2 className="font-semibold text-slate-800 text-lg">Auto-Sync Schedule</h2>
          {schedulerConfig && (
            <span className={`ml-auto text-xs px-2 py-0.5 rounded-full font-medium ${schedulerConfig.is_running ? 'bg-emerald-100 text-emerald-700' : 'bg-slate-100 text-slate-500'}`}>
              {schedulerConfig.is_running ? '● Running' : '○ Stopped'}
            </span>
          )}
        </div>
        <p className="text-sm text-slate-500 mb-5">
          How often the integration automatically runs a full push + pull sync. Changes take effect immediately.
        </p>

        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">
              Sync interval
            </label>
            <div className="flex items-center gap-3">
              <input
                type="number"
                min={0.25}
                max={168}
                step={0.25}
                value={intervalHours}
                onChange={e => setIntervalHours(parseFloat(e.target.value) || 4)}
                className="w-32 px-3 py-2 border border-slate-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
              <span className="text-sm text-slate-500">hours</span>
              <span className="text-xs text-slate-400">(min 0.25 · max 168)</span>
            </div>
            {/* Quick presets */}
            <div className="flex gap-2 mt-2">
              {[1, 4, 12, 24].map(h => (
                <button
                  key={h}
                  onClick={() => setIntervalHours(h)}
                  className={`px-2 py-1 text-xs rounded border transition-colors ${intervalHours === h ? 'bg-blue-600 text-white border-blue-600' : 'bg-white text-slate-600 border-slate-300 hover:bg-slate-50'}`}
                >
                  {h}h
                </button>
              ))}
            </div>
          </div>

          {schedulerConfig?.next_run && (
            <p className="text-xs text-slate-400">
              Next run: {new Date(schedulerConfig.next_run).toLocaleString()}
            </p>
          )}
        </div>

        <div className="mt-4 flex items-center gap-3">
          <button
            onClick={handleSaveScheduler}
            disabled={savingScheduler}
            className="px-4 py-2 text-sm rounded-lg bg-blue-600 hover:bg-blue-700 text-white font-medium disabled:opacity-50 transition-colors"
          >
            {savingScheduler ? 'Saving…' : 'Update Schedule'}
          </button>
          {schedulerSaved && (
            <span className="text-emerald-600 text-sm font-medium">✓ Schedule updated</span>
          )}
        </div>
      </div>

      {/* Save */}
      <div className="flex items-center gap-4">
        <button onClick={handleSave} disabled={saving}
          className="px-6 py-2.5 bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium rounded-lg disabled:opacity-50 transition-colors">
          {saving ? 'Saving…' : 'Save Settings'}
        </button>
        {saved && (
          <span className="text-emerald-600 text-sm font-medium">✓ Settings saved</span>
        )}
      </div>
    </div>
  )
}
