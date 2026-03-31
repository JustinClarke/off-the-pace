import FeaturePage from '../../ui/layout/FeaturePage'
import RankedTable from '../../ui/charts/RankedTable'
import { methodologyContent, methodologyHref } from './methodology'
import { useQuery } from '../../data/hooks/useQuery'
import { transform, toCsvRows } from './transform'
import type { WetSpecialistRow } from './transform'
import './queries'
import type { WetRaceRow } from './queries'

const TIER_BADGE: Record<string, string> = {
  'specialist':    'bg-blue-500/20 text-blue-300',
  'slight-edge':   'bg-white/10 text-muted',
  'dry-preferred': 'bg-orange-500/20 text-orange-300',
}

function fmt(s: number) {
  return `${s >= 0 ? '+' : ''}${s.toFixed(3)}s`
}

export default function WetRaceSpecialistPage() {
  const { data, isLoading, error } = useQuery<WetRaceRow[]>(
    'wet-race.career',
    undefined
  )

  const result = data ? transform(data) : null

  return (
    <FeaturePage
      title="Wet-Race Specialist"
      hook="Who actually gets better when it rains? Comparing each driver's skill residual in wet versus dry races controlling for car, tyres, and conditions isolates the drivers who adapt best to unpredictable grip."
      badges={[
        {
          label: 'What It Means',
          content: 'Positive wet advantage = the driver\'s race residual is better (faster) in wet conditions than their dry baseline. Controls for car pace, tyre compound, and ambient conditions.',
        },
        {
          label: 'Why It Matters',
          content: 'Rain removes much of the car\'s aero advantage, so driver feel and adaptability become decisive. This shows who genuinely improves relative to their dry norm, not just who happens to win in the rain.',
        },
        {
          label: "How It's Calculated",
          content: 'Aggregated over 2018–2024. Requires ≥4 wet races and ≥5 dry races. Estimates are shrunk toward zero by sample size drivers with fewer wet races appear closer to neutral.',
        },
      ]}
      methodology={methodologyContent}
      methodologyHref={methodologyHref}
      provenance={{ dataWindow: '2018–2024', nObs: result?.rows.length }}
      csvRows={result ? toCsvRows(result) : undefined}
      csvFilename="wet-race-specialists.csv"
      isLoading={isLoading}
      error={error}
      isEmpty={result?.rows.length === 0}
    >
      {result && (
        <RankedTable<WetSpecialistRow>
          rows={result.rows}
          rowClass={r => r.sample_weight < 0.5 ? 'opacity-50' : undefined}
          columns={[
            { key: 'driver_id', header: 'Driver', align: 'left' },
            {
              key: 'wet_races',
              header: 'Wet races',
              align: 'right',
              render: (v, row) => {
                const n = v as number
                const cls = row.sample_weight >= 0.6
                  ? 'text-green-400'
                  : row.sample_weight >= 0.5
                  ? 'text-yellow-400'
                  : 'text-muted'
                return <span className={cls}>{n}</span>
              },
            },
            {
              key: 'wet_skill_s',
              header: 'Wet skill',
              align: 'right',
              render: v => fmt(v as number),
              cellClass: v => (v as number) > 0 ? 'text-green-400' : 'text-red-400',
            },
            {
              key: 'dry_skill_s',
              header: 'Dry skill',
              align: 'right',
              render: v => fmt(v as number),
              cellClass: v => (v as number) > 0 ? 'text-green-400' : 'text-red-400',
            },
            {
              key: 'wet_advantage_s',
              header: 'Wet advantage',
              align: 'right',
              render: v => fmt(v as number),
              cellClass: v => {
                const s = v as number
                if (s > 0.3)  return 'text-blue-400'
                if (s < -0.3) return 'text-orange-400'
                return 'text-[rgb(var(--color-text))]'
              },
            },
            {
              key: 'tier',
              header: 'Tier',
              align: 'center',
              render: v => (
                <span className={`px-2 py-0.5 rounded text-xs font-sans uppercase tracking-wide ${TIER_BADGE[v as string]}`}>
                  {(v as string).replace('-', ' ')}
                </span>
              ),
            },
          ]}
          sortKey="wet_advantage_s"
          sortDir="desc"
        />
      )}
    </FeaturePage>
  )
}
