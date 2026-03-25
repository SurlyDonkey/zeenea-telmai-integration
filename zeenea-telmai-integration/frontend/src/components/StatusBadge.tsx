interface QualityBadgeProps {
  score: number | null
  size?: 'sm' | 'md'
}

export function QualityBadge({ score, size = 'md' }: QualityBadgeProps) {
  if (score === null) {
    return (
      <span className={`inline-flex items-center rounded-full font-medium bg-slate-100 text-slate-500 ${size === 'sm' ? 'px-2 py-0.5 text-xs' : 'px-2.5 py-1 text-sm'}`}>
        N/A
      </span>
    )
  }

  let colorClass = ''
  let label = `${score.toFixed(1)}%`

  if (score >= 80) {
    colorClass = 'bg-emerald-100 text-emerald-700'
  } else if (score >= 60) {
    colorClass = 'bg-yellow-100 text-yellow-700'
  } else {
    colorClass = 'bg-red-100 text-red-700'
  }

  return (
    <span className={`inline-flex items-center rounded-full font-medium ${colorClass} ${size === 'sm' ? 'px-2 py-0.5 text-xs' : 'px-2.5 py-1 text-sm'}`}>
      {label}
    </span>
  )
}

interface StatusBadgeProps {
  status: 'linked' | 'unlinked' | 'syncing' | 'error' | 'success' | 'failed' | 'skipped'
  size?: 'sm' | 'md'
}

export function StatusBadge({ status, size = 'md' }: StatusBadgeProps) {
  const config: Record<string, { label: string; classes: string }> = {
    linked: { label: 'Linked', classes: 'bg-blue-100 text-blue-700' },
    unlinked: { label: 'Unlinked', classes: 'bg-slate-100 text-slate-500' },
    syncing: { label: 'Syncing', classes: 'bg-purple-100 text-purple-700' },
    error: { label: 'Error', classes: 'bg-red-100 text-red-700' },
    success: { label: 'Success', classes: 'bg-emerald-100 text-emerald-700' },
    failed: { label: 'Failed', classes: 'bg-red-100 text-red-700' },
    skipped: { label: 'Skipped', classes: 'bg-slate-100 text-slate-500' },
  }

  const { label, classes } = config[status] ?? { label: status, classes: 'bg-slate-100 text-slate-500' }

  return (
    <span className={`inline-flex items-center rounded-full font-medium ${classes} ${size === 'sm' ? 'px-2 py-0.5 text-xs' : 'px-2.5 py-1 text-sm'}`}>
      {label}
    </span>
  )
}

interface AlertBadgeProps {
  count: number
  size?: 'sm' | 'md'
}

export function AlertBadge({ count, size = 'md' }: AlertBadgeProps) {
  if (count === 0) {
    return (
      <span className={`inline-flex items-center rounded-full font-medium bg-emerald-100 text-emerald-700 ${size === 'sm' ? 'px-2 py-0.5 text-xs' : 'px-2.5 py-1 text-sm'}`}>
        0
      </span>
    )
  }
  const colorClass = count >= 5 ? 'bg-red-100 text-red-700' : 'bg-yellow-100 text-yellow-700'
  return (
    <span className={`inline-flex items-center rounded-full font-medium ${colorClass} ${size === 'sm' ? 'px-2 py-0.5 text-xs' : 'px-2.5 py-1 text-sm'}`}>
      {count}
    </span>
  )
}
