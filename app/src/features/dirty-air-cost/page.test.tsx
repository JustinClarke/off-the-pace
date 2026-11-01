import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { FilterProvider } from '../../state/FilterContext'
import type { DirtyAirCostRow, DirtyAirLapRow } from './queries'

// Record every useQuery call; answer from fixtures synchronously (no DuckDB, no parquet).
const calls: { name: string; params: Record<string, unknown>; enabled: boolean }[] = []

const row = (driver_id: string, total: number): DirtyAirCostRow => ({
  driver_id, total_placeholder_cost_s: total, avg_placeholder_cost_s: total / 50,
  laps_modelled: 50, laps_unavailable: 0, total_laps: 50, unavailable_reasons: null,
  corner_class: 'medium', race_loss_s_per_lap_within_1s: 0.27, avg_lap_loss_s: 0.27,
  tyre_factors: 'MEDIUM (C3) x1.00', laps_tyre_neutral: 0, constructor_id: 'Ferrari',
  constructor_factor: 1, constructor_factor_source: 'neutral_default', constructor_basis: 'neutral default',
  laps_lap_loss_bounded: 0, factor_flags: null, era: 'e', era_factor: 0.8, loss_source: 'race_structure',
  loss_bounded: false, loss_basis: 'Assumed rule', value_kind: 'placeholder', disclaimer: 'd', disclaimer_placeholder: 'p',
})

const lap = (n: number): DirtyAirLapRow => ({
  lap_number: n, share_lap_within_1s: 0.5, share_lap_within_2s: 0.8, wake_exposure: 0.65,
  wake_cost_placeholder_s: 0.17, loss_s_per_lap_within_1s: 0.27, race_loss_s_per_lap_within_1s: 0.27,
  compound_class: 'MEDIUM', tyre_c_number: 'C3', compound_factor: 1, constructor_factor: 1, unavailable_reason: null,
})

vi.mock('../../data/hooks/useQuery', async importOriginal => ({
  ...(await importOriginal<typeof import('../../data/hooks/useQuery')>()),
  useQuery: (name: string, params: Record<string, unknown>, options?: { enabled?: boolean }) => {
    const enabled = options?.enabled ?? true
    calls.push({ name, params, enabled })
    if (!enabled) return { data: undefined, isLoading: false, error: null }
    if (name === 'dirty-air-cost.race') return { data: [row('HAM', 9), row('LEC', 5)], isLoading: false, error: null }
    return { data: [lap(1), lap(2), lap(3)], isLoading: false, error: null }
  },
}))

vi.mock('../shared/useRaceOptions', () => ({
  useRaceOptions: () => ({
    raceOptions: [{ value: '2025_5', label: 'Race Five' }, { value: '2025_6', label: 'Race Six' }],
    isLoading: false,
  }),
}))

const { default: DirtyAirCostPage } = await import('./page')

const renderAt = (url: string) => render(
  <MemoryRouter initialEntries={[url]}><FilterProvider><DirtyAirCostPage /></FilterProvider></MemoryRouter>,
)
const raceCalls = () => calls.filter(c => c.name === 'dirty-air-cost.race')
const readout = () => screen.getByText(/Hover or focus the chart|^Lap \d+:/)

beforeEach(() => { calls.length = 0 })

describe('race query is gated on a picked race (review R3)', () => {
  it('no race: the race query is disabled and the select-a-race state shows', () => {
    renderAt('/aero/dirty-air?season=2025')
    expect(raceCalls().length).toBeGreaterThan(0)
    expect(raceCalls().every(c => !c.enabled)).toBe(true)
    expect(screen.getByText('Select a race to view the dirty air cost leaderboard.')).toBeTruthy()
  })

  it('a ?race= deep link enables the query on first render and shows the race', () => {
    renderAt('/aero/dirty-air?season=2025&race=2025_5')
    expect(raceCalls()[0]).toMatchObject({ enabled: true, params: { season: 2025, raceId: '2025_5' } })
    expect(screen.getByText('Race Five · 2025')).toBeTruthy()
  })

  it('picking a race from the select enables it', () => {
    renderAt('/aero/dirty-air?season=2025')
    fireEvent.change(screen.getByRole('combobox'), { target: { value: '2025_6' } })
    expect(raceCalls().at(-1)).toMatchObject({ enabled: true, params: { raceId: '2025_6' } })
  })
})

describe('state resets with the race and the driver (review R4)', () => {
  it('expanded table rows collapse when the race changes', () => {
    renderAt('/aero/dirty-air?season=2025&race=2025_5')
    fireEvent.click(document.querySelector('tr[data-driver="HAM"]') as HTMLElement)
    expect(document.querySelector('tr[data-driver="HAM"] button')?.getAttribute('aria-expanded')).toBe('true')
    fireEvent.change(screen.getByRole('combobox'), { target: { value: '2025_6' } })
    expect(screen.getByText('Race Six · 2025')).toBeTruthy()
    expect(document.querySelector('tr[data-driver="HAM"] button')?.getAttribute('aria-expanded')).toBe('false')
  })

  it('the lap cursor clears when another driver is picked', () => {
    renderAt('/aero/dirty-air?season=2025&race=2025_5')
    const group = screen.getByRole('group', { name: /HAM/ })
    fireEvent.keyDown(group, { key: 'ArrowRight' })
    expect(readout().textContent).toMatch(/^Lap 1:/)
    const bars = screen.getByRole('list', { name: /Total wake cost per driver/ })
    fireEvent.click(within(bars).getAllByRole('button')[1])
    expect(screen.getByRole('group', { name: /LEC/ })).toBeTruthy()
    expect(readout().textContent).toMatch(/^Hover or focus the chart/)
  })
})
