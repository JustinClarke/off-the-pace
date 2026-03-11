import { useMemo, useState } from 'react'
import type { DriverSeries, SpanCohort } from './transform'
import { ERA_BOUNDARY } from './transform'

export const COHORT_STYLE: Record<SpanCohort, { color: string; label: string; hint: string }> = {
  bridge:      { color: '#34d399', label: 'Bridge',    hint: 'raced both sides of 2022 anchors the era calibration' },
  'full-span': { color: '#60a5fa', label: 'Full span', hint: 'present every season, not a calibration anchor' },
  joined:      { color: '#fbbf24', label: 'Joined',    hint: 'debuted after the opening season' },
  left:        { color: '#f472b6', label: 'Left',      hint: 'last season before the final year' },
  cameo:       { color: '#94a3b8', label: 'Cameo',     hint: 'single season only' },
}

const LANE_H = 22
const LANE_GAP = 4
const LABEL_W = 52
const AXIS_H = 22
const PAD_R = 16
const DOT_R = 4
const VBW = 760

interface Props {
  series: DriverSeries[]
  seasonRange: [number, number]
  selected: string[]
  onToggle: (driverId: string) => void
  colorOf: (driverId: string) => string
  hovered: string | null
  onHover: (driverId: string | null) => void
}

function laneHeight(count: number) {
  return count * (LANE_H + LANE_GAP)
}

function Lane({
  d, i, xFor, selectedSet, hovered, colorOf, onToggle, onHover,
}: {
  d: DriverSeries
  i: number
  xFor: (y: number) => number
  selectedSet: Set<string>
  hovered: string | null
  colorOf: (id: string) => string
  onToggle: (id: string) => void
  onHover: (id: string | null) => void
}) {
  const y = i * (LANE_H + LANE_GAP)
  const cy = y + LANE_H / 2
  const isSel = selectedSet.has(d.driver_id)
  const isHover = hovered === d.driver_id
  const style = COHORT_STYLE[d.cohort]
  const x1 = xFor(d.firstSeason)
  const x2 = xFor(d.lastSeason)
  const barW = Math.max(x2 - x1, 2)
  const opacity = isSel || isHover ? 1 : 0.32
  const markColor = isSel ? colorOf(d.driver_id) : style.color

  return (
    <g
      onClick={() => onToggle(d.driver_id)}
      onMouseEnter={() => onHover(d.driver_id)}
      onMouseLeave={() => onHover(null)}
      className="cursor-pointer"
    >
      <rect
        x={0} y={y - LANE_GAP / 2}
        width={VBW} height={LANE_H + LANE_GAP}
        rx={4}
        fill={isHover ? 'rgba(255,255,255,0.06)' : isSel ? 'rgba(255,255,255,0.025)' : 'transparent'}
        style={{ transition: 'fill 120ms' }}
      />
      <rect
        x={0} y={cy - 6}
        width={3} height={12} rx={1.5}
        fill={style.color}
        opacity={isSel || isHover ? 0.9 : 0.4}
      />
      <text
        x={LABEL_W - 8} y={cy + 3}
        textAnchor="end"
        style={{ fontSize: 11, fontWeight: isSel || isHover ? 700 : 500, opacity, fontFamily: 'ui-monospace, monospace' }}
        fill={isSel ? markColor : isHover ? 'rgb(var(--color-text))' : 'rgb(var(--color-text-muted))'}
      >
        {d.driver_id}
      </text>
      <rect x={x1} y={cy - 3} width={barW} height={6} rx={3} fill={markColor} opacity={opacity} />
      {d.activeSeasons.map(s => (
        <circle
          key={s}
          cx={xFor(s)} cy={cy}
          r={isSel ? DOT_R : DOT_R - 1}
          fill={markColor}
          opacity={opacity}
          stroke={isSel ? 'rgb(var(--color-bg))' : 'none'}
          strokeWidth={isSel ? 1.5 : 0}
        />
      ))}
    </g>
  )
}

