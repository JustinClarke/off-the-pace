import { useEffect } from 'react'
import { useSearchParams } from 'react-router-dom'
import FeaturePage from '../../ui/layout/FeaturePage'
import RankedTable from '../../ui/charts/RankedTable'
import { methodologyContent, methodologyHref } from './methodology'
import { useQuery } from '../../data/hooks/useQuery'
import { useFilters } from '../../state/FilterContext'
import { useRaceOptions } from '../shared/useRaceOptions'
import { transform, toCsvRows } from './transform'
import type { PartyModeRow, } from './queries'
import type { ModeLabel } from './transform'
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

function deltaClass(v: unknown) {
  const s = v as number
  if (s < -0.15) return 'text-purple-400'
  if (s > 0.15) return 'text-orange-400'
  return 'text-[rgb(var(--color-text))]'
}

const MODE_BADGE: Record<ModeLabel, string> = {
  party: 'bg-purple-500/20 text-purple-300',
  race: 'bg-orange-500/20 text-orange-300',
  balanced: 'bg-white/10 text-muted',
}

export default function PartyModePage() {
  const { season } = useFilters()
  const [searchParams, setSearchParams] = useSearchParams()
  const raceId = searchParams.get('race') ?? ''

  useEffect(() => {
    setSearchParams(p => { p.delete('race'); return p }, { replace: true })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [season])

  const { raceOptions, isLoading: racesLoading } = useRaceOptions(season)

  const { data, isLoading, error } = useQuery<PartyModeRow[]>(
    'party-mode.data',
    { season, raceId: raceId || null }
  )

  const entries = data ? transform(data) : []

  const title = raceId
    ? raceOptions.find(r => r.value === raceId)?.label ?? raceId
    : `${season} Season Average`

  return (
    <FeaturePage
      title="Party Mode"
      hook="Which constructors gain the most in qualifying that they can't hold in a race? Compare each team's single-lap pace advantage against their race-distance pace."
      badges={[
        {
          label: 'Party Mode',
          content: 'Qualifying pace meaningfully better than race pace. Delta < −0.15s. The car extracts more from a single lap than a full race stint.',
        },
        {
          label: 'Race Spec',
          content: 'Race pace better than qualifying pace. Delta > +0.15s. The setup favours endurance over peak lap time.',
        },
        {
          label: 'Balanced',
          content: 'Within ±0.15s of zero. The team\'s relative performance is consistent across qualifying and race trim.',
        },
      ]}
      methodology={methodologyContent}
      methodologyHref={methodologyHref}
      provenance={{ dataWindow: '2018-2024' }}
      csvRows={entries.length ? toCsvRows(entries) : undefined}
      csvFilename={`party-mode-${season}-${raceId || 'season'}.csv`}
      isLoading={isLoading}
      error={error}
      isEmpty={!isLoading && entries.length === 0}
    >
      <div className="flex flex-col gap-1 mb-6">
        <label className="text-xs font-medium text-muted uppercase tracking-wider">Race</label>
        <select
          value={raceId}
          onChange={e =>
            setSearchParams(p => {
              e.target.value ? p.set('race', e.target.value) : p.delete('race')
              return p
            }, { replace: true })
          }
          disabled={racesLoading}
          className="bg-surface border border-border rounded px-3 py-1.5 text-sm font-mono
                     text-[rgb(var(--color-text))] focus:outline-none focus:ring-1 focus:ring-accent
                     disabled:opacity-40 cursor-pointer min-w-[220px]"
        >
          <option value="">Season average</option>
          {raceOptions.map(o => (
            <option key={o.value} value={o.value}>{o.label}</option>
          ))}
        </select>
      </div>

      {entries.length > 0 && (
        <>
          <p className="text-xs text-muted uppercase tracking-wider font-mono mb-4">
            {title} &middot; quali − race delta
          </p>
          <RankedTable
            rows={entries}
            columns={[
              { key: 'constructor', header: 'Constructor', align: 'left' },
              {
                key: 'quali_pace_s',
                header: 'Quali pace',
                align: 'right',
                render: v => fmt(v as number),
                cellClass: paceClass,
              },
              {
                key: 'race_pace_s',
                header: 'Race pace',
                align: 'right',
                render: v => fmt(v as number),
                cellClass: paceClass,
              },
              {
                key: 'delta_s',
                header: 'Delta (Q−R)',
                align: 'right',
                render: v => fmt(v as number),
                cellClass: deltaClass,
              },
              {
                key: 'mode',
                header: 'Mode',
                align: 'center',
                render: v => (
                  <span className={`px-2 py-0.5 rounded text-xs font-sans uppercase tracking-wide ${MODE_BADGE[v as ModeLabel]}`}>
                    {v as string}
                  </span>
                ),
              },
            ]}
          />
        </>
      )}
    </FeaturePage>
  )
}
