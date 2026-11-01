import { describe, it, expect } from 'vitest'
import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import {
  transform, totals, toCsvRows, formatSeconds, assumptionNotes, fieldTotalLine, TYRE_FACTOR_SUMMARY,
  DD_WC2_DISCLAIMER, PLACEHOLDER_LINE, UNAVAILABLE, HOW_CALCULATED,
} from './transform'
import { buildDirtyAirCostSql, DIRTY_AIR_LAPS_SQL, TYRE_LABEL_SQL } from './queries'
import type { DirtyAirCostRow } from './queries'

const mkRow = (
  driver_id: string,
  total: number | null,
  avg: number | null,
  modelled = 40,
  unavailable = 0,
  reasons: string | null = null,
): DirtyAirCostRow => ({
  driver_id,
  total_placeholder_cost_s: total,
  avg_placeholder_cost_s: avg,
  laps_modelled: modelled,
  laps_unavailable: unavailable,
  total_laps: modelled + unavailable,
  unavailable_reasons: reasons,
  corner_class: 'medium',
  race_loss_s_per_lap_within_1s: 0.27,
  avg_lap_loss_s: 0.27,
  tyre_factors: 'HARD x0.96, MEDIUM x1.00',
  laps_tyre_neutral: 0,
  constructor_id: 'Ferrari',
  constructor_factor: 1,
  constructor_factor_source: 'neutral_default',
  constructor_basis: 'neutral default, no public evidence used',
  laps_lap_loss_bounded: 0,
  factor_flags: null,
  era: '2024_25_mature_ground_effect',
  era_factor: 0.8,
  loss_source: 'race_structure',
  loss_bounded: false,
  loss_basis: 'Assumed rule: 7.75 fast-corner equivalents',
  value_kind: 'placeholder',
  disclaimer: DD_WC2_DISCLAIMER,
  disclaimer_placeholder: 'x',
})

describe('transform', () => {
  it('returns empty for no rows', () => {
    expect(transform([])).toEqual([])
  })

  it('ranks by total descending regardless of input order', () => {
    const rows = [mkRow('ALO', 2.0, 0.05), mkRow('LEC', 8.0, 0.16), mkRow('HAM', 5.0, 0.10)]
    expect(transform(rows).map(r => r.driver_id)).toEqual(['LEC', 'HAM', 'ALO'])
    expect(transform(rows)[0].rank).toBe(1)
  })

  it('labels every value modelled, and a driver with no value unavailable, sorted last', () => {
    const rows = [mkRow('SAR', null, null, 0, 52, 'no gap measured on this lap'), mkRow('VER', 1.0, 0.02)]
    const out = transform(rows)
    expect(out.map(r => r.driver_id)).toEqual(['VER', 'SAR'])
    expect(out[0].value_label).toBe('modelled')
    expect(out[1].value_label).toBe('unavailable')
    expect(out[1].total_placeholder_cost_s).toBeNull()
  })

  it('does not mutate input', () => {
    const rows = [mkRow('VER', 1.0, 0.02), mkRow('NOR', 3.0, 0.06)]
    const original = rows.map(r => ({ ...r }))
    transform(rows)
    expect(rows).toEqual(original)
  })
})

describe('unavailable is never 0', () => {
  it('formats a missing value as an em dash', () => {
    expect(formatSeconds(null)).toBe(UNAVAILABLE)
    expect(formatSeconds(undefined)).toBe(UNAVAILABLE)
    expect(formatSeconds(0)).toBe('0.00s')
  })

  it('writes the em dash to the CSV, with the label and the disclaimer', () => {
    const csv = toCsvRows([mkRow('SAR', null, null, 0, 52, 'neutralised lap (safety car, VSC or red flag)')])
    expect(csv[0].total_placeholder_cost_s).toBe(UNAVAILABLE)
    expect(csv[0].value_label).toBe('unavailable')
    expect(csv[0].value_kind).toBe('placeholder')
    expect(csv[0].disclaimer).toBe(DD_WC2_DISCLAIMER)
  })
})

describe('totals print the modelled share', () => {
  it('sums only drivers with a value and reports 100% modelled', () => {
    const t = totals([mkRow('VER', 1.5, 0.03, 50, 2), mkRow('SAR', null, null, 0, 52)])
    expect(t.total_s).toBeCloseTo(1.5)
    expect(t.modelled_share).toBe(1)
    expect(t.laps_modelled).toBe(50)
    expect(t.laps_unavailable).toBe(54)
  })

  it('has no total and no share when nothing has a value', () => {
    const t = totals([mkRow('SAR', null, null, 0, 52)])
    expect(t.total_s).toBeNull()
    expect(t.modelled_share).toBeNull()
  })
})

