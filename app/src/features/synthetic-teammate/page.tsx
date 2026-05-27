import FeaturePage from '../../ui/layout/FeaturePage'
import RankedTable from '../../ui/charts/RankedTable'
import { methodologyContent, methodologyHref } from './methodology'
import { useQuery } from '../../data/hooks/useQuery'
import { useFilters } from '../../state/FilterContext'
import { transform, toCsvRows } from './transform'
import './queries'
import type { SyntheticTmRow } from './queries'

const VERDICT_BADGE: Record<string, string> = {
  ahead:  'bg-green-500/20 text-green-300',
  even:   'bg-white/10 text-muted',
  behind: 'bg-red-500/20 text-red-300',
}

function fmt(s: number) {
  return `${s >= 0 ? '+' : ''}${s.toFixed(3)}s`
}

export default function SyntheticTeammatePage() {
  const { season } = useFilters()
  const { data, isLoading, error } = useQuery<SyntheticTmRow[]>(
    'synthetic-teammate.season',
    { season }
  )

  const result = data ? transform(data) : null

  return (
    <FeaturePage
      title="Synthetic Teammate"
      hook="Which driver would be faster with an identical car, in the same race, lap for lap? The synthetic teammate adjusts for strategic divergence and tyre position so the comparison reflects pure pace, not timing luck."
      badges={[
        {
          label: 'What It Means',
          content: 'Skill proxy < 0: the driver is faster than their synthetic benchmark. Proxy > 0: they would be slower in a controlled head-to-head against the same car.',
        },
        {
          label: 'Why It Matters',
          content: 'The "synthetic teammate" reconstructs what the teammate\'s pace would be on an identical strategy. Strategic divergence laps are excluded. Only non-divergent, comparable laps count.',
        },
        {
          label: "How It's Calculated",
          content: 'The quality weight reflects how comparable the laps are similar tyre age, race position, fuel load. Low-confidence races are included but down-weighted in the average.',
        },
      ]}
      methodology={methodologyContent}
      methodologyHref={methodologyHref}
      provenance={{ dataWindow: '2018–2024', nObs: result?.points.length }}
      csvRows={result ? toCsvRows(result) : undefined}
      csvFilename={`synthetic-teammate-${season}.csv`}
      isLoading={isLoading}
      error={error}
      isEmpty={result?.points.length === 0}
    >
      {result && (
        <RankedTable
          rows={result.points}
          columns={[
            { key: 'driver_id',          header: 'Driver',     align: 'left' },
            { key: 'teammate_driver_id', header: 'vs (tm)',     align: 'left' },
            { key: 'constructor_id',     header: 'Constructor', align: 'left' },
            { key: 'n_races',            header: 'Races',       align: 'right' },
            {
              key: 'avg_skill_proxy_s',
              header: 'Skill proxy',
              align: 'right',
              render: v => fmt(v as number),
              cellClass: v => (v as number) < -0.1 ? 'text-green-400' : (v as number) > 0.1 ? 'text-red-400' : '',
            },
            {
              key: 'avg_quality_weight',
              header: 'Confidence',
              align: 'right',
              render: v => `${((v as number) * 100).toFixed(0)}%`,
            },
            {
              key: 'verdict',
              header: 'Verdict',
              align: 'center',
              render: v => (
                <span className={`px-2 py-0.5 rounded text-xs font-sans uppercase tracking-wide ${VERDICT_BADGE[v as string]}`}>
                  {v as string}
                </span>
              ),
            },
          ]}
          sortKey="avg_skill_proxy_s"
          sortDir="asc"
        />
      )}
    </FeaturePage>
  )
}
