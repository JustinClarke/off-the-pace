import FeaturePage from '../../ui/layout/FeaturePage'
import RankedTable from '../../ui/charts/RankedTable'
import { methodologyContent, methodologyHref } from './methodology'
import { useQuery } from '../../data/hooks/useQuery'
import { useFilters } from '../../state/FilterContext'
import { transform, toCsvRows } from './transform'
import './queries'
import type { EraTranslatorRow } from './queries'
import { TechTooltip } from '../../ui/TechTooltip'

function fmtRating(v: number) {
  return `${v >= 0 ? '+' : ''}${v.toFixed(3)}s`
}

function ratingClass(v: unknown) {
  const s = v as number
  if (s < -3)   return 'text-green-300'
  if (s < -1.5) return 'text-green-400'
  if (s > 0.5)  return 'text-red-400'
  return 'text-[rgb(var(--color-text))]'
}

export default function EraTranslatorPage() {
  const { season } = useFilters()
  const { data, isLoading, error } = useQuery<EraTranslatorRow[]>(
    'era-translator.season',
    { season }
  )

  const result = data ? transform(data) : null

  return (
    <FeaturePage
      title="Era Translator"
      hook="How fast was Hamilton in 2020, measured on the same scale as Verstappen in 2024? Era-adjusted ratings anchor every season to a common baseline using bridge drivers who raced across the 2022 regulation boundary."
      badges={[
        {
          label: 'What It Means',
          content: 'Ratings are corrected for the pace baseline shift at the 2022 ground-effect regulation change. A 2018 rating of −2.5s is directly comparable to a 2024 rating of −2.5s.',
        },
        {
          label: 'Why It Matters',
          content: 'Drivers marked ★ raced on both sides of the 2022 regulation boundary. Their consistent performance anchors the era correction. More bridge drivers = tighter era uncertainty.',
        },
        {
          label: "How It's Calculated",
          content: 'Wider CI means less certainty fewer races, fewer clean laps, or weaker bridge coverage in that era. The rating is still the best estimate, just with greater spread.',
        },
      ]}
      methodology={methodologyContent}
      methodologyHref={methodologyHref}
      provenance={{ dataWindow: '2018–2024', nObs: result?.rows.length }}
      csvRows={result ? toCsvRows(result) : undefined}
      csvFilename={`era-translator-${season}.csv`}
      isLoading={isLoading}
      error={error}
      isEmpty={result?.rows.length === 0}
    >
      {result && (
        <RankedTable
          rows={result.rows}
          columns={[
            { key: 'rank', header: '#', align: 'right' },
            {
              key: 'driver_id',
              header: 'Driver',
              align: 'left',
              render: (v, row) => (
                <span className="flex items-center gap-1">
                  <span className="font-mono">{v as string}</span>
                  {(row as { bridge_driver_anchor_flag: boolean }).bridge_driver_anchor_flag && (
                    <TechTooltip content="Bridge driver anchor">
                      <span className="text-amber-400/80 text-[10px] cursor-help">★</span>
                    </TechTooltip>
                  )}
                </span>
              ),
            },
            {
              key: 'era_adjusted_rating',
              header: 'Era rating (s)',
              align: 'right',
              render: v => fmtRating(v as number),
              cellClass: ratingClass,
            },
            {
              key: 'ci_low',
              header: '95% CI low',
              align: 'right',
              render: v => fmtRating(v as number),
              cellClass: () => 'text-muted/70',
            },
            {
              key: 'ci_high',
              header: '95% CI high',
              align: 'right',
              render: v => fmtRating(v as number),
              cellClass: () => 'text-muted/70',
            },
            {
              key: 'rating_confidence',
              header: 'Confidence',
              align: 'right',
              render: v => `${((v as number) * 100).toFixed(0)}%`,
            },
            { key: 'n_races', header: 'Races', align: 'right' },
          ]}
        />
      )}
    </FeaturePage>
  )
}
