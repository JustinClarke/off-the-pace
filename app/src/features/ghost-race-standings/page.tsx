import { useSearchParams } from 'react-router-dom'
import FeaturePage from '../../ui/layout/FeaturePage'
import GhostStandingsChart from './GhostStandingsChart'
import { methodologyContent, methodologyHref } from './methodology'
import { useQuery } from '../../data/hooks/useQuery'
import { transform, toCsvRows } from './transform'
import './queries'
import type { EraAffinityRow, CircuitOption, EraOption } from './queries'

const DEFAULT_ERA = 'post2022'
const MIN_RACES_OPTIONS = ['1', '2', '3']
const DEFAULT_MIN_RACES = '2'

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

export default function GhostStandingsPage() {
  const [searchParams, setSearchParams] = useSearchParams()

  const circuitId = searchParams.get('circuit') ?? ''
  const eraKey = searchParams.get('era') ?? DEFAULT_ERA
  const minRaces = searchParams.get('min') ?? DEFAULT_MIN_RACES

  const setParam = (key: string, value: string) =>
    setSearchParams(p => { value ? p.set(key, value) : p.delete(key); return p }, { replace: true })

  // Options are cross-season (eras), so no season dependency.
  const { data: opts, isLoading: optsLoading } = useQuery<{
    circuits: CircuitOption[]
    eras: EraOption[]
  }>('ghost-race-standings.options', {})

  const circuitOptions = (opts?.circuits ?? []).map(c => ({
    value: c.circuit_id,
    label: c.circuit_name,
  }))
  const eraOptions = (opts?.eras ?? []).map(e => ({
    value: e.era_key,
    label: e.era_label,
  }))

  const ready = Boolean(circuitId && eraKey)
  const { data, isLoading: dataLoading, error } = useQuery<EraAffinityRow[]>(
    'ghost-race-standings.data',
    { circuitId, eraKey },
    { enabled: ready }
  )

  // Pre-filter by minimum race count so the leader (and gap-to-leader) is the fastest
  // driver among the survivors, then rank.
  const minN = Number(minRaces) || 1
  const filtered = (data ?? []).filter(r => r.n_obs >= minN)
  const result = filtered.length ? transform(filtered) : null

  // No driver at all at this (circuit, era) → genuine empty state; rows exist but all
  // fell below the min-races filter → a tailored "lower the filter" hint instead.
  const settled = ready && !dataLoading
  const noDataAtAll = settled && (data?.length ?? 0) === 0
  const allFilteredOut = settled && (data?.length ?? 0) > 0 && result === null

  const selectors = (
    <div className="flex flex-wrap gap-4 mb-6">
      <Select
        label="Circuit"
        value={circuitId}
        onChange={v => setParam('circuit', v)}
        options={circuitOptions}
        disabled={optsLoading}
      />
      <Select
        label="Era"
        value={eraKey}
        onChange={v => setParam('era', v)}
        options={eraOptions}
        disabled={optsLoading}
      />
      <Select
        label="Min. races"
        value={minRaces}
        onChange={v => setParam('min', v)}
        options={MIN_RACES_OPTIONS.map(n => ({ value: n, label: `≥ ${n}` }))}
      />
    </div>
  )

  const eraLabel = result?.eraLabel ?? (eraKey === 'pre2022' ? '2018–2021' : '2022–2024')
  const csvFilename = circuitId
    ? `equal-car-record-${circuitId}-${eraKey}.csv`
    : 'equal-car-record.csv'

  return (
    <FeaturePage
      title="What If the Cars Were Equal?"
      hook="Strip the car advantage and re-rank every driver on pure pace. The ghost car standings reveal who's really fastest."
      badges={[
        {
          label: 'What It Means',
          content: 'A driver topping the board at a circuit is the fastest there once the car is removed regardless of where their real machinery let them finish. It is a measure of the driver, not the team.',
        },
        {
          label: 'Why It Matters',
          content: "Real finishing order is dominated by car performance. Equalising the car exposes which drivers genuinely master a track and which were flattered by quick machinery and the confidence column tells you when there are too few races to trust the number.",
        },
        {
          label: "How It's Calculated",
          content: "Each lap's driver-skill residual (time left after fuel, tyre, rubber, ambient and constructor are removed) is averaged per driver per circuit within a regulation era, then shrunk toward the driver's era-wide mean (Bayesian, prior = 5 races). Eras split at the 2022 ground-effect change and are never blended. Negative = faster than the field.",
        },
      ]}
      methodology={methodologyContent}
      methodologyHref={methodologyHref}
      provenance={{ dataWindow: eraLabel, nObs: result?.entries.length }}
      csvRows={result ? toCsvRows(result) : undefined}
      csvFilename={csvFilename}
      isLoading={dataLoading && ready}
      error={error}
    >
      {/* Selectors stay mounted in every state so the user can always recover a
          dead-end selection (e.g. an era a circuit never raced in). */}
      {selectors}
      {!ready && !dataLoading && (
        <p className="text-sm text-muted py-6">Select a circuit and era above to see the equal-car track record.</p>
      )}
      {noDataAtAll && (
        <p className="text-sm text-muted py-6">No driver raced this circuit in the selected era try the other era.</p>
      )}
      {allFilteredOut && (
        <p className="text-sm text-muted py-6">No driver meets the minimum race count for this circuit and era lower the “Min. races” filter.</p>
      )}
      {result && <GhostStandingsChart result={result} />}
    </FeaturePage>
  )
}
