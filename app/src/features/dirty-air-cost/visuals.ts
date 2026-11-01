import type { DirtyAirResult } from './transform'
import { UNAVAILABLE, formatSeconds } from './transform'
import type { DirtyAirLapRow } from './queries'

/** Label printed on both visuals. Nothing here is measured except the exposure. */
export const VISUAL_LABEL = 'placeholder, modelled'

export interface DriverBar {
  driver_id: string
  /** Seconds, or null when the driver has no value (never 0). */
  value: number | null
  /** Bar length as a fraction of the largest bar, 0..1; null when no value. */
  fraction: number | null
  /** Direct label on the bar (top few drivers only); '' otherwise. */
  label: string
  /** Why there is no bar; '' when there is a value. */
  reason: string
  tooltip: string[]
}

/** Bars in table order (rows are already sorted by transform). Top `labelTop` get a direct label. */
export function driverBars(rows: DirtyAirResult[], labelTop = 3): DriverBar[] {
  const max = rows.reduce((m, r) => Math.max(m, r.total_placeholder_cost_s ?? 0), 0)
  return rows.map((r, i) => {
    const v = r.total_placeholder_cost_s
    const has = v != null
    return {
      driver_id: r.driver_id,
      value: has ? v : null,
      fraction: has && max > 0 ? Math.min(1, Math.max(0, v / max)) : has ? 0 : null,
      label: has && i < labelTop ? formatSeconds(v, 1) : '',
      reason: has ? '' : (r.unavailable_reasons ?? 'no reason recorded'),
      tooltip: [
        `${r.driver_id} (${VISUAL_LABEL})`,
        `Total ${formatSeconds(v)}`,
        `Avg/lap ${formatSeconds(r.avg_placeholder_cost_s, 3)}`,
        `${r.laps_modelled} laps with a value, ${r.laps_unavailable} unavailable${
          r.laps_unavailable && r.unavailable_reasons ? ` (${UNAVAILABLE}: ${r.unavailable_reasons})` : ''}`,
      ],
    }
  })
}

export interface LapColumn {
  lap: number
  available: boolean
  /** Measured share of the lap within 1 s, 0..1 (null when unavailable). */
  within1: number | null
  /** Measured share between 1 and 2 s, 0..1 (null when unavailable). */
  within1to2: number | null
  /** Assumed cost, seconds (null when unavailable, never 0). */
  cost: number | null
  /** Cost as a fraction of the strip's top (0..1). */
  costFraction: number | null
  reason: string
  /** Readout lines for hover / keyboard / screen readers. */
  readout: string
}

export interface LapStrip {
  columns: LapColumn[]
  /** Top of the cost strip in seconds: the largest per-lap assumed loss (the cost can never exceed it). */
  costTop: number
}

const clamp01 = (x: number) => Math.min(1, Math.max(0, x))

export function lapStrip(rows: DirtyAirLapRow[]): LapStrip {
  const costTop = rows.reduce((m, r) => Math.max(m, r.loss_s_per_lap_within_1s ?? 0), 0)
  const columns = rows.map((r): LapColumn => {
    const available = r.wake_cost_placeholder_s != null && r.share_lap_within_1s != null && r.share_lap_within_2s != null
    if (!available) {
      const reason = r.unavailable_reason ?? 'no reason recorded'
      return {
        lap: r.lap_number, available: false, within1: null, within1to2: null,
        cost: null, costFraction: null, reason,
        readout: `Lap ${r.lap_number}: ${UNAVAILABLE} ${reason}`,
      }
    }
    const w1 = clamp01(r.share_lap_within_1s as number)
    const w2 = clamp01(r.share_lap_within_2s as number)
    const cost = r.wake_cost_placeholder_s as number
    return {
      lap: r.lap_number, available: true,
      within1: w1, within1to2: Math.max(0, w2 - w1),
      cost, costFraction: costTop > 0 ? clamp01(cost / costTop) : 0, reason: '',
      readout: `Lap ${r.lap_number}: measured ${Math.round(w1 * 100)}% of the lap within 1 s, ${
        Math.round(Math.max(0, w2 - w1) * 100)}% between 1 and 2 s. Assumed (${VISUAL_LABEL}): ${
        (r.loss_s_per_lap_within_1s ?? 0).toFixed(2)}s x exposure ${(r.wake_exposure ?? 0).toFixed(2)} = ${
        formatSeconds(cost, 3)}`,
    }
  })
  return { columns, costTop }
}

/** The formula line for the selected driver: assumed race value x tyre x car. */
export function formulaLine(rows: DirtyAirLapRow[]): string {
  const modelled = rows.filter(r => r.wake_cost_placeholder_s != null)
  if (!modelled.length) return `No lap has a value ${UNAVAILABLE}`
  const race = modelled[0].race_loss_s_per_lap_within_1s
  const tyres = Array.from(new Set(modelled.map(r => `${r.compound_class ?? 'unresolved'}${r.tyre_c_number ? ` (${r.tyre_c_number})` : ''} x${(r.compound_factor ?? 1).toFixed(2)}`))).sort()
  const cars = Array.from(new Set(modelled.map(r => (r.constructor_factor ?? 1).toFixed(2))))
  return `Assumed race value ${race == null ? UNAVAILABLE : race.toFixed(2) + 's'} x tyre factor (${tyres.join(', ')}) x car factor ${cars.join(', ')}`
}
