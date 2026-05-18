// Global filter context season, driver, and race selections persisted in URL search params; consumed by all data routes.
import { createContext, useContext, ReactNode } from 'react'
import { useSearchParams } from 'react-router-dom'
import { LATEST_SEASON } from '../data/constants'

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

  const season = Number(searchParams.get('season') ?? LATEST_SEASON)
  const raceId = searchParams.get('race') ? Number(searchParams.get('race')) : null
  const driverId = searchParams.get('driver') ? Number(searchParams.get('driver')) : null
  const constructorId = searchParams.get('constructor') ? Number(searchParams.get('constructor')) : null

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
