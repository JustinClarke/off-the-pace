import { useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import FeaturePage from '../../ui/layout/FeaturePage'
import { RaceChart, SeasonChart } from './HiddenPerformanceChart'
import { methodologyContent, methodologyHref } from './methodology'
import { useQuery } from '../../data/hooks/useQuery'
import { useFilters } from '../../state/FilterContext'
import { transform, seasonTransform, toCsvRows, toSeasonCsvRows } from './transform'
import './queries'

type View = 'race' | 'season'

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

function ViewToggle({ view, onChange }: { view: View; onChange: (v: View) => void }) {
  return (
    <div className="flex flex-col gap-1">
      <span className="text-xs font-medium text-muted uppercase tracking-wider">View</span>
      <div className="flex rounded border border-border overflow-hidden text-sm font-mono">
        {(['race', 'season'] as const).map(v => (
          <button
            key={v}
            onClick={() => onChange(v)}
            className={`px-3 py-1.5 capitalize transition-colors ${
              view === v
                ? 'bg-accent text-white'
                : 'bg-surface text-[rgb(var(--color-text))] hover:bg-accent/10'
            }`}
          >
            {v === 'race' ? 'Per-race' : 'Season'}
          </button>
        ))}
      </div>
    </div>
  )
}

function MinRacesSelect({ value, onChange }: { value: number; onChange: (v: number) => void }) {
  return (
    <div className="flex flex-col gap-1">
      <label className="text-xs font-medium text-muted uppercase tracking-wider">Min races</label>
      <select
        value={value}
        onChange={e => onChange(Number(e.target.value))}
        className="bg-surface border border-border rounded px-3 py-1.5 text-sm font-mono
                   text-[rgb(var(--color-text))] focus:outline-none focus:ring-1 focus:ring-accent
                   cursor-pointer"
      >
        {[1, 2, 3, 5, 8].map(n => (
          <option key={n} value={n}>{n}+</option>
        ))}
      </select>
    </div>
  )
}

export default function HiddenPerformancePage() {
  const { season } = useFilters()
  const [searchParams, setSearchParams] = useSearchParams()
  const hostConstructorId = searchParams.get('constructor') ?? ''
  const [view, setView] = useState<View>('race')
  const [minRaces, setMinRaces] = useState(3)

  const setConstructor = (v: string) =>
    setSearchParams(p => { v ? p.set('constructor', v) : p.delete('constructor'); return p }, { replace: true })

  useEffect(() => {
    setSearchParams(p => { p.delete('constructor'); return p }, { replace: true })
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [season])

  const { data: constructors, isLoading: consLoading } = useQuery<{ host_constructor_id: string }[]>(
    'hidden-performance.constructors',
    { season }
  )
  const constructorOptions = (constructors ?? []).map(c => ({
    value: c.host_constructor_id,
    label: c.host_constructor_id,
  }))

  const ready = Boolean(hostConstructorId)

  const { data: raceData, isLoading: raceLoading, error: raceError } = useQuery<Parameters<typeof transform>[0]>(
    'hidden-performance.data',
    { season, hostConstructorId },
    { enabled: ready && view === 'race' }
  )

  const { data: seasonData, isLoading: seasonLoading, error: seasonError } = useQuery<Parameters<typeof seasonTransform>[0]>(
    'hidden-performance.season',
    { season, hostConstructorId, minRaces },
    { enabled: ready && view === 'season' }
  )

  const raceEntries = raceData ? transform(raceData) : []
  const seasonEntries = seasonData ? seasonTransform(seasonData) : []

  const isLoading = view === 'race' ? raceLoading : seasonLoading
  const error = view === 'race' ? raceError : seasonError
  const isEmpty = ready && (view === 'race' ? raceEntries.length === 0 : seasonEntries.length === 0)

  const csvRows = view === 'race'
    ? (raceEntries.length ? toCsvRows(raceEntries) : undefined)
    : (seasonEntries.length ? toSeasonCsvRows(seasonEntries) : undefined)

  return (
    <FeaturePage
      title="Hidden Performance Detector"
      hook="Which drivers were short-changed by their car? Ghost-project every driver into a chosen team's car for every race of a season, then rank the biggest gaps between projected and actual finish. A model-derived inversion of Driver of the Day."
      badges={[
        {
          label: 'What It Means',
          content: 'Adjusted delta removes the team baseline a Williams driver projected P7 but finishing P15 in a Red Bull might just be reflecting that all Williams drivers finish P15. The adjusted column strips that out.',
        },
        {
          label: 'Why It Matters',
          content: 'Fan polls reward visible heroics. This surfaces drives that were statistically impressive but buried by the grid. Confidence gating ensures only well-estimated scenarios rank.',
        },
        {
          label: "How It's Calculated",
          content: "Constructor-adjusted delta = raw delta minus that driver's team average delta in the same scenario. A consistently underrewarded driver in the season view outranks a one-off fluke. Circuit affinity (▲ = track advantage) contextualises large deltas. ± SE is the Poisson-binomial SD of finishing positions.",
        },
      ]}
      methodology={methodologyContent}
      methodologyHref={methodologyHref}
      provenance={{ dataWindow: '2018-2024' }}
      csvRows={csvRows}
      csvFilename={`hidden-performance-${season}-${hostConstructorId || 'all'}-${view}.csv`}
      isLoading={isLoading && ready}
      error={error}
      isEmpty={isEmpty}
    >
      <div className="flex flex-wrap items-end gap-4 mb-6">
        <Select
          label="Host constructor"
          value={hostConstructorId}
          onChange={setConstructor}
          options={constructorOptions}
          disabled={consLoading}
        />
        <ViewToggle view={view} onChange={setView} />
        {view === 'season' && (
          <MinRacesSelect value={minRaces} onChange={setMinRaces} />
        )}
      </div>
      {!ready && (
        <p className="text-sm text-muted py-6">Select a host constructor above to see under-rewarded drives.</p>
      )}
      {ready && view === 'race' && raceEntries.length > 0 && <RaceChart data={raceEntries} />}
      {ready && view === 'season' && seasonEntries.length > 0 && <SeasonChart data={seasonEntries} />}
    </FeaturePage>
  )
}
