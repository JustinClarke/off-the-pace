import { useEffect } from 'react'
import { useSearchParams } from 'react-router-dom'
import FeaturePage from '../../ui/layout/FeaturePage'
import RankedTable from '../../ui/charts/RankedTable'
import { methodologyContent, methodologyHref } from './methodology'
import { useQuery } from '../../data/hooks/useQuery'
import { useFilters } from '../../state/FilterContext'
import { useRaceOptions } from '../shared/useRaceOptions'
import { transform, toCsvRows } from './transform'
import type { PaceMode, ConstructorPaceRow } from './queries'
import './queries'

function fmt(s: number) {
  return `${s >= 0 ? '+' : ''}${s.toFixed(3)}s`
}

function paceClass(v: unknown) {
  const s = v as number
  if (s < -0.3) return 'text-green-400'
  if (s > 0.3) return 'text-red-400'
  return 'text-[rgb(var(--color-text))]'
}

function ciLabel(lo: unknown, hi: unknown) {
  return `[${(lo as number).toFixed(2)}, ${(hi as number).toFixed(2)}]`
}

export default function ConstructorStructuralPacePage() {
  const { season } = useFilters()
  const [searchParams, setSearchParams] = useSearchParams()

  const raceId = searchParams.get('race') ?? ''
  const mode = (searchParams.get('mode') ?? 'race') as PaceMode

  const setParam = (key: string, value: string) =>
    setSearchParams(p => { value ? p.set(key, value) : p.delete(key); return p }, { replace: true })

  useEffect(() => {
    setSearchParams(p => { p.delete('race'); return p }, { replace: true })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [season])

  const { raceOptions, isLoading: racesLoading } = useRaceOptions(season)

  const { data, isLoading, error } = useQuery<ConstructorPaceRow[]>(
    'constructor-structural-pace.data',
    { season, raceId: raceId || null, mode }
  )

  const entries = data ? transform(data) : []

  const title = raceId
    ? raceOptions.find(r => r.value === raceId)?.label ?? raceId
    : `${season} Season Average`

  return (
    <FeaturePage
      title="Constructor Structural Pace"
      hook="Strip out driver skill, tyre state, and conditions what's left is the car. Ranks every constructor's raw pace advantage per race or across a season."
      badges={[
        {
          label: 'What It Means',
          content: 'Negative = faster than field average. The number is the lap-time contribution of the chassis alone, after all other factors are modelled out.',
        },
        {
          label: 'Race vs Qualifying',
          content: 'Race pace reflects tyre management ability across a stint. Qualifying pace reflects peak single-lap performance. Teams can rank differently on each metric.',
        },
        {
          label: '95% CI',
          content: 'Width reflects how many clean same-team laps went into the estimate. A team with only one driver completing a race has a wider interval.',
        },
      ]}
      methodology={methodologyContent}
      methodologyHref={methodologyHref}
      provenance={{ dataWindow: '2018-2024' }}
      csvRows={entries.length ? toCsvRows(entries, mode) : undefined}
      csvFilename={`constructor-pace-${season}-${raceId || 'season'}-${mode}.csv`}
      isLoading={isLoading}
      error={error}
      isEmpty={!isLoading && entries.length === 0}
    >
      {/* Controls */}
      <div className="flex flex-wrap gap-4 mb-6 items-end">
        <div className="flex flex-col gap-1">
          <label className="text-xs font-medium text-muted uppercase tracking-wider">Race</label>
          <select
            value={raceId}
            onChange={e => setParam('race', e.target.value)}
            disabled={racesLoading}
            className="bg-surface border border-border rounded px-3 py-1.5 text-sm font-mono
                       text-[rgb(var(--color-text))] focus:outline-none focus:ring-1 focus:ring-accent
                       disabled:opacity-40 cursor-pointer min-w-[200px]"
          >
            <option value="">Season average</option>
            {raceOptions.map(o => (
              <option key={o.value} value={o.value}>{o.label}</option>
            ))}
          </select>
        </div>

        <div className="flex flex-col gap-1">
          <label className="text-xs font-medium text-muted uppercase tracking-wider">Mode</label>
          <div className="flex rounded overflow-hidden border border-border text-sm font-mono">
            {(['race', 'qualifying'] as PaceMode[]).map(m => (
              <button
                key={m}
                onClick={() => setParam('mode', m)}
                className={`px-4 py-1.5 capitalize transition-colors ${
                  mode === m
                    ? 'bg-accent text-white'
                    : 'text-muted hover:text-[rgb(var(--color-text))]'
                }`}
              >
                {m}
              </button>
            ))}
          </div>
        </div>
      </div>

      {entries.length > 0 && (
        <>
          <p className="text-xs text-muted uppercase tracking-wider font-mono mb-4">
            {title} &middot; {mode} pace
          </p>
          <RankedTable
            rows={entries}
            columns={[
              { key: 'rank', header: '#', align: 'right' },
              { key: 'constructor', header: 'Constructor', align: 'left' },
              {
                key: 'pace_s',
                header: 'Pace vs field',
                align: 'right',
                render: v => fmt(v as number),
                cellClass: paceClass,
              },
              {
                key: 'ci_low_s',
                header: '95% CI',
                align: 'right',
                render: (v, row) => ciLabel(v, row.ci_high_s),
              },
              { key: 'observations', header: 'Obs', align: 'right' },
              {
                key: 'races',
                header: 'Races',
                align: 'right',
                render: v => (v as number) > 1 ? String(v) : ' ',
              },
            ]}
          />
        </>
      )}
    </FeaturePage>
  )
}
