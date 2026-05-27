import FeaturePage from '../../ui/layout/FeaturePage'
import { Heatmap } from '../../ui/charts'
import type { HeatmapCell } from '../../ui/charts'
import { methodologyContent, methodologyHref } from './methodology'
import { useQuery } from '../../data/hooks/useQuery'
import { transform, toCsvRows } from './transform'
import './queries'
import type { CircuitInteractionRow } from './queries'

function InteractionTooltip({
  cell,
  xLabel,
  yLabel,
  rows,
}: {
  cell: HeatmapCell
  xLabel: string
  yLabel: string
  rows: CircuitInteractionRow[]
}) {
  const row = rows.find(r => r.constructor_id === yLabel && r.circuit_name === xLabel)
  return (
    <div className="bg-[#13151a] border border-white/15 rounded px-3 py-2 text-xs shadow-xl">
      <p className="font-semibold mb-1">{yLabel} @ {xLabel}</p>
      <p className="text-muted">
        Circuit bonus:{' '}
        <span className={`font-mono ${cell.value !== null && cell.value < 0 ? 'text-green-400' : 'text-red-400'}`}>
          {cell.value !== null ? `${cell.value > 0 ? '+' : ''}${cell.value.toFixed(3)}s` : ' '}
        </span>
      </p>
      {row && (
        <p className="text-muted">
          Races: <span className="font-mono text-[rgb(var(--color-text))]">{row.n_races}</span>
        </p>
      )}
    </div>
  )
}

export default function ConstructorCircuitInteractionPage() {
  const { data, isLoading, error } = useQuery<CircuitInteractionRow[]>(
    'constructor-circuit-interaction.all',
    undefined
  )

  const heatmap = data ? transform(data) : null

  return (
    <FeaturePage
      title="Circuit × Constructor"
      hook="Some constructors are systematically faster at specific circuits beyond their season-average coefficient Ferrari at Monza, Red Bull at high-altitude venues. This heatmap surfaces those persistent circuit bonuses and penalties."
      badges={[
        {
          label: 'What It Means',
          content: 'Green = constructor outperforms their own season average at that circuit. Red = underperforms. These are circuit-specific setup advantages above and beyond general car speed.',
        },
        {
          label: 'Why It Matters',
          content: 'Circuit interaction terms explain why race weekend predictions based purely on season pace can be systematically wrong at certain venues. A constructor with a strong Monza interaction will outperform expectations every year they bring their usual low-drag package.',
        },
        {
          label: "How It's Calculated",
          content: 'Per (constructor, circuit), the model computes the deviation from the season-average structural pace, then applies Bayesian shrinkage toward zero with a 3-race prior. The average across multiple seasons is shown.',
        },
      ]}
      methodology={methodologyContent}
      methodologyHref={methodologyHref}
      provenance={{ dataWindow: '2018–2024' }}
      csvRows={data ? toCsvRows(data) : undefined}
      csvFilename="constructor-circuit-interaction.csv"
      isLoading={isLoading}
      error={error}
      isEmpty={!isLoading && heatmap?.cells.length === 0}
    >
      {heatmap && heatmap.cells.length > 0 && (
        <section className="rounded-xl border border-border bg-white/[0.015] p-4 sm:p-5">
          <h2 className="text-sm font-semibold tracking-tight mb-1">
            Constructor × Circuit pace bonus/penalty
          </h2>
          <p className="text-xs text-muted mb-4">
            Constructors sorted by average interaction. Circuits alphabetical.
            Only circuits with ≥ 2 races shown. Green = circuit specialist, red = weak venue.
          </p>
          <Heatmap
            xLabels={heatmap.xLabels}
            yLabels={heatmap.yLabels}
            cells={heatmap.cells}
            minValue={heatmap.minValue}
            maxValue={heatmap.maxValue}
            colorMode="diverging"
            cellWidth={28}
            cellHeight={26}
            yLabelWidth={96}
            legendLabel="Circuit bonus"
            renderTooltip={(cell, xLabel, yLabel) => (
              <InteractionTooltip
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
