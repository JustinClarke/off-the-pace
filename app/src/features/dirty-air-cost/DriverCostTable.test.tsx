import { describe, it, expect } from 'vitest'
import { render, screen, fireEvent, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import DriverCostTable from './DriverCostTable'
import type { DirtyAirResult } from './transform'

const res = (id: string, total: number | null, over: Partial<DirtyAirResult> = {}): DirtyAirResult => ({
  rank: 1, driver_id: id, total_placeholder_cost_s: total, avg_placeholder_cost_s: total == null ? null : total / 50,
  laps_modelled: total == null ? 0 : 47, laps_unavailable: total == null ? 1 : 3, total_laps: total == null ? 1 : 50,
  unavailable_reasons: 'neutralised lap (safety car, VSC or red flag)', constructor_id: 'Ferrari',
  car_factor: '1.00 (neutral default, no public evidence used)', tyre_factors: 'HARD (C3) x0.96, SOFT (C5) x1.10',
  factor_flags: null, value_label: total == null ? 'unavailable' : 'modelled', ...over,
})

const detailId = (d: string) => `dac-detail-${d}`

describe('DriverCostTable', () => {
  const rows = [res('HAD', 12.3), res('VER', 0), res('TSU', null)]

  it('collapsed rows show only the essentials; the detail is hidden', () => {
    render(<DriverCostTable rows={rows} />)
    const btn = screen.getByRole('button', { name: 'HAD' })
    expect(btn.getAttribute('aria-expanded')).toBe('false')
    expect(document.getElementById(detailId('HAD'))?.hasAttribute('hidden')).toBe(true)
    expect(screen.getAllByText('modelled').length).toBe(2)
  })

  it('a click on the row expands the detail, a second click collapses it', async () => {
    render(<DriverCostTable rows={rows} />)
    const btn = screen.getByRole('button', { name: 'HAD' })
    const det = document.getElementById(detailId('HAD')) as HTMLElement
    expect(btn.getAttribute('aria-controls')).toBe(det.id)
    fireEvent.click(document.querySelector('tr[data-driver="HAD"]') as HTMLElement)
    expect(btn.getAttribute('aria-expanded')).toBe('true')
    expect(det.hasAttribute('hidden')).toBe(false)
    expect(within(det).getByText('HARD (C3) x0.96, SOFT (C5) x1.10')).toBeTruthy()
    expect(within(det).getByText(/neutral default/)).toBeTruthy()
    fireEvent.click(document.querySelector('tr[data-driver="HAD"]') as HTMLElement)
    expect(btn.getAttribute('aria-expanded')).toBe('false')
  })

  it('opens from the keyboard (Enter and Space) and allows several rows open at once', async () => {
    const user = userEvent.setup()
    render(<DriverCostTable rows={rows} />)
    const had = screen.getByRole('button', { name: 'HAD' })
    const ver = screen.getByRole('button', { name: 'VER' })
    had.focus()
    await user.keyboard('{Enter}')
    ver.focus()
    await user.keyboard(' ')
    expect(had.getAttribute('aria-expanded')).toBe('true')
    expect(ver.getAttribute('aria-expanded')).toBe('true')
  })

  it('unavailable driver: dash (never 0), pill says unavailable, reason is in the detail', () => {
    render(<DriverCostTable rows={rows} />)
    const tsu = document.querySelector('tr[data-driver="TSU"]') as HTMLElement
    expect(within(tsu).getAllByText('—').length).toBe(2)
    expect(within(tsu).getByText('unavailable')).toBeTruthy()
    fireEvent.click(tsu)
    expect(within(document.getElementById(detailId('TSU')) as HTMLElement).getByText(/neutralised lap/)).toBeTruthy()
  })

  it('a modelled zero prints 0.00s with a modelled label', () => {
    render(<DriverCostTable rows={rows} />)
    const ver = document.querySelector('tr[data-driver="VER"]') as HTMLElement
    expect(within(ver).getByText('0.00s')).toBeTruthy()
    expect(within(ver).getByText('modelled')).toBeTruthy()
  })
})
