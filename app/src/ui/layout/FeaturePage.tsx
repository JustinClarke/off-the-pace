// Shared chrome for every analytical feature: title, hook, audience panels, methodology drawer,
// provenance footer, CSV export, and standard loading/empty/error states.
import { ReactNode, useState } from 'react'
import * as Dialog from '@radix-ui/react-dialog'
import DataBoundary from '../feedback/DataBoundary'
import { downloadCsv } from '../../lib/csv'
import type { ProvenanceMeta } from '../methodology'

export interface AudienceBadge {
  label: 'What It Means' | 'Why It Matters' | 'How It\'s Calculated'
  content: string
}

interface FeaturePageProps {
  title: string
  hook: string
  badges?: AudienceBadge[]
  /** Methodology drawer body JSX or plain string */
  methodology?: ReactNode
  /** Deep-link into the docs site */
  methodologyHref?: string
  provenance?: ProvenanceMeta
  /** CSV rows emitted when the user clicks "Export CSV" */
  csvRows?: Record<string, unknown>[]
  csvFilename?: string
  /** Query state forwarded from the feature's useQuery call */
  isLoading?: boolean
  error?: Error | null
  isEmpty?: boolean
  children: ReactNode
}

const PANEL_STYLES: Record<string, { tab: string; panel: string }> = {
  'What It Means': {
    tab: 'data-[active=true]:text-blue-400 data-[active=true]:border-b-blue-400',
    panel: 'border-blue-500/20 bg-blue-500/5',
  },
  'Why It Matters': {
    tab: 'data-[active=true]:text-emerald-400 data-[active=true]:border-b-emerald-400',
    panel: 'border-emerald-500/20 bg-emerald-500/5',
  },
  "How It's Calculated": {
    tab: 'data-[active=true]:text-violet-400 data-[active=true]:border-b-violet-400',
    panel: 'border-violet-500/20 bg-violet-500/5',
  },
}

function AudienceTabs({ badges }: { badges: AudienceBadge[] }) {
  const [active, setActive] = useState<string | null>(badges[0]?.label ?? null)

  return (
    <div className="mt-3">
      {/* Tab row */}
      <div className="flex gap-0 border-b border-border">
        {badges.map(b => {
          const isActive = active === b.label
          const styles = PANEL_STYLES[b.label]
          return (
            <button
              key={b.label}
              data-active={isActive}
              onClick={() => setActive(isActive ? null : b.label)}
              className={`text-xs px-3 py-1.5 -mb-px border-b-2 border-transparent text-muted transition-colors hover:text-[rgb(var(--color-text))] ${styles.tab}`}
            >
              {b.label}
            </button>
          )
        })}
      </div>

      {/* Panel */}
      {active && (() => {
        const badge = badges.find(b => b.label === active)!
        const styles = PANEL_STYLES[active]
        return (
          <div className={`text-xs text-muted leading-relaxed px-3 py-2.5 border-x border-b rounded-b ${styles.panel}`}>
            {badge.content}
          </div>
        )
      })()}
    </div>
  )
}

function MethodologyDrawer({
  content,
  href,
}: {
  content: ReactNode
  href?: string
}) {
  return (
    <Dialog.Root>
      <Dialog.Trigger asChild>
        <button className="text-xs text-muted hover:text-accent transition-colors underline underline-offset-2">
          How this is calculated →
        </button>
      </Dialog.Trigger>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 bg-black/50 z-40" />
        <Dialog.Content style={{ backgroundColor: 'rgb(var(--color-bg))' }} className="fixed right-0 top-0 h-full w-full max-w-md border-l border-border z-50 overflow-y-auto p-6 flex flex-col gap-4">
          <div className="flex items-center justify-between">
            <Dialog.Title className="text-base font-semibold">Methodology</Dialog.Title>
            <Dialog.Close className="text-muted hover:text-[rgb(var(--color-text))] transition-colors text-lg leading-none">
              ×
            </Dialog.Close>
          </div>
          <div className="text-sm text-muted leading-relaxed prose prose-invert prose-sm max-w-none">
            {content}
          </div>
          {href && (
            <a
              href={href}
              target="_blank"
              rel="noopener noreferrer"
              className="mt-auto text-xs text-accent hover:underline"
            >
              Full reference documentation →
            </a>
          )}
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  )
}

function ProvenanceFooter({ meta }: { meta: ProvenanceMeta }) {
  const parts: string[] = []
  if (meta.fitDate) parts.push(`fit ${meta.fitDate}`)
  if (meta.dataWindow) parts.push(meta.dataWindow)
  if (meta.nObs !== undefined) parts.push(`n=${meta.nObs.toLocaleString()}`)
  if (meta.modelVersion) parts.push(`v${meta.modelVersion}`)
  if (meta.datasetFingerprint) parts.push(`sha:${meta.datasetFingerprint.slice(0, 8)}`)
  if (!parts.length) return null
  return (
    <p className="text-xs text-muted/60 font-mono">
      {parts.join(' · ')}
    </p>
  )
}

export default function FeaturePage({
  title,
  hook,
  badges,
  methodology,
  methodologyHref,
  provenance,
  csvRows,
  csvFilename,
  isLoading,
  error,
  isEmpty,
  children,
}: FeaturePageProps) {
  return (
    <div className="max-w-5xl mx-auto px-6 py-10 flex flex-col gap-6">
      {/* Header */}
      <div className="flex flex-col gap-1">
        <h1 className="text-2xl font-bold tracking-tight">{title}</h1>
        <p className="text-muted text-sm leading-relaxed max-w-2xl">{hook}</p>
        {badges && badges.length > 0 && <AudienceTabs badges={badges} />}
      </div>

      {/* Chart slot */}
      <DataBoundary isLoading={isLoading ?? false} error={error ?? null} isEmpty={isEmpty}>
        {children}
      </DataBoundary>

      {/* Footer: methodology + provenance + CSV */}
      <div className="flex flex-wrap items-center justify-between gap-3 pt-2 border-t border-border">
        <div className="flex flex-wrap items-center gap-4">
          {methodology && (
            <MethodologyDrawer content={methodology} href={methodologyHref} />
          )}
          {provenance && <ProvenanceFooter meta={provenance} />}
        </div>

        {csvRows && csvRows.length > 0 && (
          <button
            onClick={() => downloadCsv(csvFilename ?? `${title.toLowerCase().replace(/\s+/g, '-')}.csv`, csvRows)}
            className="text-xs px-3 py-1.5 rounded border border-border text-muted hover:text-[rgb(var(--color-text))] hover:border-accent transition-colors"
          >
            Export CSV
          </button>
        )}
      </div>
    </div>
  )
}
