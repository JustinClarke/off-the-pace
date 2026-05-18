import { useRef, useState } from 'react'

export type StrategyVerdict = 'optimal' | 'overran' | 'unknown' | null

export interface GanttStint {
  /** y-axis identity */
  driverId: string
  stintNumber: number
  /** absolute lap numbers (1-based) */
  startLap: number
  endLap: number
  compound: string
  /** from int_pit_strategy_value */
  verdict: StrategyVerdict
  overrunLaps: number | null
  opportunityCostS: number | null
  optimalPitLapInStint: number | null
  cliffLapInStint: number | null
  pitDurationS: number | null
  tyreManagementScore: number | null
}

export interface GanttProps {
  stints: GanttStint[]
  totalLaps: number
  compoundColor: (compound: string) => string
}

const VERDICT_COLORS: Record<string, string> = {
  optimal: 'rgb(52, 211, 153)',   // emerald-400
  overran: 'rgb(248, 113, 113)',  // red-400
  unknown: 'rgb(100, 116, 139)',  // slate-500
}
const ROW_H = 24
const ROW_GAP = 6
const LABEL_W = 52
const PADDING = { top: 8, right: 20, bottom: 36, left: LABEL_W + 8 }

function verdictLabel(v: StrategyVerdict): string {
  if (v === 'optimal') return 'Optimal'
  if (v === 'overran') return 'Overran'
  return 'Unknown'
}

interface TooltipState {
  x: number
  y: number
  stint: GanttStint
}

