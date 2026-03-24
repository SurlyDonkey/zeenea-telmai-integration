import { useState } from 'react'
import { triggerSync, SyncResult } from '../api/client'

interface SyncButtonProps {
  direction: 'push' | 'pull' | 'full'
  label?: string
  onComplete?: (result: SyncResult) => void
  size?: 'sm' | 'md'
  variant?: 'primary' | 'secondary'
}

export default function SyncButton({
  direction,
  label,
  onComplete,
  size = 'md',
  variant = 'primary',
}: SyncButtonProps) {
  const [loading, setLoading] = useState(false)
  const [flash, setFlash] = useState<'success' | 'error' | null>(null)

  const defaultLabel =
    direction === 'push' ? 'Push to Telmai' : direction === 'pull' ? 'Pull from Telmai' : 'Sync All'

  async function handleClick() {
    setLoading(true)
    setFlash(null)
    try {
      const result = await triggerSync(direction)
      setFlash('success')
      onComplete?.(result)
    } catch {
      setFlash('error')
    } finally {
      setLoading(false)
      setTimeout(() => setFlash(null), 2000)
    }
  }

  const sizeClasses = size === 'sm' ? 'px-3 py-1.5 text-xs' : 'px-4 py-2 text-sm'

  let bgClasses = ''
  if (flash === 'success') {
    bgClasses = 'bg-emerald-600 hover:bg-emerald-700 text-white'
  } else if (flash === 'error') {
    bgClasses = 'bg-red-600 hover:bg-red-700 text-white'
  } else if (variant === 'primary') {
    bgClasses = 'bg-blue-600 hover:bg-blue-700 text-white'
  } else {
    bgClasses = 'bg-white border border-slate-300 text-slate-700 hover:bg-slate-50'
  }

  return (
    <button
      onClick={handleClick}
      disabled={loading}
      className={`inline-flex items-center gap-1.5 rounded-lg font-medium transition-colors disabled:opacity-60 disabled:cursor-not-allowed ${sizeClasses} ${bgClasses}`}
    >
      {loading ? (
        <>
          <span className="inline-block w-3 h-3 border-2 border-current border-t-transparent rounded-full animate-spin" />
          Syncing…
        </>
      ) : flash === 'success' ? (
        <>✓ Done</>
      ) : flash === 'error' ? (
        <>✗ Error</>
      ) : (
        <>
          {direction === 'push' ? '→' : direction === 'pull' ? '←' : '⇄'}{' '}
          {label ?? defaultLabel}
        </>
      )}
    </button>
  )
}
