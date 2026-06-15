import { useEffect } from 'react'
import { useSearchParams } from 'react-router-dom'
import FeaturePage from '../../ui/layout/FeaturePage'
import ChampionshipChart from './ChampionshipChart'
import { methodologyContent, methodologyHref } from './methodology'
import { useQuery } from '../../data/hooks/useQuery'
import { useFilters } from '../../state/FilterContext'
import { transform, toCsvRows } from './transform'
import './queries'

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

export default function CounterfactualChampionshipPage() {
  const { season } = useFilters()
  const [searchParams, setSearchParams] = useSearchParams()
  const hostConstructorId = searchParams.get('constructor') ?? ''

  const setConstructor = (v: string) =>
    setSearchParams(p => { v ? p.set('constructor', v) : p.delete('constructor'); return p }, { replace: true })

  useEffect(() => {
    setSearchParams(p => { p.delete('constructor'); return p }, { replace: true })
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [season])

  const { data: constructors, isLoading: consLoading } = useQuery<{ host_constructor_id: string }[]>(
    'counterfactual-championship.constructors',
    { season }
  )
  const constructorOptions = (constructors ?? []).map(c => ({
    value: c.host_constructor_id,
    label: c.host_constructor_id,
  }))

  const ready = Boolean(hostConstructorId)
  const { data, isLoading, error } = useQuery<Parameters<typeof transform>[0]>(
    'counterfactual-championship.data',
    { season, hostConstructorId },
    { enabled: ready }
  )

  const result = data ? transform(data) : null

  return (
    <FeaturePage
      title="Counterfactual Championship"
      hook="The ghost car model taken to its logical conclusion. Place every driver in one chosen team's car for the entire season and re-run the championship revealing how much of the WDC and WCC was the driver versus the machinery."
      badges={[
        {
          label: 'What It Means',
          content: 'In a 2023 Williams, Verstappen finishes where his talent alone stripped of Red Bull\'s 1.2 s/lap advantage can take him.',
        },
        {
          label: 'Why It Matters',
          content: 'A full-season aggregation of the ghost car model is the most rigorous answer to "who is actually the best driver on the grid?" that pure statistics can produce.',
        },
        {
          label: "How It's Calculated",
          content: "Each driver is transplanted into the host car (fct_ghost_race_finish) and ranked against the rest of the grid in their real cars so the host car's pace level actually drives the result. F1 points (25-18-15-12-10-8-6-4-2-1) assigned to both projected and actual positions. Only scenarios with avg_recombination_confidence ≥ 0.3 count; coverage < 15 races triggers a warning badge.",
        },
      ]}
      methodology={methodologyContent}
      methodologyHref={methodologyHref}
      provenance={{ dataWindow: '2018-2024' }}
      csvRows={result ? toCsvRows(result.ghostStandings) : undefined}
      csvFilename={`counterfactual-championship-${season}-${hostConstructorId || 'all'}.csv`}
      isLoading={isLoading && ready}
      error={error}
      isEmpty={ready && result?.ghostStandings.length === 0}
    >
      <div className="flex flex-wrap gap-4 mb-6">
        <Select
          label="Host constructor"
          value={hostConstructorId}
          onChange={setConstructor}
          options={constructorOptions}
          disabled={consLoading}
        />
      </div>
      {!ready && (
        <p className="text-sm text-muted py-6">Select a host constructor to run the counterfactual championship.</p>
      )}
      {result && result.ghostStandings.length > 0 && (
        <ChampionshipChart data={result.ghostStandings} coverageWarning={result.coverageWarning} />
      )}
    </FeaturePage>
  )
}
