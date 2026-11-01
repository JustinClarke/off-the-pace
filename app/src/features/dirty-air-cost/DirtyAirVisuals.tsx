import { useState } from 'react'
import { tokens } from '../../ui/tokens'
import { UNAVAILABLE, formatSeconds } from './transform'
import type { DirtyAirResult } from './transform'
import type { DirtyAirLapRow } from './queries'
import { driverBars, lapStrip, formulaLine, VISUAL_LABEL } from './visuals'

const MODELLED = tokens.color.dirty_air // one hue for the assumed/modelled magnitude
const MEASURED = tokens.color.fuel      // one hue for the measured exposure
const FOCUS = 'focus:outline-none focus-visible:ring-2 focus-visible:ring-accent rounded'
const HATCH = 'repeating-linear-gradient(45deg, rgb(var(--color-text-muted) / 0.45) 0 1px, transparent 1px 4px)'

/** Visual 1: total placeholder cost per driver, same order as the table. Click a bar to explain it below. */
export function DriverCostBars({ rows, selected, onSelect }: {
  rows: DirtyAirResult[]
  selected: string | null
  onSelect: (driverId: string) => void
}) {
  const [active, setActive] = useState<string | null>(null)
  const bars = driverBars(rows)
  return (
    <div>
      <p className="text-xs text-muted mb-3">
        Total wake cost per driver, seconds ({VISUAL_LABEL}). Bars start at zero. Select a driver to see how
        their cost is built.
      </p>
      <ul className="flex flex-col gap-1" aria-label={`Total wake cost per driver (${VISUAL_LABEL})`}>
        {bars.map(b => (
          <li key={b.driver_id} className="relative">
            <button
              type="button"
              onClick={() => onSelect(b.driver_id)}
              onMouseEnter={() => setActive(b.driver_id)}
              onMouseLeave={() => setActive(null)}
              onFocus={() => setActive(b.driver_id)}
              onBlur={() => setActive(null)}
              aria-pressed={selected === b.driver_id}
              aria-label={b.tooltip.join('. ')}
              className={`w-full flex items-center gap-2 py-0.5 text-left cursor-pointer ${FOCUS} ${
                selected === b.driver_id ? 'bg-white/[0.06]' : 'hover:bg-white/[0.04]'}`}
            >
              <span className="w-12 shrink-0 font-mono text-xs">{b.driver_id}</span>
              <span className="flex-1 min-w-0 relative h-4 flex items-center">
                {b.fraction != null ? (
                  <>
                    <span
                      className="h-2.5 rounded-r-[4px]"
                      style={{ width: `${Math.max(b.fraction * 86, 0.5)}%`, background: MODELLED }}
                    />
                    {b.label && <span className="ml-1.5 font-mono text-xs">{b.label}</span>}
                  </>
                ) : (
                  <span className="font-mono text-xs text-muted truncate">{UNAVAILABLE} {b.reason}</span>
                )}
              </span>
            </button>
            {active === b.driver_id && (
              <div role="tooltip" className="absolute z-10 left-14 top-full mt-0.5 max-w-[calc(100%-3.5rem)] rounded border border-border
                bg-surface px-3 py-2 text-xs shadow-lg pointer-events-none">
                {b.tooltip.map((t, i) => <p key={i} className={i === 0 ? 'font-medium' : 'font-mono text-muted'}>{t}</p>)}
              </div>
            )}
          </li>
        ))}
      </ul>
    </div>
  )
}

