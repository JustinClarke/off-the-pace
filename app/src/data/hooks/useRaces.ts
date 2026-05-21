// Fetches dim_events for a given season from DuckDB; cached for the session lifetime.
import { useQuery as useTanstackQuery } from '@tanstack/react-query'
import { rawQuery } from './useQuery'

export interface Race {
  raceId: number
  season: number
  round: number
  name: string
  circuitId: number
  circuitName: string
  date: string
}

export function useRaces(season: number) {
  return useTanstackQuery<Race[], Error>({
    queryKey: ['races', season],
    queryFn: () => rawQuery<Race>(
      `SELECT * FROM dim_events WHERE season = ? ORDER BY round`,
      [season]
    ),
    staleTime: Infinity,
    enabled: season > 0,
  })
}