describe('query', () => {
  it('reads the placeholder table, not the label tax', () => {
    const sql = buildDirtyAirCostSql(2023)
    expect(sql).toContain('int_lap_wake_placeholder_cost_2023')
    expect(sql).not.toContain('dirty_air_tax')
  })
})

describe('disclaimer', () => {
  it('is the DD-WC2 text word for word', () => {
    expect(DD_WC2_DISCLAIMER).toBe(
      "Modelled: an assumed typical loss for this circuit, season, tyre and car, applied to the measured time spent close behind another car. Not calibrated on this driver's own stints.",
    )
    expect(DD_WC2_DISCLAIMER).not.toContain('Normalised from other compounds')
  })
})

describe('per-race assumed loss (WC-12)', () => {
  it('carries the race value and its basis into the totals', () => {
    const t = totals([mkRow('HAM', 5.0, 0.1)])
    expect(t.race_loss_s_per_lap_within_1s).toBe(0.27)
    expect(t.loss_basis).toContain('fast-corner equivalents')
    expect(t.is_fallback).toBe(false)
  })

  it('flags a fallback race', () => {
    const row = { ...mkRow('HAM', 5.0, 0.1), loss_source: 'class_fallback', loss_basis: 'Fallback: no corner structure' }
    expect(totals([row]).is_fallback).toBe(true)
  })

  it('selects the basis columns', () => {
    const sql = buildDirtyAirCostSql(2024)
    for (const c of ['loss_basis', 'loss_source', 'era_factor']) expect(sql).toContain(c)
  })

  it('keeps the placeholder line word for word', () => {
    expect(PLACEHOLDER_LINE).toBe(
      'Placeholder = an interim value set by a fixed rule, not a measurement of this lap.',
    )
  })
})

describe('tyre and car factors (WC-13)', () => {
  it('says when the car factor is the neutral default', () => {
    const out = transform([mkRow('LEC', 5.0, 0.1)])
    expect(out[0].car_factor).toBe('1.00 (neutral default, no public evidence used)')
    expect(totals([mkRow('LEC', 5.0, 0.1)]).car_factors_all_neutral).toBe(true)
  })

  it('shows a cited source for a non-neutral car factor', () => {
    const row = { ...mkRow('LEC', 5.0, 0.1), constructor_factor: 1.03, constructor_factor_source: 'public_concept', constructor_basis: 'team statement X' }
    expect(transform([row])[0].car_factor).toBe('1.03 (public concept: team statement X)')
    expect(totals([row]).car_factors_all_neutral).toBe(false)
  })

  it('names a missing-key fallback as a fallback, not a neutral default', () => {
    const row = { ...mkRow('LEC', 5.0, 0.1), constructor_factor_source: 'neutral_missing_constructor', constructor_basis: 'no row' }
    expect(transform([row])[0].car_factor).toContain('neutral fallback')
  })

  it('carries the tyre factors and flags, and shows — when a driver has none', () => {
    const flagged = { ...mkRow('SAR', 1.0, 0.02), factor_flags: 'no compound recorded on this lap: neutral tyre factor used' }
    const none = { ...mkRow('ALB', null, null, 0, 40), tyre_factors: null }
    const out = transform([flagged, none])
    expect(out[0].tyre_factors).toBe('HARD x0.96, MEDIUM x1.00')
    expect(out[0].factor_flags).toContain('neutral tyre factor')
    expect(out[1].tyre_factors).toBe(UNAVAILABLE)
  })

  it('selects the factor columns', () => {
    const sql = buildDirtyAirCostSql(2023)
    for (const c of ['compound_factor', 'constructor_factor', 'constructor_basis', 'factor_flag', 'lap_loss_bounded', 'race_loss_s_per_lap_within_1s', 'tyre_c_number'])
      expect(sql).toContain(c)
  })

  it('labels a tyre with its C-number when it has one (WC-16)', () => {
    expect(buildDirtyAirCostSql(2025)).toContain(TYRE_LABEL_SQL)
    expect(TYRE_LABEL_SQL).toContain("COALESCE(' (' || tyre_c_number || ')', '')")
    expect(DIRTY_AIR_LAPS_SQL(2025)).toContain('tyre_c_number')
  })

  it('describes the C-number tyre rule and the 2018 fallback (WC-16)', () => {
    for (const s of ['C-number', 'x1.10', 'x1.17', 'x0.96', 'x0.93', 'medium x1.00', '2018', 'neutral'])
      expect(TYRE_FACTOR_SUMMARY).toContain(s)
    // DD-WC29: the medium shift was dropped; the page must not describe one
    expect(TYRE_FACTOR_SUMMARY).not.toContain('x0.97')
    expect(TYRE_FACTOR_SUMMARY).not.toContain('x1.06')
  })
})

