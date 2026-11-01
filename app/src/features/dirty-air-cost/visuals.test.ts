import { describe, it, expect } from 'vitest'
import { driverBars, lapStrip, formulaLine, VISUAL_LABEL } from './visuals'
import type { DirtyAirResult } from './transform'
import type { DirtyAirLapRow } from './queries'

const res = (id: string, total: number | null, reasons: string | null = null): DirtyAirResult => ({
  rank: 0, driver_id: id, total_placeholder_cost_s: total, avg_placeholder_cost_s: total == null ? null : total / 50,
  laps_modelled: total == null ? 0 : 50, laps_unavailable: total == null ? 60 : 3, total_laps: 60,
  unavailable_reasons: reasons, constructor_id: 'X', car_factor: '1.00', tyre_factors: '-', factor_flags: null,
  value_label: total == null ? 'unavailable' : 'modelled',
})
const lap = (n: number, o: Partial<DirtyAirLapRow> = {}): DirtyAirLapRow => ({
  lap_number: n, share_lap_within_1s: 0.5, share_lap_within_2s: 0.8, wake_exposure: 0.65,
  wake_cost_placeholder_s: 0.2, loss_s_per_lap_within_1s: 0.3, race_loss_s_per_lap_within_1s: 0.3,
  compound_class: 'MEDIUM', tyre_c_number: null, compound_factor: 1, constructor_factor: 1, unavailable_reason: null, ...o,
})

describe('driverBars', () => {
  const bars = driverBars([res('A', 20), res('B', 10), res('C', null, 'no gap measured'), res('D', 5), res('E', 1)])
  it('keeps table order and scales to the largest bar', () => {
    expect(bars.map(b => b.driver_id)).toEqual(['A', 'B', 'C', 'D', 'E'])
    expect(bars[0].fraction).toBe(1)
    expect(bars[1].fraction).toBe(0.5)
  })
  it('never draws a bar for an unavailable driver and gives the reason', () => {
    expect(bars[2].fraction).toBeNull()
    expect(bars[2].value).toBeNull()
    expect(bars[2].reason).toBe('no gap measured')
  })
  it('direct-labels only the top few', () => {
    expect(bars.filter(b => b.label).map(b => b.driver_id)).toEqual(['A', 'B'])
    expect(bars[2].label).toBe('')
  })
  it('fractions stay within 0..1 and tooltips carry the placeholder label', () => {
    for (const b of bars) {
      if (b.fraction != null) { expect(b.fraction).toBeGreaterThanOrEqual(0); expect(b.fraction).toBeLessThanOrEqual(1) }
      expect(b.tooltip[0]).toContain(VISUAL_LABEL)
      expect(b.tooltip.join(' ')).toMatch(/laps with a value/)
    }
  })
  it('handles an all-zero field without NaN', () => {
    expect(driverBars([res('A', 0)])[0].fraction).toBe(0)
  })
})

describe('lapStrip', () => {
  const s = lapStrip([
    lap(1), lap(2, { wake_cost_placeholder_s: null, share_lap_within_1s: null, share_lap_within_2s: null, wake_exposure: null, unavailable_reason: 'safety car' }),
    lap(3, { wake_cost_placeholder_s: 0.3, share_lap_within_1s: 1, share_lap_within_2s: 1 }),
  ])
  it('marks unavailable laps with a reason and no cost', () => {
    const c = s.columns[1]
    expect(c.available).toBe(false)
    expect(c.cost).toBeNull()
    expect(c.costFraction).toBeNull()
    expect(c.reason).toBe('safety car')
    expect(c.readout).toContain('—')
  })
  it('keeps shares and cost fractions in bounds', () => {
    for (const c of s.columns.filter(c => c.available)) {
      expect((c.within1 as number) + (c.within1to2 as number)).toBeLessThanOrEqual(1.0000001)
      expect(c.costFraction).toBeGreaterThanOrEqual(0)
      expect(c.costFraction).toBeLessThanOrEqual(1)
    }
    expect(s.costTop).toBe(0.3)
  })
  it('readouts label the cost as placeholder', () => {
    expect(s.columns[0].readout).toContain(VISUAL_LABEL)
  })
})

describe('formulaLine', () => {
  it('states race value, tyre and car factors', () => {
    expect(formulaLine([lap(1)])).toBe('Assumed race value 0.30s x tyre factor (MEDIUM x1.00) x car factor 1.00')
    // WC-16: a lap with a C-number shows it beside the class
    expect(formulaLine([lap(1, { compound_class: 'SOFT', tyre_c_number: 'C4', compound_factor: 1.1 })]))
      .toBe('Assumed race value 0.30s x tyre factor (SOFT (C4) x1.10) x car factor 1.00')
  })
  it('says unavailable when no lap has a value', () => {
    expect(formulaLine([lap(1, { wake_cost_placeholder_s: null })])).toContain('—')
  })
})
