import { test, expect, type Page } from '@playwright/test'
import { expectNoQueryError } from './_helpers'

// AX-03: card links land on their page with the race (and driver) selected, and the page no longer
// strips the race key on mount. The URLs below are the ones buildRouteUrl()/cardLink() emit
// (asserted in src/nav/routeParams.test.ts); they are spelled out here because routeParams.ts reads
// import.meta.env through data/manifest.ts, which Playwright's Node loader does not provide.
// The race and driver must exist in the data the app is served: run against local data (VITE_DATA_BASE="" build) or the CDN. Override with E2E_CARD_RACE /
// E2E_CARD_DRIVER / E2E_CARD_COMPOUND if the default is not in the served export.
const RACE = process.env.E2E_CARD_RACE ?? '2024_8'
const DRIVER = process.env.E2E_CARD_DRIVER ?? 'LEC'
const COMPOUND = process.env.E2E_CARD_COMPOUND ?? 'MEDIUM'

const SEASON = RACE.split('_')[0]
const ROUND = String(Number(RACE.split('_')[1]))
const LINKS = {
  raceLost: `/lap-decomposition/race-lost?season=${SEASON}&race=${RACE}&driver=${DRIVER}`,
  waterfall: `/lap-decomposition/waterfall?season=${SEASON}&race=${ROUND}&driver=${DRIVER}`,
  pitGantt: `/tyre-strategy/pit-gantt?season=${SEASON}&race_id=${RACE}`,
  degradation: `/tyre-strategy/degradation?season=${SEASON}&race=${RACE}`,
  survival: `/tyre-strategy/survival?season=${SEASON}&race_id=${RACE}&compound=${COMPOUND}`,
}

/** Wait until a <select> holding `value` as an option is rendered with it selected. */
async function expectSelected(page: Page, value: string): Promise<void> {
  const sel = page.locator('select', { has: page.locator(`option[value="${value}"]`) }).first()
  await expect(sel).toHaveValue(value)
}

async function expectKept(page: Page, key: string, value: string): Promise<void> {
  // Give mount effects time to run, then the key must still be in the URL.
  await page.waitForLoadState('networkidle')
  expect(new URL(page.url()).searchParams.get(key), `${key} after mount`).toBe(value)
}

test.describe('card links (AX-03)', () => {
  test('race-lost: race and driver selected', async ({ page }) => {
    await page.goto(LINKS.raceLost)
    await expectSelected(page, RACE)
    await expectSelected(page, DRIVER)
    await expectKept(page, 'race', RACE)
    await expectNoQueryError(page)
  })

  test('waterfall: integer round plus season, driver highlighted', async ({ page }) => {
    await page.goto(LINKS.waterfall)
    await expect(page.getByText(`Race ${RACE}`, { exact: true })).toBeVisible()
    await expect(page.getByRole('button', { name: DRIVER, exact: true })).toHaveClass(/border-accent text-accent/)
    await expectKept(page, 'race', ROUND)
    await expectNoQueryError(page)
  })

  test('pit-gantt: race_id selected', async ({ page }) => {
    await page.goto(LINKS.pitGantt)
    await expectSelected(page, RACE)
    await expectKept(page, 'race_id', RACE)
    await expectNoQueryError(page)
  })

  test('degradation: race selected', async ({ page }) => {
    await page.goto(LINKS.degradation)
    await expectSelected(page, RACE)
    await expectKept(page, 'race', RACE)
    await expectNoQueryError(page)
  })

  test('survival: race_id and compound selected', async ({ page }) => {
    await page.goto(LINKS.survival)
    await expectSelected(page, RACE)
    await expectSelected(page, COMPOUND)
    await expectKept(page, 'race_id', RACE)
    await expectKept(page, 'compound', COMPOUND)
    await expectNoQueryError(page)
  })

  test('the race key survives mount on every race page (?season=<yyyy>&race=<race>)', async ({ page }) => {
    for (const route of ['/lap-decomposition/race-lost', '/aero/field-pace', '/aero/track-evolution', '/lap-decomposition/sectors']) {
      await page.goto(`${route}?season=${SEASON}&race=${RACE}`)
      await expectKept(page, 'race', RACE)
    }
  })
})
