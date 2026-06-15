import { useMemo } from 'react'
import FeaturePage from '../../ui/layout/FeaturePage'
import { RankedTable } from '../../ui/charts'
import type { RankedTableColumn } from '../../ui/charts'
import { methodologyContent, methodologyHref } from './methodology'
import { useQuery } from '../../data/hooks/useQuery'
import { useFilters } from '../../state/FilterContext'
import { useRaceOptions } from '../shared/useRaceOptions'
import { transform, toCsvRows } from './transform'
import './queries'
import type { QualityAuditRow } from './queries'
import type { QualityResult } from './transform'

const columns: RankedTableColumn<QualityResult>[] = [
  { key: 'circuit_name', header: 'Race', align: 'left' },
  { key: 'total_laps', header: 'Total', align: 'right' },
  { key: 'usable_laps', header: 'Usable', align: 'right' },
  {
    key: 'pct_usable',
    header: 'Usable %',
    align: 'right',
    render: (v) => `${(v as number).toFixed(1)}%`,
    cellClass: (v) => {
      const n = v as number
      if (n >= 80) return 'text-emerald-400'
      if (n >= 70) return undefined
      return 'text-amber-400'
    },
  },
  { key: 'neutralised_laps', header: 'SC/VSC', align: 'right' },
  { key: 'rain_laps', header: 'Rain', align: 'right' },
  { key: 'out_in_laps', header: 'Out/In', align: 'right' },
  { key: 'anomaly_laps', header: 'Anomalies', align: 'right' },
]


export default function DataQualityAuditPage() {
  const { season } = useFilters()

  const { data, isLoading, error } = useQuery<QualityAuditRow[]>(
    'data-quality-audit.season',
    { season }
  )
  const { raceData } = useRaceOptions(season)

  const nameMap = useMemo(
    () => Object.fromEntries(raceData.map(r => [r.race_id, r.circuit_name])),
    [raceData]
  )

  const result = data ? transform(data, nameMap) : null

  return (
    <FeaturePage
      title="Data Quality Audit"
      hook="What fraction of laps actually made it into the model? See which races were hit by safety cars, wet weather, or anomalous laps and how the pipeline handled them."
      badges={[
        {
          label: 'What It Means',
          content: 'Usable % is the fraction of laps that passed all pipeline filters and were included in the skill and degradation models. The remaining laps were excluded because they occurred under neutralisation (SC/VSC), in wet conditions, at stint boundaries, or were flagged as anomalous.',
        },
        {
          label: 'Why It Matters',
          content: 'Low usable % races (incidents, rain) produce noisier model estimates. Races with many anomalies may show wider confidence intervals in the Ghost Car standings and degradation timeline features.',
        },
        {
          label: "How It's Calculated",
          content: 'The int_lap_anomaly_flags model applies a cascade of correction rules neutralisation (SC/VSC), weather, stint boundaries, and statistical outlier detection and outputs a boolean usable_for_modelling flag per lap.',
        },
      ]}
      methodology={methodologyContent}
      methodologyHref={methodologyHref}
      provenance={{ dataWindow: '2018–2024' }}
      csvRows={data ? toCsvRows(data) : undefined}
      csvFilename={`data-quality-${season}.csv`}
      isLoading={isLoading}
      error={error}
      isEmpty={!isLoading && result?.length === 0}
    >
      {result && result.length > 0 && (
        <section className="rounded-xl border border-border bg-white/[0.015] p-4 sm:p-5">
          <h2 className="text-sm font-semibold tracking-tight mb-1">Lap quality by race · {season}</h2>
          <p className="text-xs text-muted/70 mb-3">
            Sorted chronologically · green = ≥80% usable · amber = &lt;70%
          </p>
          <RankedTable rows={result} columns={columns} initialRows={30} />
        </section>
      )}
    </FeaturePage>
  )
}
