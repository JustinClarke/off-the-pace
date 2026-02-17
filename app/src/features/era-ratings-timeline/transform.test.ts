import { describe, it, expect } from 'vitest'
import { transform, topDriversByConfidence } from './transform'
import type { EraRatingRow } from './queries'

const makeRow = (overrides: Partial<EraRatingRow>): EraRatingRow => ({
  driver_id: 'VER',
  season: 2023,
  era_adjusted_rating: -0.3,
  era_adjusted_rating_ci_low_s: -0.6,
  era_adjusted_rating_ci_high_s: 0.0,
  rating_confidence: 0.8,
  n_races: 20,
  bridge_driver_anchor_flag: false,
  low_anchor_sample_flag: false,
  n_bridge_drivers: 20,
  ...overrides,
})

describe('transform', () => {
  it('returns empty result for empty input', () => {
    const result = transform([])
    expect(result.series).toHaveLength(0)
    expect(result.seasons).toHaveLength(0)
  })

  it('groups rows by driver_id into series', () => {
    const rows = [
      makeRow({ driver_id: 'VER', season: 2022 }),
      makeRow({ driver_id: 'VER', season: 2023 }),
      makeRow({ driver_id: 'HAM', season: 2022 }),
    ]
    const result = transform(rows)
    expect(result.series).toHaveLength(2)
    const ver = result.series.find(s => s.driver_id === 'VER')!
    expect(ver.points).toHaveLength(2)
  })

  it('sorts points within a series by season ascending', () => {
    const rows = [
      makeRow({ driver_id: 'VER', season: 2024 }),
      makeRow({ driver_id: 'VER', season: 2019 }),
      makeRow({ driver_id: 'VER', season: 2022 }),
    ]
    const result = transform(rows)
    const ver = result.series.find(s => s.driver_id === 'VER')!
    expect(ver.points.map(p => p.x)).toEqual([2019, 2022, 2024])
  })

  it('marks bridge driver correctly', () => {
    const rows = [
      makeRow({ driver_id: 'HAM', bridge_driver_anchor_flag: true }),
      makeRow({ driver_id: 'VER', bridge_driver_anchor_flag: false }),
    ]
    const result = transform(rows)
    expect(result.series.find(s => s.driver_id === 'HAM')!.isBridgeDriver).toBe(true)
    expect(result.series.find(s => s.driver_id === 'VER')!.isBridgeDriver).toBe(false)
  })

  it('sorts series so fastest (most-negative mean) comes first', () => {
    const rows = [
      makeRow({ driver_id: 'SLOW', era_adjusted_rating: 0.5 }),
      makeRow({ driver_id: 'FAST', era_adjusted_rating: -0.8 }),
    ]
    const result = transform(rows)
    expect(result.series[0].driver_id).toBe('FAST')
    expect(result.series[1].driver_id).toBe('SLOW')
  })

  it('collects all unique seasons sorted ascending', () => {
    const rows = [
      makeRow({ driver_id: 'A', season: 2022 }),
      makeRow({ driver_id: 'B', season: 2019 }),
      makeRow({ driver_id: 'A', season: 2024 }),
    ]
    expect(transform(rows).seasons).toEqual([2019, 2022, 2024])
  })

  it('maps CI columns to CIPoint lo/hi', () => {
    const rows = [makeRow({ era_adjusted_rating_ci_low_s: -1.5, era_adjusted_rating_ci_high_s: 0.5 })]
    const result = transform(rows)
    const p = result.series[0].points[0]
    expect(p.lo).toBe(-1.5)
    expect(p.hi).toBe(0.5)
  })

  it('propagates low_anchor_sample_flag', () => {
    const rows = [makeRow({ low_anchor_sample_flag: true })]
    expect(transform(rows).lowAnchorSample).toBe(true)
  })

  it('reports the dataset-wide season range', () => {
    const rows = [
      makeRow({ driver_id: 'A', season: 2018 }),
      makeRow({ driver_id: 'B', season: 2024 }),
    ]
    expect(transform(rows).seasonRange).toEqual([2018, 2024])
  })

  it('records each driver first/last season and active seasons', () => {
    const rows = [
      makeRow({ driver_id: 'VER', season: 2019 }),
      makeRow({ driver_id: 'VER', season: 2022 }),
      makeRow({ driver_id: 'VER', season: 2024 }),
    ]
    const ver = transform(rows).series.find(s => s.driver_id === 'VER')!
    expect(ver.firstSeason).toBe(2019)
    expect(ver.lastSeason).toBe(2024)
    expect(ver.activeSeasons).toEqual([2019, 2022, 2024])
  })
})

describe('cohort classification', () => {
  // Global range is 2018-2024 in each case below.
  const frame = (extra: EraRatingRow[]): EraRatingRow[] => [
    makeRow({ driver_id: 'ANCHOR_LO', season: 2018 }),
    makeRow({ driver_id: 'ANCHOR_HI', season: 2024 }),
    ...extra,
  ]

  it('marks a bridge driver as bridge', () => {
    const rows = frame([
      makeRow({ driver_id: 'HAM', season: 2020, bridge_driver_anchor_flag: true }),
      makeRow({ driver_id: 'HAM', season: 2023, bridge_driver_anchor_flag: true }),
    ])
    expect(transform(rows).series.find(s => s.driver_id === 'HAM')!.cohort).toBe('bridge')
  })

  it('marks a non-anchor present-every-season driver as full-span', () => {
    const rows = frame([
      makeRow({ driver_id: 'ZHO', season: 2018 }),
      makeRow({ driver_id: 'ZHO', season: 2024 }),
    ])
    expect(transform(rows).series.find(s => s.driver_id === 'ZHO')!.cohort).toBe('full-span')
  })

  it('marks a late debut as joined', () => {
    const rows = frame([
      makeRow({ driver_id: 'PIA', season: 2023 }),
      makeRow({ driver_id: 'PIA', season: 2024 }),
    ])
    expect(transform(rows).series.find(s => s.driver_id === 'PIA')!.cohort).toBe('joined')
  })

  it('marks an early exit as left', () => {
    const rows = frame([
      makeRow({ driver_id: 'RAI', season: 2018 }),
      makeRow({ driver_id: 'RAI', season: 2021 }),
    ])
    expect(transform(rows).series.find(s => s.driver_id === 'RAI')!.cohort).toBe('left')
  })

  it('marks a single-season driver as cameo', () => {
    const rows = frame([makeRow({ driver_id: 'AIT', season: 2020 })])
    expect(transform(rows).series.find(s => s.driver_id === 'AIT')!.cohort).toBe('cameo')
  })
})

describe('topDriversByConfidence', () => {
  const stub = (driver_id: string, latestConfidence: number) => ({
    driver_id,
    points: [],
    isBridgeDriver: false,
    latestConfidence,
    firstSeason: 2018,
    lastSeason: 2024,
    activeSeasons: [2018],
    meanRating: 0,
    cohort: 'full-span' as const,
  })

  it('returns top n drivers by latestConfidence descending', () => {
    const series = [stub('A', 0.5), stub('B', 0.9), stub('C', 0.7)]
    expect(topDriversByConfidence(series, 2)).toEqual(['B', 'C'])
  })
})
