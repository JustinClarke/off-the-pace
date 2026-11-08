import { describe, it, expect } from 'vitest'
import { transform, seasonMeanSe, t975, toCsvRows } from './transform'
import type { ConstructorPaceRow } from './queries'

const makeRow = (overrides: Partial<ConstructorPaceRow> = {}): ConstructorPaceRow => ({
  constructor_id: 'Ferrari',
  constructor_structural_pace_s: -0.83,
  constructor_structural_pace_se_s: 0.10,
  constructor_structural_pace_ci_low_s: -1.03,
  constructor_structural_pace_ci_high_s: -0.63,
  panel_observations_n: 101,
  races_n: 1,
  ...overrides,
})

describe('transform', () => {
  it('assigns rank starting at 1', () => {
    const entries = transform([makeRow(), makeRow({ constructor_id: 'McLaren' })])
    expect(entries[0].rank).toBe(1)
    expect(entries[1].rank).toBe(2)
  })

  it('maps constructor_id to constructor field', () => {
    const entries = transform([makeRow({ constructor_id: 'Red Bull Racing' })])
    expect(entries[0].constructor).toBe('Red Bull Racing')
  })

  it('carries pace and CI through', () => {
    const entries = transform([makeRow()])
    expect(entries[0].pace_s).toBeCloseTo(-0.83)
    expect(entries[0].ci_low_s).toBeCloseTo(-1.03)
    expect(entries[0].ci_high_s).toBeCloseTo(-0.63)
  })

  it('returns empty for empty input', () => {
    expect(transform([])).toEqual([])
  })
})

const MERC_P = [
  -1.3073817939366945, -1.3838524920034068, -1.8283883999704025, -1.2014821428016496,
  -0.75285425709014, -1.6119718148277031, -0.48419564103369606, -1.5258938300921288,
  -1.0887010889196085, -1.5405682331723884, -1.75884005959594, -0.7783600296425797,
  -1.7000429962065793, -1.4689076634226894, -0.8480785890966649, -1.093666797036144,
]
const MERC_SE = [
  0.0583477657020264, 0.08803080503646468, 0.1315338277940761, 0.07793856801034359,
  0.0923166610281464, 0.1577449104590612, 0.07179757375790612, 0.08409214091770775,
  0.03832899496597576, 0.08823792887056313, 0.20150981047704578, 0.10434208569705576,
  0.08587930446177859, 0.10746267541219351, 0.08549422189553199, 0.10870198200775681,
]

describe('t975 (AP-07)', () => {
  it('matches scipy.stats.t.ppf(0.975, df) to 4 dp at checked points', () => {
    expect(t975(2)).toBe(4.3027)
    expect(t975(8)).toBe(2.306)
    expect(t975(15)).toBe(2.1314)
    expect(t975(20)).toBe(2.086)
    expect(t975(22)).toBe(2.0739)
    expect(t975(60)).toBe(2.0003)
  })
  it('falls back to 1.96 beyond df 60 and has no value below df 2', () => {
    expect(t975(61)).toBe(1.96)
    expect(t975(1)).toBeNull()
  })
})

describe('seasonMeanSe (AP-07)', () => {
  it('uses the spread when VAR_SAMP > mean(se^2)', () => {
    const p = [0, 1, 2, 3] // var_samp = 5/3
    const se = [0.1, 0.1, 0.1, 0.1]
    expect(seasonMeanSe(p, se)).toBeCloseTo(Math.sqrt(5 / 3 / 4), 12)
  })
  it('uses the estimation error when VAR_SAMP < mean(se^2)', () => {
    const p = [0, 0.01, 0.02] // var_samp = 1e-4
    const se = [0.3, 0.4, 0.5] // mean se^2 = (0.09+0.16+0.25)/3
    expect(seasonMeanSe(p, se)).toBeCloseTo(Math.sqrt(((0.09 + 0.16 + 0.25) / 3) / 3), 12)
  })
  it('gives a finite result when se = 0', () => {
    expect(seasonMeanSe([0, 1, 2], [0, 0, 0])).toBeCloseTo(Math.sqrt(1 / 3), 12)
  })
  it('k = 1 and k = 2 give null; null pairs are dropped before counting', () => {
    expect(seasonMeanSe([1], [0.1])).toBeNull()
    expect(seasonMeanSe([1, 2], [0.1, 0.1])).toBeNull()
    expect(seasonMeanSe([1, null, 2, 3], [0.1, 0.1, null, 0.1])).toBeNull()
    expect(seasonMeanSe([1, null, 2, 3], [0.1, 0.1, 0.1, 0.1])).not.toBeNull()
  })
})

describe('season transform (AP-07)', () => {
  it('Mercedes 2020 worked case: SE and t(15) CI at 12 dp', () => {
    const k = MERC_P.length
    const mean = MERC_P.reduce((a, b) => a + b, 0) / k
    const se = seasonMeanSe(MERC_P, MERC_SE)!
    const [e] = transform([makeRow({
      constructor_id: 'Mercedes',
      constructor_structural_pace_s: mean,
      constructor_structural_pace_se_s: se,
      constructor_structural_pace_ci_low_s: null,
      constructor_structural_pace_ci_high_s: null,
      races_n: k,
    })], 'season')
    expect(mean).toBeCloseTo(-1.273324114303026, 12)
    expect(se).toBeCloseTo(0.10038245862558223, 12)
    expect(e.ci_low_s).toBeCloseTo(-1.4873, 4)
    expect(e.ci_high_s).toBeCloseTo(-1.0594, 4)
    expect(e.ci_low_s).toBeCloseTo(mean - 2.1314 * se, 12)
    expect(e.ci_high_s).toBeCloseTo(mean + 2.1314 * se, 12)
    expect(e.season).toBe(true)
  })

  it('k = 2 season row has no SE and no CI; CSV prints null', () => {
    const [e] = transform([makeRow({
      constructor_structural_pace_se_s: null,
      constructor_structural_pace_ci_low_s: null,
      constructor_structural_pace_ci_high_s: null,
      races_n: 2,
    })], 'season')
    expect(e.se_s).toBeNull()
    expect(e.ci_low_s).toBeNull()
    expect(e.ci_high_s).toBeNull()
    const [csv] = toCsvRows([e], 'race')
    expect(csv.se_s).toBeNull()
    expect(csv.ci_low_s).toBeNull()
    expect(String(csv.interval_method)).toMatch(/^season/)
  })

  it('race rows keep the stored CI and the race interval method', () => {
    const [e] = transform([makeRow()], 'race')
    expect(e.ci_low_s).toBeCloseTo(-1.03)
    expect(toCsvRows([e], 'race')[0].interval_method).toBe('race: +/-1.96*se')
  })
})