export default function CareerSpanTimeline({
  series, seasonRange, selected, onToggle, colorOf, hovered, onHover,
}: Props) {
  const [expanded, setExpanded] = useState(false)

  const [first, last] = seasonRange
  const years = useMemo(
    () => Array.from({ length: last - first + 1 }, (_, i) => first + i),
    [first, last],
  )

  const plotW = VBW - LABEL_W - PAD_R
  const xFor = (year: number) => {
    if (last === first) return LABEL_W
    return LABEL_W + ((year - first) / (last - first)) * plotW
  }
  const eraX = xFor(ERA_BOUNDARY)

  // Selected lanes always visible; unselected go in the collapsible section
  const selectedSet = useMemo(() => new Set(selected), [selected])
  const lanes = useMemo(() => {
    const sel = series.filter(s => selected.includes(s.driver_id))
    const rest = series.filter(s => !selected.includes(s.driver_id))
    return { sel, rest }
  }, [series, selected])

  const axisVBH = AXIS_H + 4
  const selH = laneHeight(lanes.sel.length)
  const restH = laneHeight(lanes.rest.length)

  // Shared x-axis + 2022 line rendered once at the top
  const AxisSVG = (
    <svg
      viewBox={`0 0 ${VBW} ${axisVBH}`}
      className="w-full"
      style={{ minWidth: 520, height: axisVBH, display: 'block' }}
      aria-hidden
    >
      {years.map(y => {
        const x = xFor(y)
        return (
          <g key={y}>
            <text x={x} y={12} textAnchor="middle" style={{ fontSize: 10, fill: 'rgb(var(--color-text-muted))' }}>
              {y}
            </text>
          </g>
        )
      })}
      <text x={eraX} y={AXIS_H - 8} textAnchor="middle" style={{ fontSize: 9, fontWeight: 600, fill: 'rgba(52,211,153,0.7)' }}>
        2022 regs
      </text>
    </svg>
  )

  // Shared gridlines rendered behind both lane blocks
  function GridLines({ height }: { height: number }) {
    return (
      <>
        {years.map(y => {
          const x = xFor(y)
          return (
            <line key={y} x1={x} x2={x} y1={0} y2={height} stroke="rgba(255,255,255,0.05)" strokeWidth={1} />
          )
        })}
        <line x1={eraX} x2={eraX} y1={0} y2={height} stroke="rgba(52,211,153,0.45)" strokeWidth={1.5} strokeDasharray="5 3" />
      </>
    )
  }

  return (
    <div className="w-full overflow-x-auto">
      {/* Year axis */}
      {AxisSVG}

      {/* Selected lanes always visible */}
      {lanes.sel.length > 0 && (
        <svg
          viewBox={`0 0 ${VBW} ${selH}`}
          className="w-full"
          style={{ minWidth: 520, height: selH, display: 'block' }}
          aria-label="Selected driver career spans"
        >
          <GridLines height={selH} />
          {lanes.sel.map((d, i) => (
            <Lane key={d.driver_id} d={d} i={i} xFor={xFor} selectedSet={selectedSet} hovered={hovered} colorOf={colorOf} onToggle={onToggle} onHover={onHover} />
          ))}
        </svg>
      )}

      {/* Expander trigger */}
      {lanes.rest.length > 0 && (
        <>
          <button
            onClick={() => setExpanded(o => !o)}
            className="flex items-center gap-2 mt-1 mb-0.5 text-xs text-muted/60 hover:text-muted transition-colors"
          >
            <svg
              width="12" height="12" viewBox="0 0 12 12" fill="none"
              style={{ transition: 'transform 220ms ease', transform: expanded ? 'rotate(180deg)' : 'rotate(0deg)' }}
            >
              <path d="M2 4L6 8L10 4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
            {expanded ? 'Show fewer' : `Show ${lanes.rest.length} more drivers`}
          </button>

          {/* Collapsible rest CSS max-height transition */}
          <div
            style={{
              maxHeight: expanded ? restH + 8 : 0,
              overflow: 'hidden',
              transition: 'max-height 320ms cubic-bezier(0.4, 0, 0.2, 1)',
            }}
          >
            <svg
              viewBox={`0 0 ${VBW} ${restH}`}
              className="w-full"
              style={{ minWidth: 520, height: restH, display: 'block' }}
              aria-label="Additional driver career spans"
            >
              <GridLines height={restH} />
              {lanes.rest.map((d, i) => (
                <Lane key={d.driver_id} d={d} i={i} xFor={xFor} selectedSet={selectedSet} hovered={hovered} colorOf={colorOf} onToggle={onToggle} onHover={onHover} />
              ))}
            </svg>
          </div>
        </>
      )}
    </div>
  )
}