/** Visual 2: how one driver's cost is built, lap by lap. Lap-level data. */
export function CostBuildDiagram({ driverId, laps }: { driverId: string; laps: DirtyAirLapRow[] }) {
  const strip = lapStrip(laps)
  const [idx, setIdx] = useState<number | null>(null)
  const n = strip.columns.length
  if (!n) return <p className="text-sm text-muted">No laps for {driverId}.</p>
  const cur = idx == null ? null : strip.columns[Math.min(idx, n - 1)]
  const colStyle = { minWidth: 2 }
  const onKey = (e: React.KeyboardEvent) => {
    if (e.key === 'ArrowRight') { e.preventDefault(); setIdx(i => Math.min(n - 1, (i ?? -1) + 1)) }
    else if (e.key === 'ArrowLeft') { e.preventDefault(); setIdx(i => Math.max(0, (i ?? n) - 1)) }
    else if (e.key === 'Escape') setIdx(null)
  }
  return (
    <div>
      <p className="text-xs leading-relaxed mb-2">
        <strong>{driverId}</strong>: for each lap, the <span style={{ color: MEASURED }}>measured</span> share of
        the lap close behind another car, times an <span style={{ color: MODELLED }}>assumed</span> loss
        ({VISUAL_LABEL}), gives that lap's cost.
      </p>
      <p className="font-mono text-xs text-muted mb-3">{formulaLine(laps)}. Exposure = share within 1 s + half the share
        between 1 and 2 s.</p>
      <div
        tabIndex={0}
        role="group"
        aria-label={`Lap by lap build-up of the placeholder wake cost for ${driverId}. Use left and right arrow keys to read a lap.`}
        onKeyDown={onKey}
        onBlur={() => setIdx(null)}
        className={`${FOCUS} p-1 -m-1`}
      >
        <p className="text-xs mb-1">Measured: share of the lap near the car ahead</p>
        <div className="flex items-end gap-px h-16 border-b border-border" onMouseLeave={() => setIdx(null)}>
          {strip.columns.map((c, i) => (
            <div key={c.lap} className="flex-1 h-full flex flex-col justify-end relative" style={colStyle} onMouseEnter={() => setIdx(i)}>
              {c.available ? (
                <>
                  <div style={{ height: `${(c.within1to2 ?? 0) * 100}%`, background: MEASURED, opacity: 0.4 }} />
                  <div style={{ height: `${(c.within1 ?? 0) * 100}%`, background: MEASURED }} />
                </>
              ) : (
                <div className="h-full" style={{ background: HATCH }} />
              )}
              {cur?.lap === c.lap && <div className="absolute inset-0 ring-1 ring-[rgb(var(--color-text))] pointer-events-none" />}
            </div>
          ))}
        </div>
        <p className="text-xs mt-3 mb-1">Assumed cost per lap (up to {formatSeconds(strip.costTop, 2)}, {VISUAL_LABEL})</p>
        <div className="flex items-end gap-px h-16 border-b border-border" onMouseLeave={() => setIdx(null)}>
          {strip.columns.map((c, i) => (
            <div key={c.lap} className="flex-1 h-full flex flex-col justify-end relative" style={colStyle} onMouseEnter={() => setIdx(i)}>
              {c.available ? (
                <div style={{ height: `${Math.max((c.costFraction ?? 0) * 100, 0)}%`, background: MODELLED }} />
              ) : (
                <div className="h-full" style={{ background: HATCH }} />
              )}
            </div>
          ))}
        </div>
        <div className="flex justify-between font-mono text-[10px] text-muted mt-1">
          <span>lap {strip.columns[0].lap}</span><span>lap {strip.columns[n - 1].lap}</span>
        </div>
      </div>
      <p className="font-mono text-xs min-h-[3.5rem] mt-2" aria-live="polite">
        {cur ? cur.readout : 'Hover or focus the chart and use the arrow keys to read a lap.'}
      </p>
      <ul className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted mt-1">
        <li><span className="inline-block w-3 h-3 align-middle mr-1" style={{ background: MEASURED }} />measured, within 1 s</li>
        <li><span className="inline-block w-3 h-3 align-middle mr-1" style={{ background: MEASURED, opacity: 0.4 }} />measured, 1 to 2 s</li>
        <li><span className="inline-block w-3 h-3 align-middle mr-1" style={{ background: MODELLED }} />assumed cost ({VISUAL_LABEL})</li>
        <li>blank = measured, no car within 2 s (a modelled 0 s cost, not an unavailable lap)</li>
        <li><span className="inline-block w-3 h-3 align-middle mr-1 border border-border" style={{ background: HATCH }} />{UNAVAILABLE} unavailable (safety car or no gap measured; never 0)</li>
      </ul>
      <details className="mt-3 text-xs">
        <summary className={`cursor-pointer ${FOCUS}`}>Lap table for {driverId}</summary>
        <div className="overflow-x-auto max-h-64 overflow-y-auto mt-2">
          <table className="w-full font-mono">
            <thead><tr className="text-left text-muted">
              <th className="pr-3">Lap</th><th className="pr-3">Within 1 s (measured)</th><th className="pr-3">1-2 s (measured)</th>
              <th className="pr-3">Cost (placeholder)</th><th>Reason</th></tr></thead>
            <tbody>
              {strip.columns.map(c => (
                <tr key={c.lap}>
                  <td className="pr-3">{c.lap}</td>
                  <td className="pr-3">{c.within1 == null ? UNAVAILABLE : `${Math.round(c.within1 * 100)}%`}</td>
                  <td className="pr-3">{c.within1to2 == null ? UNAVAILABLE : `${Math.round(c.within1to2 * 100)}%`}</td>
                  <td className="pr-3">{formatSeconds(c.cost, 3)}</td>
                  <td>{c.reason}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>
    </div>
  )
}
