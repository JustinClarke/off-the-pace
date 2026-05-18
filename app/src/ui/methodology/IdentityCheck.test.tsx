import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import IdentityCheck from './IdentityCheck'

describe('IdentityCheck', () => {
  it('shows green checkmark when within tolerance', () => {
    render(<IdentityCheck explained={10.0001} observed={10} tolerance={1e-4} />)
    expect(screen.getByText('✓')).toBeInTheDocument()
    expect(screen.getByText('Identity valid')).toBeInTheDocument()
  })

  it('shows orange warning when outside tolerance', () => {
    render(<IdentityCheck explained={10.001} observed={10} tolerance={1e-4} />)
    expect(screen.getByText('⚠')).toBeInTheDocument()
    expect(screen.getByText(/Identity gap:/)).toBeInTheDocument()
  })

  it('formats gap value correctly', () => {
    render(<IdentityCheck explained={10.01} observed={10} tolerance={1e-4} />)
    expect(screen.getByText(/Identity gap: 0\.0100/)).toBeInTheDocument()
  })

  it('accepts custom label', () => {
    render(<IdentityCheck explained={10} observed={10} label="additive closure" />)
    const badge = screen.getByText('Identity valid').closest('span[title]')
    expect(badge?.getAttribute('title')).toMatch(/additive closure/)
  })

  it('uses default tolerance of 1e-4', () => {
    const { rerender } = render(
      <IdentityCheck explained={10.00009} observed={10} />
    )
    expect(screen.getByText('Identity valid')).toBeInTheDocument()

    rerender(<IdentityCheck explained={10.00015} observed={10} />)
    expect(screen.getByText(/Identity gap:/)).toBeInTheDocument()
  })

  it('handles negative values', () => {
    render(<IdentityCheck explained={-5.00001} observed={-5} tolerance={1e-4} />)
    expect(screen.getByText('Identity valid')).toBeInTheDocument()
  })
})
