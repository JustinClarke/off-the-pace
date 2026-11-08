// Driver roster from the published assistant_entities table (AX-02): code, display name, seasons.
// Replaces the old `SELECT * FROM dim_drivers ORDER BY last_name`, which queried a column dim_drivers
// does not have (it carries only driver_id, driver_number, debut_year, career_races_in_dataset).
import { useQuery as useTanstackQuery } from '@tanstack/react-query'
import { listValues } from '../../assistant/listValues'

export interface Driver {
  code: string
  display: string
  seasons: string
}

export function useDrivers() {
  return useTanstackQuery<Driver[], Error>({
    queryKey: ['drivers'],
    queryFn: async () => {
      const r = await listValues({ domain: 'driver', limit: 20 })
      return r.status === 'ok' ? r.rows.map(({ code, display, seasons }) => ({ code, display, seasons })) : []
    },
    staleTime: Infinity,
  })
}