describe('assumption notes and field total line (WC-15)', () => {
  const rows = [mkRow('A', 10, 0.25), mkRow('B', null, null, 0, 1, 'neutralised lap (safety car, VSC or red flag)')]
  it('field total line keeps total, modelled share, placeholder tag and lap counts', () => {
    const line = fieldTotalLine(totals(rows))
    expect(line).toContain('Field total 10.0s')
    expect(line).toContain('modelled share 100% (placeholder)')
    expect(line).toContain('40 laps with a value, 1 unavailable')
  })
  it('field total line shows the dash, not 0, when nothing has a value', () => {
    const line = fieldTotalLine(totals([mkRow('B', null, null, 0, 1, 'x')]))
    expect(line).toContain(`Field total ${UNAVAILABLE}`)
    expect(line).toContain(`modelled share ${UNAVAILABLE}`)
  })
  it('summary is one line with the assumed race loss; the detail holds rule, tyre legend and car note', () => {
    const n = assumptionNotes(totals(rows))
    expect(n.summary).toBe('Assumed 0.27s per full lap within 1 s for this race (placeholder), before tyre and car factors.')
    expect(n.rule).toBe('Assumed rule: 7.75 fast-corner equivalents')
    expect(n.tyre).toContain(TYRE_FACTOR_SUMMARY)
    expect(n.car).toContain('neutral default 1.00 for every team')
  })
  it('marks a fallback race', () => {
    const n = assumptionNotes(totals([{ ...mkRow('A', 1, 0.1), loss_source: 'class_fallback' }]))
    expect(n.rule?.startsWith('FALLBACK · ')).toBe(true)
  })
  it('a driver whose measured laps all have zero exposure keeps a modelled 0.00s, not a dash', () => {
    const [r] = transform([mkRow('Z', 0, 0, 3, 0)])
    expect(r.value_label).toBe('modelled')
    expect(formatSeconds(r.total_placeholder_cost_s)).toBe('0.00s')
  })
})

/** Minimal CSV reader for the factor seeds: first columns only, quoted basis text ignored. */
const seedRows = (name: string): string[][] =>
  readFileSync(join(__dirname, '../../../../transform/seeds', name), 'utf8')
    .trim().split('\n').slice(1).map(l => l.split(','))

describe('tyre factor text matches the seeds (review R1)', () => {
  const steps = new Map(seedRows('wake_placeholder_c_number_factor.csv')
    .filter(r => r[0] === 'step').map(r => [Number(r[1]), r[2]]))
  const classes = new Map(seedRows('wake_placeholder_compound_factor.csv').map(r => [r[0], r[1]]))

  it('the C-number steps in the summary are the seed values (2019+)', () => {
    expect(TYRE_FACTOR_SUMMARY).toContain(`one step softer x${steps.get(1)}`)
    expect(TYRE_FACTOR_SUMMARY).toContain(`two or more x${steps.get(2)}`)
    expect(TYRE_FACTOR_SUMMARY).toContain(`one step harder x${steps.get(-1)}`)
    expect(TYRE_FACTOR_SUMMARY).toMatch(new RegExp(`harder x${steps.get(-1)}, two or more x${steps.get(-2)}`))
    expect(TYRE_FACTOR_SUMMARY).toContain(`medium x${steps.get(0)}`)
    expect(steps.size).toBe(5)
  })

  it('the 2018 relative-class values in the summary are the seed values', () => {
    expect(TYRE_FACTOR_SUMMARY).toContain(
      `2018 races: softest x${classes.get('SOFT')}, middle x${classes.get('MEDIUM')}, hardest x${classes.get('HARD')}`)
    expect(TYRE_FACTOR_SUMMARY).toContain(`intermediate and wet x${classes.get('INTERMEDIATE')}`)
    expect(classes.get('WET')).toBe(classes.get('INTERMEDIATE'))
  })

  it("the How It's Calculated badge carries the same summary, not the pre-WC-16 text", () => {
    expect(HOW_CALCULATED).toContain(TYRE_FACTOR_SUMMARY)
    expect(HOW_CALCULATED).not.toContain('softest dry compound of the race')
    // the badge states no tyre factor other than the summary's
    const outside = HOW_CALCULATED.replace(TYRE_FACTOR_SUMMARY, '')
    expect(outside).not.toMatch(/x?(0\.9\d|1\.1\d)\b/)
  })
})

describe('bounded-lap count and factor flags use laps with a value (review R2)', () => {
  const sql = buildDirtyAirCostSql(2024).replace(/\s+/g, ' ')
  it('counts bounded laps only when the lap has a value', () => {
    expect(sql).toContain('COUNT(*) FILTER (WHERE wake_cost_placeholder_s IS NOT NULL AND lap_loss_bounded) AS laps_lap_loss_bounded')
  })
  it('aggregates factor flags only over laps with a value', () => {
    expect(sql).toContain("STRING_AGG(DISTINCT factor_flag, '; ') FILTER (WHERE wake_cost_placeholder_s IS NOT NULL) AS factor_flags")
  })
})
