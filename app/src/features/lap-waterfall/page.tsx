import { useState } from 'react'
import FeaturePage from '../../ui/layout/FeaturePage'
import LapWaterfallChart from './LapWaterfallChart'
import { methodologyContent, methodologyHref } from './methodology'
import { useQuery } from '../../data/hooks/useQuery'
import { useFilters } from '../../state/FilterContext'
import { transform, toCsvRows } from './transform'
import type { WaterfallResult } from './transform'
import type { LapResidualRow } from './queries'
import './queries'

export default function LapWaterfallPage() {
  const { season, raceId } = useFilters()
  const filterKey = `${season}-${raceId}`
  const [selectedDriver, setSelectedDriver] = useState<string | null>(null)
  const [lastFilterKey, setLastFilterKey] = useState(filterKey)
  if (filterKey !== lastFilterKey) {
    setSelectedDriver(null)
    setLastFilterKey(filterKey)
  }

  // raceId from FilterContext is number | null convert to the string key format
  const raceKey = raceId !== null ? `${season}_${raceId}` : null

  const { data, isLoading, error } = useQuery<LapResidualRow[]>(
    'lap-waterfall.race',
    { season, raceId: raceKey }
  )

  const results: WaterfallResult[] = data ? data.map(transform) : []
  const activeDriver = selectedDriver ?? results[0]?.driverId ?? null
  const activeResult = results.find(r => r.driverId === activeDriver) ?? results[0]
  const csvRows = results.length ? toCsvRows(results) : undefined
  const drivers = results.map(r => r.driverId)

  const contextLabel = raceKey
    ? `Race ${raceKey}`
    : `${season} season average`

  return (
    <FeaturePage
      title="Lap Time Decomposition"
      hook="Seven causes, one lap time. The additive identity breaks every lap into fuel, compound, rubber, ambient, constructor, dirty air, driver skill, and unexplained noise and proves the sum closes."
      badges={[
        {
          label: 'What It Means',
          content: 'See exactly how much of a driver\'s pace advantage comes from the car vs their own skill averaged across a race or whole season.',
        },
        {
          label: 'Why It Matters',
          content: 'The decomposition is an OLS causal model enforced by a CI-checked additive invariant on every lap in the warehouse. The closure badge verifies the identity holds in the browser a live integrity check, not a claim.',
        },
        {
          label: "How It's Calculated",
          content: 'Source: fct_lap_residuals (partitioned by season). SC and major-outlier laps excluded. Each bar = mean component across clean laps. Closure gap = Σ components − pace_delta_s (reconstructed as total_explained_s + driver_skill + track_unexplained).',
        },
      ]}
      methodology={methodologyContent}
      methodologyHref={methodologyHref}
      provenance={{ dataWindow: '2018–2024', nObs: activeResult?.nLaps }}
      csvRows={csvRows}
      csvFilename={`lap-waterfall-${season}${raceKey ? `-${raceKey}` : ''}.csv`}
      isLoading={isLoading}
      error={error}
      isEmpty={results.length === 0}
    >
      {results.length > 0 && (
        <div className="flex flex-col gap-4">
          {/* Context label */}
          <p className="text-xs text-muted">
            Showing <span className="text-[rgb(var(--color-text))]">{contextLabel}</span>
            {!raceKey && ' select a race in the filter bar to narrow to one event'}
          </p>

          {/* Driver selector compact, wrapping */}
          {drivers.length > 1 && (
            <div className="flex flex-wrap gap-1.5 max-h-24 overflow-y-auto pr-1">
              {drivers.map(d => (
                <button
                  key={d}
                  onClick={() => setSelectedDriver(d)}
                  className={`text-xs px-2 py-0.5 rounded border transition-colors font-mono ${
                    d === activeDriver
                      ? 'border-accent text-accent bg-accent/10'
                      : 'border-border text-muted hover:border-accent/40 hover:text-[rgb(var(--color-text))]'
                  }`}
                >
                  {d}
                </button>
              ))}
            </div>
          )}

          <LapWaterfallChart results={results} selectedDriver={activeDriver} />
        </div>
      )}
    </FeaturePage>
  )
}
