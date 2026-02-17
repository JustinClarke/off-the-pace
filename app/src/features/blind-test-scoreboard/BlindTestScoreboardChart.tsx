import { useMemo } from 'react'
import Scatter from '../../ui/charts/Scatter'
import type { ScoreboardResult, ConfusionCell, CliffClass } from './transform'
import { CLIFF_CLASSES, COMPOUND_COLORS } from './transform'

const FALLBACK_COLOR = '#a78bfa'

function compoundColor(compound: string, inEnvelope: boolean) {
  const base = COMPOUND_COLORS[compound] ?? FALLBACK_COLOR
  return inEnvelope ? base : base + '55' // dim out-of-envelope points
}

// Confusion matrix cell colour: diagonal = teal, off-diagonal intensity = rowShare
function confusionCellBg(cell: ConfusionCell): string {
  if (cell.predicted === cell.actual) {
    const alpha = Math.round(0.15 + cell.rowShare * 0.75 * 255).toString(16).padStart(2, '0')
    return `#2dd4bf${alpha}`
  }
  const alpha = Math.round(cell.rowShare * 0.7 * 255).toString(16).padStart(2, '0')
  return `#ef4444${alpha}`
}

const CLASS_LABELS: Record<CliffClass, string> = {
  '0_to_2': '0-2 laps',
  '3_to_5': '3-5 laps',
  '6_plus': '6+ laps',
  'none_in_stint': 'No cliff',
}

interface CoverageRugProps {
  rug: ScoreboardResult['rug']
}

function CoverageRug({ rug }: CoverageRugProps) {
  // Sample at most 400 laps for rendering performance
  const sample = rug.length > 400 ? rug.filter((_, i) => i % Math.ceil(rug.length / 400) === 0) : rug
  return (
    <div className="flex flex-col gap-1">
      <div className="text-xs text-muted mb-1">Interval coverage rug (each bar = one lap)</div>
      <div className="flex gap-px h-6 w-full overflow-hidden rounded-sm">
        {sample.map((entry, i) => (
          <div
            key={i}
            className="flex-1 min-w-0"
            style={{ background: entry.inEnvelope ? '#2dd4bf' : '#ef444466' }}
            title={entry.inEnvelope ? 'In envelope' : 'Outside envelope'}
          />
        ))}
      </div>
    </div>
  )
}

interface ConfusionMatrixProps {
  cells: ConfusionCell[]
}

function ConfusionMatrix({ cells }: ConfusionMatrixProps) {
  return (
    <div className="overflow-x-auto">
      <table className="text-xs border-collapse w-full">
        <thead>
          <tr>
            <th className="text-muted text-right pr-2 py-1 font-normal">Predicted</th>
            {CLIFF_CLASSES.map(cls => (
              <th key={cls} className="text-muted text-center px-2 py-1 font-normal">
                {CLASS_LABELS[cls]}
              </th>
            ))}
          </tr>
          <tr>
            <th className="text-muted text-right pr-2 pb-1 font-normal text-[10px]">&darr; \ Actual &rarr;</th>
            {CLIFF_CLASSES.map(cls => (
              <th key={cls} />
            ))}
          </tr>
        </thead>
        <tbody>
          {CLIFF_CLASSES.map(predicted => (
            <tr key={predicted}>
              <td className="text-muted text-right pr-2 py-1 whitespace-nowrap">{CLASS_LABELS[predicted]}</td>
              {CLIFF_CLASSES.map(actual => {
                const cell = cells.find(c => c.predicted === predicted && c.actual === actual)!
                return (
                  <td
                    key={actual}
                    className="text-center px-2 py-1 font-mono min-w-[60px] rounded"
                    style={{ background: cell.count > 0 ? confusionCellBg(cell) : 'transparent' }}
                    title={`${cell.count} laps (${(cell.rowShare * 100).toFixed(0)}% of predicted ${CLASS_LABELS[predicted]})`}
                  >
                    {cell.count}
                  </td>
                )
              })}
            </tr>
          ))}
        </tbody>
      </table>
      <p className="text-[10px] text-muted mt-2">
        Diagonal = correct. Row-normalised intensity: teal = hit, red = miss.
      </p>
    </div>
  )
}

