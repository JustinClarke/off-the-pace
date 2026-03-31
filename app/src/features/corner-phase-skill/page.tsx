import FeaturePage from '../../ui/layout/FeaturePage'
import { RankedTable } from '../../ui/charts'
import type { RankedTableColumn } from '../../ui/charts'
import { methodologyContent, methodologyHref } from './methodology'
import { useQuery } from '../../data/hooks/useQuery'
import { useFilters } from '../../state/FilterContext'
import { transform, toCsvRows } from './transform'
import './queries'
import type { CornerPhaseResult } from './transform'

function zClass(v: unknown): string | undefined {
  const n = v as number
  if (n <= -0.25) return 'text-emerald-400'
  if (n >= 0.25) return 'text-red-400'
  return undefined
}

function fmtZ(v: unknown): string {
  const n = v as number
  return (n >= 0 ? '+' : '') + n.toFixed(2)
}

function fmtIndex(v: unknown): string {
  const n = v as number
  return (n >= 0 ? '+' : '') + n.toFixed(2)
}

const columns: RankedTableColumn<CornerPhaseResult>[] = [
  { key: 'rank', header: '#', align: 'right' },
  { key: 'driver_id', header: 'Driver', align: 'left' },
  {
    key: 'braking_skill_z',
    header: 'Braking (z)',
    align: 'right',
    render: fmtZ,
    cellClass: zClass,
  },
  {
    key: 'mid_corner_skill_z',
    header: 'Mid-corner (z)',
    align: 'right',
    render: fmtZ,
    cellClass: zClass,
  },
  {
    key: 'exit_skill_z',
    header: 'Exit (z)',
    align: 'right',
    render: fmtZ,
    cellClass: zClass,
  },
  {
    key: 'corner_skill_index',
    header: 'Skill Index',
    align: 'right',
    render: fmtIndex,
    cellClass: zClass,
  },
  { key: 'mapped_corners', header: 'Corners', align: 'right' },
]

export default function CornerPhaseSkillPage() {
  const { season } = useFilters()

  const { data, isLoading, error } = useQuery<CornerPhaseResult[]>(
    'corner-phase-skill.season',
    { season }
  )

  const result = data ? transform(data) : null

  return (
    <FeaturePage
      title="Corner-Phase Skill"
      hook="Which drivers gain time at entry, apex, or exit ranked by skill in equal machinery? Car effect is removed before scoring so fast cars don't inflate their drivers' rankings."
      badges={[
        {
          label: 'What It Means',
          content: 'Negative z-scores = faster than field average for that phase (after removing the car effect). Skill Index sums all three phases. Lower = faster overall corner driver.',
        },
        {
          label: 'Why It Matters',
          content: 'Without car-effect removal, rankings reflect car speed, not driver skill Stroll and Verstappen appear near Alonso and Hamilton because of machinery, not technique. Ghost-car recombination lets you see who is actually fast in corners regardless of which car they drive.',
        },
        {
          label: "How It's Calculated",
          content: 'For each corner, the model subtracts the car\'s average geometry (braking point, apex speed, throttle point) from the driver\'s actual geometry. The residual is the driver\'s personal deviation from their machinery. Each phase is then z-scored across the field and summed. SC / VSC / pit / inaccurate laps are excluded. Minimum 100 mapped corners per driver.',
        },
      ]}
      methodology={methodologyContent}
      methodologyHref={methodologyHref}
      provenance={{ dataWindow: '2018–2024' }}
      csvRows={result ? toCsvRows(result) : undefined}
      csvFilename={`corner-phase-skill-${season}.csv`}
      isLoading={isLoading}
      error={error}
      isEmpty={!isLoading && result?.length === 0}
    >
      {result && result.length > 0 && (
        <section className="rounded-xl border border-border bg-white/[0.015] p-4 sm:p-5">
          <h2 className="text-sm font-semibold tracking-tight mb-1">
            Corner-phase skill · {season} season
          </h2>
          <p className="text-xs text-muted mb-3">
            Negative z-score = faster than field average (car effect removed). Ranked by Skill Index (lower = faster).
          </p>
          <RankedTable rows={result} columns={columns} />
        </section>
      )}
    </FeaturePage>
  )
}
