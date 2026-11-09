import { describe, it, expect } from 'vitest'
import { render, screen, fireEvent, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import AnswerView, { pieces, UNGROUNDED_NOTE } from './AnswerView'
import { card } from './testKit'
import type { Card } from '../cards/card.types'

const wrap = (ui: React.ReactElement) => render(<MemoryRouter>{ui}</MemoryRouter>)
const sourcesOf = (cards: Card[], results: unknown[] = []) => ({ cards, results, texts: ['question'] })

describe('AnswerView render-time grounding', () => {
  const corner = card('corner_phase.season:2024:NOR:braking') // computed, links to /drivers/corner-skill?season=2024
  const gap = card('race.teammate_gap:2024_1:VER')

  it('a matched number becomes a chip that links to the card page', () => {
    wrap(<AnswerView answer="NOR gained 0.0413 s in braking." sources={sourcesOf([corner])} />)
    const link = screen.getByRole('link', { name: /0\.0413.*computed/ })
    expect(link.getAttribute('href')).toContain('/drivers/corner-skill')
    expect(link.getAttribute('href')).toContain('season=2024')
    expect(screen.queryByTestId('ungrounded-note')).toBeNull()
  })

  it('opens the details (value, interval, n, label, versions) from the info button and on focus', () => {
    wrap(<AnswerView answer="NOR gained 0.0413 s in braking." sources={sourcesOf([corner])} />)
    fireEvent.click(screen.getByRole('button', { name: 'Details for 0.0413' }))
    const d = screen.getByTestId('chip-details')
    expect(within(d).getByText(corner.id)).toBeTruthy()
    expect(d.textContent).toContain('294 cells')
    expect(d.textContent).toContain('computed')
    expect(d.textContent).toContain(`label ${corner.versions.label_version}`)
    expect(d.textContent).toContain('0.0303')
    // hover/focus also opens it (unpinned)
    fireEvent.click(screen.getByRole('button', { name: 'Details for 0.0413' })) // unpin
    expect(screen.queryByTestId('chip-details')).toBeNull()
    fireEvent.focus(screen.getByRole('link', { name: /0\.0413/ }))
    expect(screen.getByTestId('chip-details')).toBeTruthy()
  })

  it('an unmatched number is struck through and noted', () => {
    wrap(<AnswerView answer="NOR gained 0.0413 s and 9.87 s over the season." sources={sourcesOf([corner])} />)
    const struck = screen.getByTestId('struck-number')
    expect(struck.tagName).toBe('DEL')
    expect(struck.textContent).toContain('9.87')
    expect(screen.getByTestId('ungrounded-note').textContent).toContain(UNGROUNDED_NOTE)
    expect(screen.getByTestId('ungrounded-note').textContent).toContain('9.87')
  })

  it('a card with no page link still chips but without a link', () => {
    wrap(<AnswerView answer="VER was 0.62 s a lap faster over 46 laps." sources={sourcesOf([gap])} />)
    expect(screen.queryByRole('link')).toBeNull()
    expect(screen.getByRole('button', { name: 'Details for 0.62' })).toBeTruthy()
    expect(screen.queryByTestId('struck-number')).toBeNull()
  })

  it('modelled cards are hatched and say modelled; the details carry the modelled note', () => {
    const modelled: Card = { ...corner, id: 'corner_phase.season:2024:NOR:modelled', label: 'modelled' }
    wrap(<AnswerView answer="About 0.0413 s." sources={sourcesOf([modelled])} />)
    const link = screen.getByRole('link', { name: /0\.0413.*modelled/ })
    expect(link.getAttribute('style') ?? '').toContain('repeating-linear-gradient')
    expect(link.textContent).toContain('modelled')
    fireEvent.click(screen.getByRole('button', { name: 'Details for 0.0413' }))
    expect(screen.getByTestId('chip-details').textContent).toContain('Modelled')
  })

  it('a number from a query result is tagged plain count/average and has no link', () => {
    wrap(<AnswerView answer="VER ran 31 stints." sources={sourcesOf([], [{ rows: [{ driver_id: 'VER', value: 31, n: 31 }] }])} />)
    expect(screen.getByText('plain count/average')).toBeTruthy()
    expect(screen.queryByRole('link')).toBeNull()
    expect(screen.queryByTestId('struck-number')).toBeNull()
  })

  it('unavailable and held cards are listed with a dash and their reason, never 0', () => {
    const un = card('race.teammate_gap:2020_14:HAM')
    const held = card('pit_strategy.verdict:2018_1:RIC:1')
    wrap(<AnswerView answer="No value is published for HAM." sources={sourcesOf([un, held])} />)
    const rows = screen.getAllByTestId('unusable-card')
    expect(rows).toHaveLength(2)
    expect(rows[0].textContent).toContain('—')
    expect(rows[0].textContent).toContain('unavailable: rated on 1 paired lap')
    expect(rows[1].textContent).toContain('held:')
    expect(rows[1].textContent).toContain('PIT_CALL_REPRODUCTION_RATE')
    expect(rows.map((r) => r.textContent).join(' ')).not.toMatch(/\b0\b(?! of)/)
  })

  it('rule failures and the repair-skipped note render visibly', () => {
    wrap(
      <AnswerView
        answer="NOR gained 0.0413 s."
        sources={sourcesOf([corner])}
        notes={[{ kind: 'rule', code: 'THIN_SAMPLE', detail: 'missing wording (1)' }]}
        repairSkipped
      />,
    )
    expect(screen.getByTestId('rule-notes').textContent).toContain('THIN_SAMPLE')
  })

  it('pieces keeps the text between numbers intact', () => {
    const { parts } = pieces('A 0.0413 B 9.87 C', sourcesOf([corner]))
    expect(parts.map((p) => (p.kind === 'text' ? p.text : p.text)).join('')).toBe('A 0.0413 B 9.87 C')
    expect(parts.filter((p) => p.kind === 'struck').map((p) => p.text)).toEqual(['9.87'])
  })

  it('a leading minus (hyphen or U+2212) is inside the chip or the strike, and the text stays intact', () => {
    for (const sign of ['-', '\u2212']) {
      const answer = `Change of ${sign}0.0413 s, not ${sign}9.87 s.`
      const { parts } = pieces(answer, sourcesOf([corner]))
      expect(parts.filter((p) => p.kind === 'chip').map((p) => p.text)).toEqual([`${sign}0.0413`])
      expect(parts.filter((p) => p.kind === 'struck').map((p) => p.text)).toEqual([`${sign}9.87`])
      expect(parts.map((p) => p.text).join('')).toBe(answer)
    }
  })

  it('a range such as 3-5 does not pull the hyphen into a chip', () => {
    const { parts } = pieces('Laps 3-5 held.', sourcesOf([corner]))
    expect(parts.some((p) => p.kind !== 'text' && p.text.startsWith('-'))).toBe(false)
  })

  it('does not execute markup in the answer text', () => {
    const { container } = wrap(<AnswerView answer={'<img src=x onerror=alert(1)> 0.0413'} sources={sourcesOf([corner])} />)
    expect(container.querySelector('img')).toBeNull()
  })
})

describe('AnswerView "Go to page" buttons (navigate results)', () => {
  const sources = { cards: [], results: [], texts: [] }
  it('renders a button to a shipped route, labelled with the page title, routed by the app router', () => {
    wrap(<AnswerView answer="Here it is." sources={sources} links={['/tyre-strategy/degradation?season=2024']} />)
    const a = screen.getByTestId('go-to-page')
    expect(a.getAttribute('href')).toBe('/tyre-strategy/degradation?season=2024')
    expect(a.textContent).toMatch(/^Go to page: \S/)
  })
  it('renders nothing for a route that is not shipped, an external URL or a protocol-relative URL', () => {
    wrap(<AnswerView answer="x" sources={sources} links={['/nope?season=2024', 'https://evil.example/', '//evil.example/a', '/race-craft']} />)
    expect(screen.queryByTestId('go-to-page')).toBeNull()
  })
  it('renders no button when there are no links', () => {
    wrap(<AnswerView answer="x" sources={sources} />)
    expect(screen.queryByTestId('go-to-page')).toBeNull()
  })
})
