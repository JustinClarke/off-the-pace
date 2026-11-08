import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import Provenance from './Provenance'

describe('Provenance', () => {
  it('truncates dataVersion to 8 characters', () => {
    render(<Provenance meta={{ dataWindow: '2018–2025', dataVersion: '30f91247d7cb651e' }} />)
    expect(screen.getByText('2018–2025 · data:30f91247')).toBeInTheDocument()
  })

  it('renders model version, fingerprint and label version', () => {
    render(<Provenance meta={{ modelVersion: '14', datasetFingerprint: '5dbd8e51502a', labelVersion: 'v16' }} />)
    expect(screen.getByText('v14 · sha:5dbd8e51 · label v16')).toBeInTheDocument()
  })

  it('renders nothing when every field is missing', () => {
    const { container } = render(<Provenance meta={{}} />)
    expect(container).toBeEmptyDOMElement()
  })
})
