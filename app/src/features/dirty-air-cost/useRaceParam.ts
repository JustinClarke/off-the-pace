import { useEffect, useRef } from 'react'
import { useSearchParams } from 'react-router-dom'
import { useFilters } from '../../state/FilterContext'

/** Season of a race id like "2025_5", or null if the id is not season_round. */
export function raceSeason(raceId: string): number | null {
  const m = /^(\d{4})_\d+$/.exec(raceId)
  return m ? Number(m[1]) : null
}

/**
 * Reads the `race` search param and keeps it consistent with the season:
 * - a deep-linked race from another season switches the season to the race's season;
 * - a later season change clears a race that does not belong to the new season.
 * The first run never clears the race.
 */
export function useRaceParam(): [string, ReturnType<typeof useSearchParams>[1]] {
  const { season, setSeason } = useFilters()
  const [searchParams, setSearchParams] = useSearchParams()
  const raceId = searchParams.get('race') ?? ''
  const prevSeason = useRef(season)

  useEffect(() => {
    const rs = raceSeason(raceId)
    if (rs !== null && rs !== season && prevSeason.current === season) {
      setSeason(rs)
      return
    }
    if (prevSeason.current !== season) {
      prevSeason.current = season
      if (rs !== season) setSearchParams(p => { p.delete('race'); return p }, { replace: true })
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [season, raceId])

  return [raceId, setSearchParams]
}
