import { useEffect } from 'react'
import { useSearchParams } from 'react-router-dom'
import FeaturePage from '../../ui/layout/FeaturePage'
import GhostStandingsChart from './GhostStandingsChart'
import { methodologyContent, methodologyHref } from './methodology'
import { useQuery } from '../../data/hooks/useQuery'
import { useFilters } from '../../state/FilterContext'
import { transform, toCsvRows } from './transform'
import './queries'
import type { GhostStandingsRow } from './queries'

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
  const { season } = useFilters()
  const [searchParams, setSearchParams] = useSearchParams()

  const raceId = searchParams.get('race_id') ?? ''
  const hostConstructorId = searchParams.get('constructor') ?? ''

  const setParam = (key: string, value: string) =>
    setSearchParams(p => { value ? p.set(key, value) : p.delete(key); return p }, { replace: true })

  // When season changes, clear both selections they belong to the old season
  useEffect(() => {
    setSearchParams(p => { p.delete('race_id'); p.delete('constructor'); return p }, { replace: true })
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [season])

  // Options query-scoped to the selected season
  const { data: opts, isLoading: optsLoading } = useQuery<{
    races: { race_id: string; race_year: number; circuit_name: string }[]
    constructors: { host_constructor_id: string }[]
  }>(
    'ghost-race-standings.options',
    { season }
  )

  const raceOptions = (opts?.races ?? []).map(r => ({
    value: r.race_id,
    label: r.circuit_name || r.race_id,
  }))

  const constructorOptions = (opts?.constructors ?? []).map(c => ({
    value: c.host_constructor_id,
    label: c.host_constructor_id,
  }))

  // Main data query-only fires when both selectors are set
  const ready = Boolean(raceId && hostConstructorId)
  const { data, isLoading: dataLoading, error } = useQuery<GhostStandingsRow[]>(
    'ghost-race-standings.data',
    { raceId, hostConstructorId },
    { enabled: ready }
  )

  const result = data ? transform(data) : null
  const scenario = result?.scenarios[0] ?? null

  const selectors = (
    <div className="flex flex-wrap gap-4 mb-6">
      <Select
        label="Race"
        value={raceId}
        onChange={v => setParam('race_id', v)}
        options={raceOptions}
        disabled={optsLoading}
      />
      <Select
        label="Host constructor"
        value={hostConstructorId}
        onChange={v => setParam('constructor', v)}
        options={constructorOptions}
        disabled={optsLoading}
      />
    </div>
  )

  const csvFilename = raceId && hostConstructorId
    ? `ghost-standings-${raceId}-${hostConstructorId.replace(/\s+/g, '-').toLowerCase()}.csv`
    : `ghost-standings-${season}.csv`

  return (
    <FeaturePage
      title="Ghost Car Race Standings"
      hook="What if every driver raced in every team's car? Pace recombination rebuilds each driver's lap times in a host constructor's car and re-ranks the grid revealing how much of the finishing order is the car, and how much is the driver."
      badges={[
        {
          label: 'What It Means',
          content: 'A driver finishing 6th in their own car but 2nd in a top-team ghost scenario is telling you the car cost them four places not their driving.',
        },
        {
          label: 'Why It Matters',
          content: 'Ghost standings separate car performance from driver performance without requiring the impossible counterfactual to actually happen. The confidence column is an explicit uncertainty quantification not a hand-waving disclaimer.',
        },
        {
          label: "How It's Calculated",
          content: "Each driver's lap times are rebuilt from their skill residual + the host constructor's structural pace + degradation + environmental terms. Drivers are re-ranked by predicted cumulative race time. Only laps with recombination confidence >= 0.3 count.",
        },
      ]}
      methodology={methodologyContent}
      methodologyHref={methodologyHref}
      provenance={{ dataWindow: '2018-2024', nObs: scenario?.entries.length }}
      csvRows={result ? toCsvRows(result) : undefined}
      csvFilename={csvFilename}
      isLoading={dataLoading && ready}
      error={error}
      isEmpty={ready && result?.scenarios.length === 0}
    >
      {selectors}
      {!ready && !dataLoading && (
        <p className="text-sm text-muted py-6">Select a race and host constructor above to see the ghost standings.</p>
      )}
      {scenario && <GhostStandingsChart result={result!} activeScenario={scenario} />}
    </FeaturePage>
  )
}
