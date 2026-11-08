import { useProvenance } from '../../data/provenance'
import { useEffect, useRef } from 'react'
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

function fmt(s: number | null) {
  if (s == null || !Number.isFinite(s)) return '—'
  return `${s >= 0 ? '+' : ''}${s.toFixed(3)}s`
}

function ciLabel(lo: unknown, hi: unknown) {
  if (lo == null || hi == null) return '—'
  return `[${(lo as number).toFixed(2)}, ${(hi as number).toFixed(2)}]`
}

function paceClass(v: unknown) {
  if (v == null) return undefined
  const s = v as number
  if (s < -0.3) return 'text-green-400'
  if (s > 0.3) return 'text-red-400'
  return 'text-[rgb(var(--color-text))]'
}

function deltaClass(v: unknown) {
  if (v == null) return undefined
  const s = v as number
  if (s < -0.15) return 'text-purple-400'
  if (s > 0.15) return 'text-orange-400'
  return 'text-[rgb(var(--color-text))]'
}

const MODE_BADGE: Record<ModeLabel, string> = {
  party: 'bg-purple-500/20 text-purple-300',
  race: 'bg-orange-500/20 text-orange-300',
  no_clear_gap: 'bg-white/10 text-muted',
}

const MODE_TEXT: Record<ModeLabel, string> = {
  party: 'party',
  race: 'race',
  no_clear_gap: 'no clear gap',
}

export default function PartyModePage() {
  const prov = useProvenance()
  const { season } = useFilters()
  const [searchParams, setSearchParams] = useSearchParams()
  const raceId = searchParams.get('race') ?? ''

  // Clear 'race' when the season changes, not on mount, so a deep link survives load (AX-03)
  const prevSeason = useRef(season)
  useEffect(() => {
    if (prevSeason.current === season) return
    prevSeason.current = season
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
          content: 'Qualifying pace meaningfully better than race pace: delta < −0.15s and the 95% CI excludes 0. The car extracts more from a single lap than a full race stint.',
        },
        {
          label: 'Race Spec',
          content: 'Race pace better than qualifying pace: delta > +0.15s and the 95% CI excludes 0. The setup favours endurance over peak lap time.',
        },
        {
          label: 'No clear gap',
          content: 'The data do not show a quali–race gap beyond ±0.15s that is distinguishable from zero. This includes small real gaps and gaps too noisy to call. No delta (no race-pace estimate) shows a dash.',
        },
      ]}
      methodology={methodologyContent}
      methodologyHref={methodologyHref}
      provenance={{ dataWindow: prov.dataWindow, dataVersion: prov.dataVersion, labelVersion: prov.labelVersion }}
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
                key: 'delta_ci_low_s',
                header: 'Delta 95% CI',
                align: 'right',
                render: (v, row) => ciLabel(v, row.delta_ci_high_s),
              },
              {
                key: 'mode',
                header: 'Mode',
                align: 'center',
                render: v => v == null ? '—' : (
                  <span className={`px-2 py-0.5 rounded text-xs font-sans uppercase tracking-wide ${MODE_BADGE[v as ModeLabel]}`}>
                    {MODE_TEXT[v as ModeLabel]}
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
