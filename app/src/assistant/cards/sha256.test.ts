import { describe, it, expect } from 'vitest'
import { createHash } from 'node:crypto'
import { sha256Hex } from './sha256'

describe('sha256Hex', () => {
  it('matches node:crypto on known and random inputs', () => {
    expect(sha256Hex('abc')).toBe('ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad')
    for (const s of ['', 'a'.repeat(55), 'a'.repeat(56), 'a'.repeat(64), 'é∑😀'.repeat(40), JSON.stringify({ x: [1, 2, 3] })]) {
      expect(sha256Hex(s)).toBe(createHash('sha256').update(s, 'utf8').digest('hex'))
    }
  })
})
