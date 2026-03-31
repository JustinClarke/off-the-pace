import { describe, it, expect } from 'vitest'
import { transform } from './transform'
import type { DegradationProfileRow } from './queries'

const mkRow = (
  compound: string,
  lap_in_stint: number,
  avg_pace_loss_s: number,
  std_pace_loss_s = 0,
  cliff_onset_laps = 0,
): DegradationProfileRow => ({
  compound,
  lap_in_stint,
  avg_pace_loss_s,
  std_pace_loss_s,
  cliff_onset_laps,
  lap_count: 5,
})

describe('transform', () => {
  it('returns empty for no rows', () => {
    expect(transform([])).toEqual([])
  })

  it('orders SOFT / MEDIUM / HARD first', () => {
    const rows = [mkRow('HARD', 1, 0.01), mkRow('SOFT', 1, 0.03), mkRow('MEDIUM', 1, 0.02)]
    const result = transform(rows)
    expect(result.map(p => p.compound)).toEqual(['SOFT', 'MEDIUM', 'HARD'])
  })

  it('sorts laps within compound ascending', () => {
    const rows = [mkRow('SOFT', 3, 0.09), mkRow('SOFT', 1, 0.03), mkRow('SOFT', 2, 0.06)]
    const [profile] = transform(rows)
    expect(profile.points.map(p => p.x)).toEqual([1, 2, 3])
  })

  it('maps CIPoint with lo/hi from std', () => {
    const rows = [mkRow('SOFT', 5, 1.0, 0.2)]
    const [profile] = transform(rows)
    expect(profile.points[0]).toMatchObject({ x: 5, y: 1.0, lo: 0.8, hi: 1.2 })
  })

  it('clips lo to zero when std > avg', () => {
    const rows = [mkRow('SOFT', 1, 0.05, 0.3)]
    const [profile] = transform(rows)
    expect(profile.points[0].lo).toBe(0)
  })

  it('extracts cliff onset when > 0', () => {
    const rows = [mkRow('SOFT', 1, 0.01, 0, 20), mkRow('SOFT', 2, 0.02, 0, 20)]
    const [profile] = transform(rows)
    expect(profile.cliffOnset).toBe(20)
  })

  it('sets cliff onset to null when 0', () => {
    const rows = [mkRow('SOFT', 1, 0.01, 0, 0)]
    const [profile] = transform(rows)
    expect(profile.cliffOnset).toBeNull()
  })

  it('handles unknown compounds after known', () => {
    const rows = [mkRow('INTER', 1, 0.1), mkRow('SOFT', 1, 0.03)]
    const result = transform(rows)
    expect(result[0].compound).toBe('SOFT')
    expect(result[1].compound).toBe('INTER')
  })
})
