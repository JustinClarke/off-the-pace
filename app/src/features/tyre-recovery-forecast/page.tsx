import FeaturePage from '../../ui/layout/FeaturePage'
import { RankedTable } from '../../ui/charts'
import type { RankedTableColumn } from '../../ui/charts'
import { methodologyContent, methodologyHref } from './methodology'
import { useQuery } from '../../data/hooks/useQuery'
import { toCsvRows } from './transform'
import './queries'
import type { RecoveryRow } from './queries'

const COMPOUND_COLOR: Record<string, string> = {
  SOFT: '#ef4444',
  MEDIUM: '#eab308',
  HARD: '#cbd5e1',
}

const columns: RankedTableColumn<RecoveryRow>[] = [
  {
    key: 'compound',
    header: 'Compound',
    align: 'left',
    render: (v) => {
      const s = v as string
      return (
        <span className="flex items-center gap-2">
          <span
            className="w-2 h-2 rounded-full flex-shrink-0"
            style={{ backgroundColor: COMPOUND_COLOR[s] ?? '#60a5fa' }}
          />
          {s}
        </span>
      )
    },
  },
  { key: 'post_cliff_laps', header: 'Post-cliff Laps', align: 'right' },
  {
    key: 'recovery_rate_pct',
    header: 'Recovery Rate',
    align: 'right',
    render: (v) => `${(v as number).toFixed(1)}%`,
  },
  {
    key: 'avg_recovery_prob_pct',
    header: 'Avg Probability',
    align: 'right',
    render: (v) => `${(v as number).toFixed(1)}%`,
  },
  {
    key: 'avg_surface_bulk_ratio',
    header: 'Surface/Bulk',
    align: 'right',
    render: (v) => (v as number).toFixed(3),
  },
  {
    key: 'avg_thermal_s',
    header: 'Thermal (s)',
    align: 'right',
    render: (v) => `${(v as number).toFixed(3)}s`,
  },
]

export default function TyreRecoveryForecastPage() {
  const { data, isLoading, error } = useQuery<RecoveryRow[]>(
    'tyre-recovery-forecast.all',
    {}
  )

  return (
    <FeaturePage
      title="Tyre Recovery Forecast"
      hook="After a tyre crosses the degradation cliff, can it recover? The model separates surface thermal wear from bulk mechanical breakdown to estimate whether lifting off pressure would actually bring pace back."
      badges={[
        {
          label: 'What It Means',
          content: 'Recovery Rate is the fraction of post-cliff laps where any pace bounce-back was detected. Avg Probability is the model\'s estimate of the chance of recovery given the observed surface/bulk load balance a more nuanced metric than the binary flag.',
        },
        {
          label: 'Why It Matters',
          content: 'A high recovery probability suggests the tyre is thermally overloaded rather than mechanically spent the driver may be able to recover pace by lifting. Low probability means the bulk compound has degraded and recovery is unlikely regardless of driving style.',
        },
        {
          label: "How It's Calculated",
          content: 'The surface/bulk ratio separates thermal (surface) and mechanical (bulk) components of the push load. Laps with a higher surface share have higher recovery probability. Thermal attribution in seconds estimates how much of the lap time loss is recoverable through pace management.',
        },
      ]}
      methodology={methodologyContent}
      methodologyHref={methodologyHref}
      provenance={{ dataWindow: '2018–2024' }}
      csvRows={data ? toCsvRows(data) : undefined}
      csvFilename="tyre-recovery-forecast.csv"
      isLoading={isLoading}
      error={error}
      isEmpty={!isLoading && data?.length === 0}
    >
      {data && data.length > 0 && (
        <div className="flex flex-col gap-6">
          <section className="rounded-xl border border-border bg-white/[0.015] p-4 sm:p-5">
            <h2 className="text-sm font-semibold tracking-tight mb-1">Post-cliff recovery by compound</h2>
            <p className="text-xs text-muted/70 mb-3">
              All seasons · dry compounds only · laps past cliff onset
            </p>
            <RankedTable rows={data} columns={columns} />
          </section>

          <div className="rounded-xl border border-border/50 bg-amber-500/5 border-amber-500/20 px-4 py-3">
            <p className="text-xs text-amber-300/80">
              <strong>Interpretation note:</strong> The 86–89% recovery rate is high because the model
              detects any positive deviation from the cliff slope, however small. The Avg Probability
              (21–29%) is the more meaningful metric it estimates the actual chance of meaningful
              pace recovery.
            </p>
          </div>
        </div>
      )}
    </FeaturePage>
  )
}
