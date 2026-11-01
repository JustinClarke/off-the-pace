import { useState } from 'react'
import { UNAVAILABLE, formatSeconds } from './transform'
import type { DirtyAirResult } from './transform'

const FOCUS = 'focus:outline-none focus-visible:ring-2 focus-visible:ring-accent rounded'
const PILL = 'inline-block rounded-full border px-2 py-0.5 text-[10px] leading-none uppercase tracking-wider whitespace-nowrap'
const PILL_MODELLED = `${PILL} border-amber-600/50 text-amber-700 dark:border-amber-400/50 dark:text-amber-400`
const PILL_NA = `${PILL} border-border text-muted`

/** Detail row id (aria-controls target). */
const detailId = (driverId: string) => `dac-detail-${driverId}`

function Chevron({ open }: { open: boolean }) {
  return (
    <svg
      aria-hidden="true" viewBox="0 0 12 12" width="12" height="12"
      className={`shrink-0 transition-transform ${open ? 'rotate-90' : ''}`}
      fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"
    >
      <path d="M4 2l4 4-4 4" />
    </svg>
  )
}

function Detail({ r }: { r: DirtyAirResult }) {
  const item = (label: string, value: React.ReactNode) => (
    <div className="min-w-0">
      <dt className="text-[10px] uppercase tracking-wider text-muted">{label}</dt>
      <dd className="font-mono text-xs break-words">{value}</dd>
    </div>
  )
  return (
    <dl className="grid grid-cols-1 sm:grid-cols-2 gap-x-6 gap-y-2">
      {item('Tyre factor (assumed)', r.factor_flags
        ? <span title={r.factor_flags}>{`${r.tyre_factors} (flagged: ${r.factor_flags})`}</span>
        : r.tyre_factors)}
      {item('Car factor', r.car_factor)}
      {item('Laps with a value', r.laps_modelled)}
      {item('Laps unavailable', r.laps_unavailable
        ? `${r.laps_unavailable} (${UNAVAILABLE}: ${r.unavailable_reasons ?? 'no reason recorded'})`
        : '0')}
      {item('Total laps', r.total_laps)}
    </dl>
  )
}

/**
 * Per-driver table, collapsed to the essentials; a row expands inline (disclosure pattern:
 * a real button in the driver cell carries aria-expanded / aria-controls, and a click anywhere
 * on the row toggles it). Several rows can be open. The selected driver (from the bar chart)
 * is highlighted. Unavailable totals stay "—" with a reason in the detail, never 0.
 */
export default function DriverCostTable({ rows, selected }: { rows: DirtyAirResult[]; selected?: string | null }) {
  const [open, setOpen] = useState<ReadonlySet<string>>(new Set())
  const toggle = (id: string) => setOpen(prev => {
    const next = new Set(prev)
    if (next.has(id)) next.delete(id)
    else next.add(id)
    return next
  })
  const num = 'py-2 px-3 text-right font-mono tabular-nums whitespace-nowrap'
  return (
    <table className="w-full text-sm border-collapse">
      <caption className="sr-only">Placeholder wake cost by driver (modelled). Select a row to show its detail.</caption>
      <thead>
        <tr className="border-b border-border text-xs font-medium text-muted">
          <th scope="col" className="py-2 px-3 text-right hidden sm:table-cell w-10">#</th>
          <th scope="col" className="py-2 px-3 text-left">Driver</th>
          <th scope="col" className="py-2 px-3 text-left hidden sm:table-cell">Team</th>
          <th scope="col" className="py-2 px-3 text-right">Total (placeholder)</th>
          <th scope="col" className="py-2 px-3 text-right">Avg/lap (placeholder)</th>
          <th scope="col" className="py-2 px-3 text-left hidden sm:table-cell">Label</th>
        </tr>
      </thead>
      {rows.map(r => {
        const isOpen = open.has(r.driver_id)
        const id = detailId(r.driver_id)
        const na = r.total_placeholder_cost_s == null
        return (
          <tbody key={r.driver_id} className="border-b border-border/50">
            <tr
              data-driver={r.driver_id}
              onClick={() => toggle(r.driver_id)}
              className={`h-11 cursor-pointer hover:bg-surface ${selected === r.driver_id ? 'bg-accent/10' : ''}`}
            >
              <td className="py-2 px-3 text-right font-mono tabular-nums text-muted hidden sm:table-cell">{r.rank}</td>
              <td className="py-2 px-3 text-left">
                <button
                  type="button"
                  aria-expanded={isOpen}
                  aria-controls={id}
                  className={`flex items-center gap-2 font-mono ${FOCUS}`}
                >
                  <Chevron open={isOpen} />
                  <span>{r.driver_id}</span>
                </button>
              </td>
              <td className="py-2 px-3 text-left font-mono text-muted hidden sm:table-cell">{r.constructor_id ?? UNAVAILABLE}</td>
              <td className={num}>{formatSeconds(r.total_placeholder_cost_s)}</td>
              <td className={num}>{formatSeconds(r.avg_placeholder_cost_s, 3)}</td>
              <td className="py-2 px-3 text-left hidden sm:table-cell">
                <span className={na ? PILL_NA : PILL_MODELLED} title={na ? (r.unavailable_reasons ?? undefined) : undefined}>
                  {r.value_label}
                </span>
              </td>
            </tr>
            <tr id={id} hidden={!isOpen}>
              <td colSpan={6} className="px-3 pb-3 pt-1 bg-surface/50">
                <Detail r={r} />
              </td>
            </tr>
          </tbody>
        )
      })}
    </table>
  )
}
