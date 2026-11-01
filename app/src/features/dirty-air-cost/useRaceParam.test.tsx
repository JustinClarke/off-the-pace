import { describe, it, expect } from 'vitest'
import { renderHook, act } from '@testing-library/react'
import { MemoryRouter, useSearchParams } from 'react-router-dom'
import type { ReactNode } from 'react'
import { FilterProvider, useFilters } from '../../state/FilterContext'
import { useRaceParam, raceSeason } from './useRaceParam'

const setup = (url: string) => {
  const wrapper = ({ children }: { children: ReactNode }) => (
    <MemoryRouter initialEntries={[url]}><FilterProvider>{children}</FilterProvider></MemoryRouter>
  )
  return renderHook(() => {
    const [raceId] = useRaceParam()
    const { season, setSeason } = useFilters()
    const [sp] = useSearchParams()
    return { raceId, season, setSeason, sp }
  }, { wrapper })
}

describe('useRaceParam', () => {
  it('parses the season from a race id', () => {
    expect(raceSeason('2025_5')).toBe(2025)
    expect(raceSeason('')).toBeNull()
    expect(raceSeason('abc')).toBeNull()
  })

  it('first load keeps a deep-linked race in the selected season', () => {
    const { result } = setup('/aero/dirty-air?season=2025&race=2025_5')
    expect(result.current.raceId).toBe('2025_5')
    expect(result.current.season).toBe(2025)
  })

  it('a deep-linked race from another season sets the season and stays selected', () => {
    const { result } = setup('/aero/dirty-air?season=2023&race=2025_5')
    expect(result.current.season).toBe(2025)
    expect(result.current.raceId).toBe('2025_5')
  })

  it('changing the season afterwards clears the race', () => {
    const { result } = setup('/aero/dirty-air?season=2025&race=2025_5')
    act(() => result.current.setSeason(2024))
    expect(result.current.season).toBe(2024)
    expect(result.current.raceId).toBe('')
  })
})
