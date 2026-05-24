import { useEffect, useMemo } from 'react'
import { useSearchParams } from 'react-router-dom'
import FeaturePage from '../../ui/layout/FeaturePage'
import PitStrategyGanttChart from './PitStrategyGanttChart'
import { methodologyContent, methodologyHref } from './methodology'
import { useQuery } from '../../data/hooks/useQuery'
import { useFilters } from '../../state/FilterContext'
import { useRaceOptions } from '../shared/useRaceOptions'
import { transform, toCsvRows } from './transform'
import './queries'
import type { PitGanttRow, RaceSummaryRow } from './queries'

function Select({
  label,
  value,
  onChange,
  options,
  disabled,
}: {
  label: string
  value: string
  onChange: (v: string) => void
  options: { value: string; label: string }[]
  disabled?: boolean
}) {
  return (
    <div className="flex flex-col gap-1">
      <label className="text-xs font-medium text-muted uppercase tracking-wider">{label}</label>
      <select
        value={value}
        onChange={e => onChange(e.target.value)}
        disabled={disabled || !options.length}
        className="bg-surface border border-border rounded px-3 py-1.5 text-sm font-mono
                   text-[rgb(var(--color-text))] focus:outline-none focus:ring-1 focus:ring-accent
                   disabled:opacity-40 cursor-pointer min-w-[180px]"
      >
        <option value="">-- select --</option>
        {options.map(o => (
          <option key={o.value} value={o.value}>{o.label}</option>
        ))}
      </select>
    </div>
  )
}

export default function PitStrategyPage() {
  const { season } = useFilters()
  const [searchParams, setSearchParams] = useSearchParams()

  const raceId = searchParams.get('race_id') ?? ''

  const setParam = (key: string, value: string) =>
    setSearchParams(p => { value ? p.set(key, value) : p.delete(key); return p }, { replace: true })

  useEffect(() => {
    setSearchParams(p => { p.delete('race_id'); return p }, { replace: true })
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [season])

  const { raceOptions, isLoading: optsLoading } = useRaceOptions(season)

  const ready = Boolean(raceId)

  const { data: ganttRows, isLoading: ganttLoading, error } = useQuery<PitGanttRow[]>(
    'pit-strategy.gantt',
    { race_id: raceId, season },
    { enabled: ready }
  )

  const { data: summaryRows } = useQuery<RaceSummaryRow[]>(
    'pit-strategy.race-summary',
    { race_id: raceId, season },
    { enabled: ready }
  )

  const result = useMemo(() => {
    if (!ganttRows?.length) return null
    const totalLaps = summaryRows?.[0]?.total_laps ?? 70
    return transform(ganttRows, totalLaps)
  }, [ganttRows, summaryRows])

  const csvFilename = raceId
    ? `pit-strategy-${raceId}-${season}.csv`
    : `pit-strategy-${season}.csv`

  return (
    <FeaturePage
      title="Pit Strategy Gantt + Decision Grader"
      hook="Every stint in the race, laid out by lap. Bar colour = compound. Border colour = decision quality: did the team pit at the right time, or leave their driver on crumbling rubber?"
      badges={[
        {
          label: 'What It Means',
          content: 'Each horizontal bar is one tyre stint. Wider bars mean longer stints. A red border means the team overran the optimal window the car was on tyres past their peak. A dashed line inside the bar marks the cliff onset lap.',
        },
        {
          label: 'Why It Matters',
          content: 'A stint that overruns the cliff can cost several seconds per lap across multiple laps. The opportunity cost column shows the total time surrendered making this chart a direct measure of strategy quality.',
        },
        {
          label: "How It's Calculated",
          content: 'Sources: fct_stint_features (stint metadata + tyre management), int_pit_strategy_value (optimal window, overrun, opportunity cost), fct_lap_residuals (absolute lap numbers). The optimal pit lap minimises total race time given the degradation model and undercut threat window.',
        },
      ]}
      methodology={methodologyContent}
      methodologyHref={methodologyHref}
      provenance={{
        dataWindow: '2018-2024',
      }}
      csvRows={result ? toCsvRows(result) : undefined}
      csvFilename={csvFilename}
      isLoading={ganttLoading && ready}
      error={error}
      isEmpty={ready && result?.stints.length === 0}
    >
      <div className="flex flex-wrap gap-4 mb-6">
        <Select
          label="Race"
          value={raceId}
          onChange={v => setParam('race_id', v)}
          options={raceOptions}
          disabled={optsLoading}
        />
      </div>

      {!ready && (
        <p className="text-sm text-muted py-6">Select a race above to see the strategy Gantt.</p>
      )}
      {result && <PitStrategyGanttChart result={result} />}
    </FeaturePage>
  )
}
