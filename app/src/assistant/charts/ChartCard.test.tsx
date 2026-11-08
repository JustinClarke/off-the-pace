import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { ChartCardView } from './ChartCard'
import type { StoredChart } from './chartStore'

const chart: StoredChart = {
  chart_id: 'c1', label: 'computed_not_card', n: [2, 1], note: 'Observed laps.',
  spec: { type: 'line', title: '<img src=x onerror=alert(1)>', x: { col: 'lap_number', label: 'Lap' }, y: { col: 'value', label: 'Time (s)' }, series: [] },
  series: [{ label: 'LEC', points: [{ x: 1, y: 90.5 }, { x: 2, y: 91 }] }, { label: 'SAI', points: [{ x: 1, y: 90.9 }] }],
}

describe('ChartCard', () => {
  it('shows label and n, and a hidden table of the points', () => {
    const { container } = render(<ChartCardView chart={chart} />)
    expect(screen.getByText('computed_not_card')).toBeTruthy()
    expect(screen.getByText(/LEC: n = 2/)).toBeTruthy()
    expect(screen.getByText(/SAI: n = 1/)).toBeTruthy()
    const rows = container.querySelectorAll('table.sr-only tbody tr')
    expect(rows).toHaveLength(3)
  })
  it('renders an HTML title as text, creating no img element', () => {
    const { container } = render(<ChartCardView chart={chart} />)
    expect(container.querySelector('img')).toBeNull()
    expect(screen.getAllByText('<img src=x onerror=alert(1)>').length).toBeGreaterThan(0)
  })
})
