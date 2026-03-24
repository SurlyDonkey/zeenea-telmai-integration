import { useEffect, useState } from 'react'
import { fetchSettings, saveSettings, testConnection, ConnectionTestResult } from '../api/client'

interface FormState {
  zeenea_url: string
  zeenea_api_key: string
  telmai_url: string
  telmai_token: string
}

interface TestState {
  zeenea: ConnectionTestResult | null
  telmai: ConnectionTestResult | null
}

export default function Settings() {
  const [form, setForm] = useState<FormState>({
    zeenea_url: '',
    zeenea_api_key: '',
    telmai_url: '',
    telmai_token: '',
  })
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)
  const [testing, setTesting] = useState<{ zeenea: boolean; telmai: boolean }>({
    zeenea: false,
    telmai: false,
  })
  const [testResults, setTestResults] = useState<TestState>({ zeenea: null, telmai: null })
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    async function load() {
      try {
        const settings = await fetchSettings()
        setForm({
          zeenea_url: settings.zeenea_url ?? '',
          zeenea_api_key: settings.zeenea_api_key ?? '',
          telmai_url: settings.telmai_url ?? '',
          telmai_token: settings.telmai_token ?? '',
        })
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
      await saveSettings(form)
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

      {/* Zeenea Section */}
      <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6 mb-6">
        <div className="flex items-center gap-2 mb-5">
          <span className="text-xl">🌐</span>
          <h2 className="font-semibold text-slate-800 text-lg">Zeenea Data Catalog</h2>
        </div>

        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">GraphQL URL</label>
            <input
              type="url"
              value={form.zeenea_url}
              onChange={e => handleChange('zeenea_url', e.target.value)}
              placeholder="https://your-tenant.zeenea.app/api/graphql"
              className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">API Key</label>
            <input
              type="password"
              value={form.zeenea_api_key}
              onChange={e => handleChange('zeenea_api_key', e.target.value)}
              placeholder="your_zeenea_api_key"
              className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            />
          </div>
        </div>

        <div className="mt-4 flex items-center gap-3">
          <button
            onClick={() => handleTest('zeenea')}
            disabled={testing.zeenea}
            className="px-4 py-2 text-sm rounded-lg border border-slate-300 bg-white text-slate-700 hover:bg-slate-50 disabled:opacity-50 font-medium transition-colors"
          >
            {testing.zeenea ? 'Testing…' : 'Test Connection'}
          </button>
          {testResults.zeenea && (
            <div className={`flex items-center gap-1.5 text-sm ${testResults.zeenea.success ? 'text-emerald-700' : 'text-red-700'}`}>
              <span>{testResults.zeenea.success ? '✓' : '✗'}</span>
              <span>{testResults.zeenea.message}</span>
              {testResults.zeenea.dataset_count !== null && (
                <span className="text-slate-500">({testResults.zeenea.dataset_count} datasets)</span>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Telmai Section */}
      <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6 mb-6">
        <div className="flex items-center gap-2 mb-5">
          <span className="text-xl">🔍</span>
          <h2 className="font-semibold text-slate-800 text-lg">Telmai Data Quality</h2>
        </div>

        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">Base URL</label>
            <input
              type="url"
              value={form.telmai_url}
              onChange={e => handleChange('telmai_url', e.target.value)}
              placeholder="https://api.telm.ai/v1"
              className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">Token</label>
            <input
              type="password"
              value={form.telmai_token}
              onChange={e => handleChange('telmai_token', e.target.value)}
              placeholder="your_telmai_token"
              className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            />
          </div>
        </div>

        <div className="mt-4 flex items-center gap-3">
          <button
            onClick={() => handleTest('telmai')}
            disabled={testing.telmai}
            className="px-4 py-2 text-sm rounded-lg border border-slate-300 bg-white text-slate-700 hover:bg-slate-50 disabled:opacity-50 font-medium transition-colors"
          >
            {testing.telmai ? 'Testing…' : 'Test Connection'}
          </button>
          {testResults.telmai && (
            <div className={`flex items-center gap-1.5 text-sm ${testResults.telmai.success ? 'text-emerald-700' : 'text-red-700'}`}>
              <span>{testResults.telmai.success ? '✓' : '✗'}</span>
              <span>{testResults.telmai.message}</span>
              {testResults.telmai.dataset_count !== null && (
                <span className="text-slate-500">({testResults.telmai.dataset_count} datasets)</span>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Save */}
      <div className="flex items-center gap-4">
        <button
          onClick={handleSave}
          disabled={saving}
          className="px-6 py-2.5 bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium rounded-lg disabled:opacity-50 transition-colors"
        >
          {saving ? 'Saving…' : 'Save Settings'}
        </button>
        {saved && (
          <span className="text-emerald-600 text-sm font-medium">✓ Settings saved</span>
        )}
      </div>
    </div>
  )
}
