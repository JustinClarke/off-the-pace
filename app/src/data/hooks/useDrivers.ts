// Fetches dim_drivers from DuckDB; cached indefinitely (driver roster does not change mid-session).
import { useQuery as useTanstackQuery } from '@tanstack/react-query'
import { rawQuery } from './useQuery'

export interface Driver {
  driverId: number
  code: string
  firstName: string
  lastName: string
  nationality: string
  permanentNumber: number | null
}

export function useDrivers() {
  return useTanstackQuery<Driver[], Error>({
    queryKey: ['drivers'],
    queryFn: () => rawQuery<Driver>(`SELECT * FROM dim_drivers ORDER BY last_name`),
    staleTime: Infinity,
  })
}
