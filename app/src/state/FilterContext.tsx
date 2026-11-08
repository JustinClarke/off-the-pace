// Global filter context season, driver, and race selections persisted in URL search params; consumed by all data routes.
import { createContext, useContext, ReactNode } from 'react'
import { useSearchParams } from 'react-router-dom'
import { LATEST_SEASON } from '../data/constants'
import { intParam } from './urlParams'

interface FilterState {
  season: number
  raceId: number | null
  driverId: number | null
  constructorId: number | null
}

interface FilterContextValue extends FilterState {
  setSeason: (v: number) => void
  setRaceId: (v: number | null) => void
  setDriverId: (v: number | null) => void
  setConstructorId: (v: number | null) => void
}

const FilterContext = createContext<FilterContextValue | null>(null)

export function FilterProvider({ children }: { children: ReactNode }) {
  const [searchParams, setSearchParams] = useSearchParams()

  const season = intParam(searchParams.get('season')) ?? LATEST_SEASON
  // Pages also use these keys for string ids (race=2024_8, driver=LEC, constructor=ferrari).
  // Those are not this context's integers: read them as null, never NaN (AX-03 finding 2).
  const raceId = intParam(searchParams.get('race'))
  const driverId = intParam(searchParams.get('driver'))
  const constructorId = intParam(searchParams.get('constructor'))

  const setSeason = (v: number) =>
    setSearchParams(p => { p.set('season', String(v)); return p }, { replace: true })

  const setRaceId = (v: number | null) =>
    setSearchParams(p => { v !== null ? p.set('race', String(v)) : p.delete('race'); return p }, { replace: true })

  const setDriverId = (v: number | null) =>
    setSearchParams(p => { v !== null ? p.set('driver', String(v)) : p.delete('driver'); return p }, { replace: true })

  const setConstructorId = (v: number | null) =>
    setSearchParams(p => { v !== null ? p.set('constructor', String(v)) : p.delete('constructor'); return p }, { replace: true })

  return (
    <FilterContext.Provider value={{ season, raceId, driverId, constructorId, setSeason, setRaceId, setDriverId, setConstructorId }}>
      {children}
    </FilterContext.Provider>
  )
}

export function useFilters(): FilterContextValue {
  const ctx = useContext(FilterContext)
  if (!ctx) throw new Error('useFilters must be used inside FilterProvider')
  return ctx
}