export default function Gantt({ stints, totalLaps, compoundColor }: GanttProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const [tooltip, setTooltip] = useState<TooltipState | null>(null)

  const drivers = Array.from(new Set(stints.map(s => s.driverId))).sort()
  const driverIndex = Object.fromEntries(drivers.map((d, i) => [d, i]))

  const svgH = PADDING.top + drivers.length * (ROW_H + ROW_GAP) + PADDING.bottom
  const lapRange = Math.max(totalLaps, 1)

  const lapX = (lap: number, totalW: number) =>
    PADDING.left + ((lap-1) / lapRange) * totalW

  const rowY = (driverIdx: number) =>
    PADDING.top + driverIdx * (ROW_H + ROW_GAP)

  const showTooltip = (e: React.MouseEvent, stint: GanttStint) => {
    const rect = containerRef.current?.getBoundingClientRect()
    if (!rect) return
    setTooltip({ x: e.clientX-rect.left, y: e.clientY-rect.top, stint })
  }

  return (
    <div ref={containerRef} className="relative select-none">
      {/* Legend */}
      <div className="flex flex-wrap gap-4 mb-4 text-xs text-muted">
        <span className="font-medium text-[rgb(var(--color-text))]">Verdict:</span>
        {(['optimal', 'overran', 'unknown'] as const).map(v => (
          <span key={v} className="flex items-center gap-1.5">
            <span className="inline-block w-2.5 h-2.5 rounded-sm" style={{ background: VERDICT_COLORS[v] }} />
            {verdictLabel(v)}
          </span>
        ))}
        <span className="ml-4 font-medium text-[rgb(var(--color-text))]">Bar fill:</span>
        <span className="text-muted">compound colour</span>
        <span className="text-muted">| border:</span>
        <span className="text-muted">decision quality</span>
      </div>

      <div className="w-full overflow-x-auto">
        <svg
          width="100%"
          height={svgH}
          viewBox={`0 0 800 ${svgH}`}
          preserveAspectRatio="none"
          className="block"
          onMouseLeave={() => setTooltip(null)}
        >
          {/* Lap axis ticks */}
          {Array.from({ length: Math.min(11, lapRange + 1) }, (_: unknown, i: number) => {
            const lap = Math.round((i / 10) * lapRange) + 1
            return (
              <g key={i}>
                <line
                  x1={PADDING.left + (i / 10) * (800-PADDING.left-PADDING.right)}
                  y1={PADDING.top}
                  x2={PADDING.left + (i / 10) * (800-PADDING.left-PADDING.right)}
                  y2={svgH-PADDING.bottom}
                  stroke="rgba(255,255,255,0.06)"
                  strokeWidth={1}
                />
                <text
                  x={PADDING.left + (i / 10) * (800-PADDING.left-PADDING.right)}
                  y={svgH-PADDING.bottom + 14}
                  textAnchor="middle"
                  fontSize={10}
                  fill="rgb(100,116,139)"
                >
                  {i === 0 ? 'Lap 1' : lap}
                </text>
              </g>
            )
          })}

          {/* Axis label */}
          <text
            x={400}
            y={svgH-4}
            textAnchor="middle"
            fontSize={10}
            fill="rgb(100,116,139)"
          >
            Race lap
          </text>

          {/* Driver labels + rows */}
          {drivers.map(driver => {
            const di = driverIndex[driver]
            const y = rowY(di)
            const driverStints = stints.filter(s => s.driverId === driver)

            return (
              <g key={driver}>
                {/* Driver label */}
                <text
                  x={LABEL_W}
                  y={y + ROW_H / 2 + 4}
                  textAnchor="end"
                  fontSize={11}
                  fontFamily="monospace"
                  fill="rgb(var(--color-text, 220,220,230))"
                >
                  {driver}
                </text>

                {/* Row background */}
                <rect
                  x={PADDING.left}
                  y={y}
                  width={800-PADDING.left-PADDING.right}
                  height={ROW_H}
                  fill="rgba(255,255,255,0.02)"
                  rx={2}
                />

                {/* Stint bars */}
                {driverStints.map(stint => {
                  const totalW = 800-PADDING.left-PADDING.right
                  const x1 = lapX(stint.startLap, totalW)
                  const x2 = lapX(stint.endLap + 1, totalW)
                  const w = Math.max(x2-x1-1, 2)
                  const fillColor = compoundColor(stint.compound)
                  const strokeColor = VERDICT_COLORS[stint.verdict ?? 'unknown']

                  // Cliff marker (vertical tick inside bar)
                  const cliffX = stint.cliffLapInStint != null
                    ? x1 + (stint.cliffLapInStint / Math.max(stint.endLap-stint.startLap + 1, 1)) * w
                    : null

                  // Optimal pit marker
                  const optLapInStint = stint.optimalPitLapInStint
                  const optX = optLapInStint != null
                    ? x1 + (optLapInStint / Math.max(stint.endLap-stint.startLap + 1, 1)) * w
                    : null

                  return (
                    <g key={`${driver}-${stint.stintNumber}`}>
                      {/* Main bar */}
                      <rect
                        x={x1}
                        y={y + 2}
                        width={w}
                        height={ROW_H-4}
                        fill={fillColor}
                        fillOpacity={0.75}
                        stroke={strokeColor}
                        strokeWidth={1.5}
                        rx={2}
                        style={{ cursor: 'pointer' }}
                        onMouseMove={e => showTooltip(e, stint)}
                        onMouseLeave={() => setTooltip(null)}
                      />

                      {/* Cliff onset marker */}
                      {cliffX != null && (
                        <line
                          x1={cliffX}
                          y1={y + 4}
                          x2={cliffX}
                          y2={y + ROW_H-4}
                          stroke="rgba(255,255,255,0.8)"
                          strokeWidth={1}
                          strokeDasharray="2,2"
                          style={{ pointerEvents: 'none' }}
                        />
                      )}

                      {/* Optimal pit marker (triangle below bar) */}
                      {optX != null && (
                        <polygon
                          points={`${optX},${y + ROW_H} ${optX-3},${y + ROW_H + 5} ${optX + 3},${y + ROW_H + 5}`}
                          fill="rgb(52,211,153)"
                          fillOpacity={0.7}
                          style={{ pointerEvents: 'none' }}
                        />
                      )}

                      {/* Compound label inside bar (if wide enough) */}
                      {w > 28 && (
                        <text
                          x={x1 + w / 2}
                          y={y + ROW_H / 2 + 4}
                          textAnchor="middle"
                          fontSize={9}
                          fontFamily="monospace"
                          fill="rgba(0,0,0,0.75)"
                          style={{ pointerEvents: 'none' }}
                        >
                          {stint.compound.slice(0, 1)}
                        </text>
                      )}
                    </g>
                  )
                })}
              </g>
            )
          })}
        </svg>
      </div>

      {/* Marker legend */}
      <div className="flex gap-4 mt-2 text-xs text-muted">
        <span className="flex items-center gap-1.5">
          <span className="inline-block w-4 border-t border-dashed border-white/60" />
          Cliff onset
        </span>
        <span className="flex items-center gap-1.5">
          <svg width="10" height="8" className="inline-block">
            <polygon points="5,0 2,7 8,7" fill="rgb(52,211,153)" fillOpacity={0.7} />
          </svg>
          Optimal pit window
        </span>
      </div>

      {/* Tooltip */}
      {tooltip && (
        <div
          className="absolute z-10 pointer-events-none bg-[rgb(var(--color-bg-elevated,28,28,32))] border border-border rounded px-3 py-2 text-xs shadow-lg max-w-[220px]"
          style={{ left: tooltip.x + 12, top: tooltip.y-8 }}
        >
          <p className="font-mono font-medium text-[rgb(var(--color-text))]">
            {tooltip.stint.driverId} · Stint {tooltip.stint.stintNumber}
          </p>
          <p className="text-muted mt-0.5">
            Laps {tooltip.stint.startLap}&ndash;{tooltip.stint.endLap}
            {' '}({tooltip.stint.endLap-tooltip.stint.startLap + 1} laps)
          </p>
          <p className="mt-1">
            <span className="text-muted">Compound: </span>
            <span className="font-mono">{tooltip.stint.compound}</span>
          </p>
          {tooltip.stint.verdict && (
            <p>
              <span className="text-muted">Decision: </span>
              <span
                className="font-mono"
                style={{ color: VERDICT_COLORS[tooltip.stint.verdict ?? 'unknown'] }}
              >
                {verdictLabel(tooltip.stint.verdict)}
              </span>
            </p>
          )}
          {tooltip.stint.overrunLaps != null && tooltip.stint.overrunLaps > 0 && (
            <p>
              <span className="text-muted">Overrun: </span>
              <span className="font-mono text-red-400">{tooltip.stint.overrunLaps} laps</span>
            </p>
          )}
          {tooltip.stint.opportunityCostS != null && tooltip.stint.opportunityCostS > 0 && (
            <p>
              <span className="text-muted">Cost: </span>
              <span className="font-mono text-red-400">+{tooltip.stint.opportunityCostS.toFixed(1)} s</span>
            </p>
          )}
          {tooltip.stint.pitDurationS != null && (
            <p>
              <span className="text-muted">Pit time: </span>
              <span className="font-mono">{tooltip.stint.pitDurationS.toFixed(1)} s</span>
            </p>
          )}
          {tooltip.stint.tyreManagementScore != null && (
            <p>
              <span className="text-muted">Mgmt score: </span>
              <span className="font-mono">{tooltip.stint.tyreManagementScore.toFixed(3)}</span>
            </p>
          )}
        </div>
      )}
    </div>
  )
}