interface CoverageBadgeProps {
  stat: ScoreboardResult['coverageStat']
}

function CoverageBadge({ stat }: CoverageBadgeProps) {
  const pct = (stat.empirical * 100).toFixed(1)
  const nomPct = (stat.nominal * 100).toFixed(0)
  const ok = Math.abs(stat.empirical - stat.nominal) <= 0.05
  return (
    <div className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-mono
      ${ok ? 'bg-teal-500/10 text-teal-400 border border-teal-500/20' : 'bg-amber-500/10 text-amber-400 border border-amber-500/20'}`}>
      <span className={`w-2 h-2 rounded-full ${ok ? 'bg-teal-400' : 'bg-amber-400'}`} />
      {pct}% in envelope @ {nomPct}% nominal - n={stat.n.toLocaleString()}
    </div>
  )
}

interface Props {
  result: ScoreboardResult
}

export default function BlindTestScoreboardChart({ result }: Props) {
  const scatterData = useMemo(() =>
    result.scatter.map(p => ({
      x: p.x,
      y: p.y,
      label: p.label,
      color: compoundColor(p.compound, p.isInEnvelope),
      p10: p.p10,
      p90: p.p90,
      isInEnvelope: p.isInEnvelope,
      compound: p.compound,
      driverId: p.driverId,
      lapInStint: p.lapInStint,
    })),
    [result.scatter]
  )

  const compoundLegend = result.compoundFilter.map(c => ({
    label: c,
    color: COMPOUND_COLORS[c] ?? FALLBACK_COLOR,
  }))

  return (
    <div className="flex flex-col gap-8">
      {/* Coverage badge */}
      <div className="flex items-center gap-3 flex-wrap">
        <span className="text-sm text-muted">Interval coverage:</span>
        <CoverageBadge stat={result.coverageStat} />
      </div>

      {/* Predicted vs actual scatter */}
      <div>
        <h3 className="text-sm font-medium mb-3">Predicted p50 vs actual degradation jump (s)</h3>
        <Scatter
          data={scatterData}
          xLabel="Actual (s)"
          yLabel="Predicted p50 (s)"
          xFormatter={v => `${v > 0 ? '+' : ''}${v.toFixed(2)}s`}
          yFormatter={v => `${v > 0 ? '+' : ''}${v.toFixed(2)}s`}
          xRef={0}
          yRef={0}
          height={360}
          legend={compoundLegend}
          renderTooltip={p => (
            <div className="bg-[#13151a] border border-white/15 rounded px-3 py-2 text-xs shadow-xl min-w-[180px]">
              <p className="font-semibold mb-1">{p['driverId'] as string} - {p['compound'] as string} lap {p['lapInStint'] as number}</p>
              <p className="text-muted">Actual: <span className="font-mono text-foreground">{(p.x).toFixed(3)}s</span></p>
              <p className="text-muted">Predicted p50: <span className="font-mono text-foreground">{(p.y).toFixed(3)}s</span></p>
              <p className="text-muted">p10 / p90: <span className="font-mono text-foreground">{(p['p10'] as number).toFixed(2)} / {(p['p90'] as number).toFixed(2)}</span></p>
              <p className="text-muted mt-1">
                Envelope: <span className={`font-mono ${p['isInEnvelope'] ? 'text-teal-400' : 'text-red-400'}`}>
                  {p['isInEnvelope'] ? 'in' : 'out'}
                </span>
              </p>
            </div>
          )}
        />
        <p className="text-xs text-muted mt-2">
          Points on the identity diagonal = perfect prediction.
          Teal-intensity dots are in the p10-p90 envelope; desaturated dots are outside.
        </p>
      </div>

      {/* Coverage rug */}
      {result.rug.length > 0 && (
        <CoverageRug rug={result.rug} />
      )}

      {/* Cliff class confusion matrix */}
      <div>
        <h3 className="text-sm font-medium mb-3">Cliff class confusion matrix</h3>
        <ConfusionMatrix cells={result.confusion} />
      </div>
    </div>
  )
}
