import { chromium } from '@playwright/test'
const b = await chromium.launch(); const p = await b.newPage()
await p.goto('http://localhost:5173/tyre-strategy/survival', { waitUntil: 'networkidle' }); await p.waitForTimeout(3000)
const s = () => p.$$eval('select', ss => ss.map(x => ({v:x.value, n:x.options.length, d:x.disabled})))
await p.locator('select').nth(1).selectOption('2025_1'); await p.waitForTimeout(3000); console.log('race', JSON.stringify(await s()), p.url())
await b.close()
