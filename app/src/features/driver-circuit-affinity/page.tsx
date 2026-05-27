import FeaturePage from '../../ui/layout/FeaturePage'
import { Heatmap } from '../../ui/charts'
import type { HeatmapCell } from '../../ui/charts'
import { methodologyContent, methodologyHref } from './methodology'
import { useQuery } from '../../data/hooks/useQuery'
import { transform, toCsvRows } from './transform'
import './queries'
import type { CircuitAffinityRow } from './queries'

function CircuitAffinityTooltip({
  cell,
  xLabel,
  yLabel,
  rows,
}: {
  cell: HeatmapCell
  xLabel: string
  yLabel: string
  rows: CircuitAffinityRow[]
}) {
  const row = rows.find(r => r.driver_id === yLabel && r.circuit_name === xLabel)
  return (
    <div className="bg-[#13151a] border border-white/15 rounded px-3 py-2 text-xs shadow-xl">
      <p className="font-semibold mb-1">{yLabel} @ {xLabel}</p>
      <p className="text-muted">
        Affinity:{' '}
        <span className={`font-mono ${cell.value !== null && cell.value < 0 ? 'text-green-400' : 'text-red-400'}`}>
          {cell.value !== null ? `${cell.value > 0 ? '+' : ''}${cell.value.toFixed(3)}s` : ' '}
        </span>
      </p>
      {row && (
        <>
          <p className="text-muted">
            Seasons: <span className="font-mono text-[rgb(var(--color-text))]">{row.seasons_observed_n}</span>
          </p>
          <p className="text-muted">
            Confidence: <span className="font-mono text-[rgb(var(--color-text))]">{(row.affinity_confidence * 100).toFixed(0)}%</span>
          </p>
        </>
      )}
    </div>
  )
}

export default function DriverCircuitAffinityPage() {
  const { data, isLoading, error } = useQuery<CircuitAffinityRow[]>(
    'driver-circuit-affinity.all',
    undefined
  )

  const heatmap = data ? transform(data) : null

  return (
    <FeaturePage
      title="Circuit Affinity"
      hook="Which circuits suit each driver's style? This heatmap shows how much faster or slower each driver is at a specific circuit relative to their own seasonal average, after removing car and field effects."
      badges={[
        {
          label: 'What It Means',
          content: 'Green = faster than the driver\'s own global average at that circuit. Red = slower. A strong green cell (Monaco for a specialist, Spa for a power-track driver) reveals genuine circuit affinity beyond the car.',
        },
        {
          label: 'Why It Matters',
          content: 'Circuit affinity is a persistent driver trait that persists across team changes. Knowing a driver systematically gains 0.4s at a specific layout independent of car strength informs driver market valuations and race simulations.',
        },
        {
          label: "How It's Calculated",
          content: 'Per (driver, circuit), the model averages raw residuals across visits and applies Bayesian shrinkage toward the driver\'s global mean with a 5-race prior. Cells require ≥ 2 observed races to appear.',
        },
      ]}
      methodology={methodologyContent}
      methodologyHref={methodologyHref}
      provenance={{ dataWindow: '2018–2024' }}
      csvRows={data ? toCsvRows(data) : undefined}
      csvFilename="driver-circuit-affinity.csv"
      isLoading={isLoading}
      error={error}
      isEmpty={!isLoading && heatmap?.cells.length === 0}
    >
      {heatmap && heatmap.cells.length > 0 && (
        <section className="rounded-xl border border-border bg-white/[0.015] p-4 sm:p-5">
          <h2 className="text-sm font-semibold tracking-tight mb-1">
            Driver × Circuit affinity heatmap
          </h2>
          <p className="text-xs text-muted mb-4">
            Drivers sorted fastest → slowest by median affinity. Circuits alphabetical.
            Only circuits with ≥ 2 race visits shown per driver.
          </p>
          <Heatmap
            xLabels={heatmap.xLabels}
            yLabels={heatmap.yLabels}
            cells={heatmap.cells}
            minValue={heatmap.minValue}
            maxValue={heatmap.maxValue}
            colorMode="diverging"
            cellWidth={28}
            cellHeight={24}
            yLabelWidth={64}
            legendLabel="Pace delta"
            renderTooltip={(cell, xLabel, yLabel) => (
              <CircuitAffinityTooltip
                cell={cell}
                xLabel={xLabel}
                yLabel={yLabel}
                rows={data!}
              />
            )}
          />
        </section>
      )}
    </FeaturePage>
  )
}
