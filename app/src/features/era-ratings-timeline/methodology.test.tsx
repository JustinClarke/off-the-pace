import { describe, it, expect } from 'vitest'
import { renderToStaticMarkup } from 'react-dom/server'
import { methodologyContent } from './methodology'

const text = renderToStaticMarkup(methodologyContent)
  .replace(/<[^>]+>/g, ' ')
  .replace(/&#x27;/g, "'")
  .replace(/&quot;/g, '"')
  .replace(/&amp;/g, '&')
  .replace(/\s+/g, ' ')

// T34 (era pages, WI-14b): see era-translator/methodology.test.tsx. Same rating,
// drawn as career lines.
describe('T34: Era Ratings Timeline methodology matches era_adjusted_rating', () => {
  it('states negative = faster than his teammate(s)', () => {
    expect(text).toMatch(/Negative = faster than his teammate/)
  })

  it('does not describe the rating as relative to the field average', () => {
    expect(text).not.toMatch(/field average/i)
    expect(text).not.toMatch(/era-normalised/i)
  })

  it('says no era offset is applied, and does not describe an estimated one', () => {
    expect(text).toMatch(/no era offset is applied/)
    expect(text).not.toMatch(/offset is estimated/i)
    expect(text).not.toMatch(/era-offset estimation uncertainty/i)
  })
})
