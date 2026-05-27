import { useState } from 'react'
import type { ReactNode } from 'react'

export interface HeatmapCell {
  x: number
  y: number
  value: number | null
  /** Override computed color (for categorical scales) */
  color?: string
}

export interface HeatmapProps {
  xLabels: string[]
  yLabels: string[]
  cells: HeatmapCell[]
  minValue?: number
  maxValue?: number
  /**
   * diverging: green (negative) → neutral → red (positive) use for pace deltas
   * sequential: dim-blue → bright-blue use for rates/counts
   */
  colorMode?: 'diverging' | 'sequential'
  cellWidth?: number
  cellHeight?: number
  yLabelWidth?: number
  formatValue?: (v: number) => string
  renderTooltip?: (cell: HeatmapCell, xLabel: string, yLabel: string) => ReactNode
  showLegend?: boolean
  legendLabel?: string
  emptyMessage?: string
}

// ─── colour helpers ──────────────────────────────────────────────────────────

const NEUTRAL: [number, number, number] = [28, 30, 38]
const GREEN:   [number, number, number] = [34, 197, 94]
const RED:     [number, number, number] = [239, 68, 68]
const BLUE_DIM:[number, number, number] = [30, 58, 138]
const BLUE_LT: [number, number, number] = [96, 165, 250]

function lerp(a: number, b: number, t: number): number {
  return Math.round(a + (b - a) * Math.max(0, Math.min(1, t)))
}

function rgbStr(c: [number, number, number]): string {
  return `rgb(${c[0]},${c[1]},${c[2]})`
}

function divergingColor(value: number, maxAbs: number): string {
  if (maxAbs === 0) return rgbStr(NEUTRAL)
  const t = Math.abs(value) / maxAbs
  const target = value < 0 ? GREEN : RED
  return `rgb(${lerp(NEUTRAL[0], target[0], t)},${lerp(NEUTRAL[1], target[1], t)},${lerp(NEUTRAL[2], target[2], t)})`
}

function sequentialColor(value: number, min: number, max: number): string {
  const t = max === min ? 0.5 : (value - min) / (max - min)
  return `rgb(${lerp(BLUE_DIM[0], BLUE_LT[0], t)},${lerp(BLUE_DIM[1], BLUE_LT[1], t)},${lerp(BLUE_DIM[2], BLUE_LT[2], t)})`
}

// ─── component ───────────────────────────────────────────────────────────────

export default function Heatmap({
  xLabels,
  yLabels,
  cells,
  minValue,
  maxValue,
  colorMode = 'diverging',
  cellWidth = 30,
  cellHeight = 26,
  yLabelWidth = 96,
  renderTooltip,
  showLegend = true,
  legendLabel,
  emptyMessage = 'No data',
}: HeatmapProps) {
  const [tooltip, setTooltip] = useState<{ cell: HeatmapCell; mx: number; my: number } | null>(null)

  const cellMap = new Map<string, HeatmapCell>()
  for (const c of cells) cellMap.set(`${c.y},${c.x}`, c)

  const vals = cells
    .filter(c => c.value !== null && c.color === undefined)
    .map(c => c.value as number)

  const dataMin = minValue ?? (vals.length ? Math.min(...vals) : 0)
  const dataMax = maxValue ?? (vals.length ? Math.max(...vals) : 0)
  const maxAbs = Math.max(Math.abs(dataMin), Math.abs(dataMax))

  function cellBg(cell: HeatmapCell | undefined): string {
    if (!cell || cell.value === null) return 'rgba(255,255,255,0.03)'
    if (cell.color) return cell.color
    return colorMode === 'diverging'
      ? divergingColor(cell.value, maxAbs)
      : sequentialColor(cell.value, dataMin, dataMax)
  }

  if (!cells.length) {
    return <p className="text-sm text-muted py-4">{emptyMessage}</p>
  }

  return (
    <div className="relative">
      <div className="overflow-x-auto">
        <table style={{ borderCollapse: 'separate', borderSpacing: 1 }}>
          <thead>
            <tr>
              {/* corner */}
              <th style={{ minWidth: yLabelWidth }} />
              {xLabels.map((xl, xi) => (
                <th key={xi} style={{ width: cellWidth, minWidth: cellWidth, padding: 0, verticalAlign: 'bottom' }}>
                  <div style={{
                    writingMode: 'vertical-rl',
                    transform: 'rotate(180deg)',
                    fontSize: 10,
                    color: 'rgb(var(--color-text-muted))',
                    whiteSpace: 'nowrap',
                    maxHeight: 90,
                    overflow: 'hidden',
                    padding: '2px 0',
                  }}>
                    {xl}
                  </div>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {yLabels.map((yl, yi) => (
              <tr key={yi}>
                <td style={{
                  minWidth: yLabelWidth,
                  paddingRight: 8,
                  textAlign: 'right',
                  fontSize: 11,
                  color: 'rgb(var(--color-text-muted))',
                  whiteSpace: 'nowrap',
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                  maxWidth: yLabelWidth,
                }}>
                  {yl}
                </td>
                {xLabels.map((_xl, xi) => {
                  const cell = cellMap.get(`${yi},${xi}`)
                  return (
                    <td
                      key={xi}
                      title={undefined}
                      style={{
                        width: cellWidth,
                        minWidth: cellWidth,
                        height: cellHeight,
                        backgroundColor: cellBg(cell),
                        borderRadius: 2,
                        cursor: cell ? 'default' : 'default',
                      }}
                      onMouseEnter={e => cell && setTooltip({ cell, mx: e.clientX, my: e.clientY })}
                      onMouseMove={e => cell && setTooltip(t => t ? { ...t, mx: e.clientX, my: e.clientY } : null)}
                      onMouseLeave={() => setTooltip(null)}
                    />
                  )
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Legend */}
      {showLegend && colorMode === 'diverging' && maxAbs > 0 && (
        <div className="mt-3 flex items-center gap-2 text-xs text-muted">
          {legendLabel && <span className="opacity-60">{legendLabel}:</span>}
          <span style={{ color: rgbStr(GREEN) }}>−{maxAbs.toFixed(2)}s</span>
          <div style={{
            width: 72,
            height: 8,
            borderRadius: 3,
            background: `linear-gradient(to right, ${rgbStr(GREEN)}, ${rgbStr(NEUTRAL)}, ${rgbStr(RED)})`,
          }} />
          <span style={{ color: rgbStr(RED) }}>+{maxAbs.toFixed(2)}s</span>
        </div>
      )}
      {showLegend && colorMode === 'sequential' && (
        <div className="mt-3 flex items-center gap-2 text-xs text-muted">
          {legendLabel && <span className="opacity-60">{legendLabel}:</span>}
          <span>{dataMin.toFixed(2)}</span>
          <div style={{
            width: 72,
            height: 8,
            borderRadius: 3,
            background: `linear-gradient(to right, ${rgbStr(BLUE_DIM)}, ${rgbStr(BLUE_LT)})`,
          }} />
          <span>{dataMax.toFixed(2)}</span>
        </div>
      )}

      {/* Floating tooltip */}
      {tooltip && renderTooltip && (
        <div
          style={{
            position: 'fixed',
            left: tooltip.mx + 14,
            top: tooltip.my + 14,
            zIndex: 9999,
            pointerEvents: 'none',
          }}
        >
          {renderTooltip(tooltip.cell, xLabels[tooltip.cell.x], yLabels[tooltip.cell.y])}
        </div>
      )}
    </div>
  )
}
