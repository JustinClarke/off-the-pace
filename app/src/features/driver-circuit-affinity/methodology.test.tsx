import { describe, it, expect } from 'vitest'
import { renderToStaticMarkup } from 'react-dom/server'
import { methodologyContent } from './methodology'

const text = renderToStaticMarkup(methodologyContent)
  .replace(/<[^>]+>/g, ' ')
  .replace(/&#x27;/g, "'")
  .replace(/&quot;/g, '"')
  .replace(/&amp;/g, '&')
  .replace(/\s+/g, ' ')

// T34 (F44, WI-14b), the sign-text half: the methodology must describe what the
// heatmap draws (affinity_vs_driver_mean_s, a deviation from the driver's own mean),
// not the level it used to draw, and must not repeat the audit's stale claims.
describe('T34: Driver Circuit Affinity methodology matches the drawn column', () => {
  it('names the drawn column', () => {
    expect(text).toContain('affinity_vs_driver_mean_s')
  })

  it('states negative (green) = better against the teammate than the driver\'s own average', () => {
    expect(text).toMatch(/negative \(green\) = the driver does better against his teammate at this circuit than his own average/)
  })

  it('says the estimate is shrunk toward the driver\'s own mean, not toward neutral', () => {
    expect(text).toMatch(/shrunk toward the driver's own mean/)
    expect(text).not.toMatch(/toward neutral/)
  })

  it('does not claim the stale 2018–2024 window or a season-average reference', () => {
    expect(text).not.toMatch(/2018[–-]2024/)
    expect(text).not.toMatch(/season-average/)
  })
})
