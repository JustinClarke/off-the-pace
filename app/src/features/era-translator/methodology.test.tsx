import { describe, it, expect } from 'vitest'
import { renderToStaticMarkup } from 'react-dom/server'
import { methodologyContent } from './methodology'

const text = renderToStaticMarkup(methodologyContent)
  .replace(/<[^>]+>/g, ' ')
  .replace(/&#x27;/g, "'")
  .replace(/&quot;/g, '"')
  .replace(/&amp;/g, '&')
  .replace(/\s+/g, ' ')

// T34 (era pages, WI-14b): the rating is a gap to the teammate (F40) with no era
// offset (F45). The text must say so, and must not keep the pre-fix claims that it
// is measured against the (era-normalised) field average or corrected by a
// bridge-driver offset.
describe('T34: Era Translator methodology matches era_adjusted_rating', () => {
  it('states negative = faster than his teammate', () => {
    expect(text).toMatch(/Negative = faster than his teammate/)
  })

  it('does not describe the rating as relative to the field average', () => {
    expect(text).not.toMatch(/field average/i)
    expect(text).not.toMatch(/era-normalised/i)
  })

  it('says no era offset is applied, and no longer claims a bridge-driver anchor', () => {
    expect(text).toMatch(/No era offset is applied/)
    expect(text).not.toMatch(/offset by the era shift/i)
    expect(text).not.toMatch(/anchor/i)
  })
})
