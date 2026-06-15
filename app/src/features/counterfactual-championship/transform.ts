import type { ChampionshipRow } from './queries'

export interface ChampionshipEntry {
  driver: string
  ghostPoints: number
  actualPoints: number
  delta: number
  racesCounted: number
  avgConfidence: number
  ghostRank: number
  actualRank: number
}

export function transform(rows: ChampionshipRow[]): {
  ghostStandings: ChampionshipEntry[]
  actualStandings: ChampionshipEntry[]
  coverageWarning: boolean
} {
  const ghostStandings = rows
    .map((r, i) => ({
      driver: r.ego_driver_id,
      ghostPoints: r.ghost_points,
      actualPoints: r.actual_points,
      delta: r.ghost_points - r.actual_points,
      racesCounted: r.races_counted,
      avgConfidence: r.avg_confidence,
      ghostRank: i + 1,
      actualRank: 0,
    }))

  const actualStandings = [...ghostStandings].sort((a, b) => b.actualPoints - a.actualPoints)
  actualStandings.forEach((e, i) => { e.actualRank = i + 1 })
  ghostStandings.forEach(e => {
    const found = actualStandings.find(a => a.driver === e.driver)
    if (found) e.actualRank = found.actualRank
  })

  const maxRaces = Math.max(...rows.map(r => r.races_counted))
  return {
    ghostStandings,
    actualStandings,
    coverageWarning: maxRaces < 15,
  }
}

export function toCsvRows(entries: ChampionshipEntry[]): Record<string, unknown>[] {
  return entries.map(e => ({
    driver: e.driver,
    ghost_rank: e.ghostRank,
    actual_rank: e.actualRank,
    ghost_points: e.ghostPoints,
    actual_points: e.actualPoints,
    points_delta: e.delta,
    races_counted: e.racesCounted,
    avg_confidence: e.avgConfidence.toFixed(3),
  }))
}
