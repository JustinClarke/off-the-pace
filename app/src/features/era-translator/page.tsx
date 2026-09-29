import FeaturePage from '../../ui/layout/FeaturePage'
import RankedTable from '../../ui/charts/RankedTable'
import { methodologyContent, methodologyHref } from './methodology'
import { useQuery } from '../../data/hooks/useQuery'
import { useFilters } from '../../state/FilterContext'
import { transform, toCsvRows, ratingClass } from './transform'
import './queries'
import type { EraTranslatorRow } from './queries'
import { TechTooltip } from '../../ui/TechTooltip'

function fmtRating(v: number) {
  return `${v >= 0 ? '+' : ''}${v.toFixed(3)}s`
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
      hook="How big was Hamilton's 2020 margin over his teammate, next to Verstappen's in 2024? Every season is rated by the driver's lap-by-lap gap to his teammate in the same car, so the car, and the 2022 regulation change, cancel out."
      badges={[
        {
          label: 'What It Means',
          content: 'Negative = faster than his teammate, in seconds per lap (median lap-by-lap gap, season average). A 2018 rating of −0.3s and a 2024 rating of −0.3s are the same margin over a teammate. No era offset is applied: a regulation change moves both teammates alike, so it cancels.',
        },
        {
          label: 'Why It Matters',
          content: 'A rating says as much about the teammate as the driver: a margin over a weak teammate and the same margin over a strong one are different achievements. Drivers marked ★ raced at least 8 races on each side of the 2022 regulation boundary.',
        },
        {
          label: "How It's Calculated",
          content: 'Per race, the median of the driver\'s lap-by-lap gap to his teammate on laps both ran clean. Per season, those are averaged and shrunk toward the season mean with a 5-race prior. A wider CI means fewer races.',
        },
      ]}
      methodology={methodologyContent}
      methodologyHref={methodologyHref}
      provenance={{ dataWindow: '2018–2025', nObs: result?.rows.length }}
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
                    <TechTooltip content="Raced 8+ races on each side of the 2022 regulation change">
                      <span className="text-amber-400/80 text-[10px] cursor-help">★</span>
                    </TechTooltip>
                  )}
                </span>
              ),
            },
            {
              key: 'era_adjusted_rating',
              header: 'Gap to teammate (s)',
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
