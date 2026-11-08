// AX-20: the launch run's browser check, through the REAL drawer, the REAL Worker and the real model.
// Skipped unless ASSISTANT_E2E_ENDPOINT is set, and kept out of the default CI run (it spends the Worker's daily
// neuron allowance). The build under test must be the owner's flag-on PREVIEW build, built with
// VITE_ASSISTANT_ENABLED=true, VITE_ASSISTANT_WORKER_URL=<the same endpoint> and VITE_DATA_BASE at the frozen data:
//   ASSISTANT_E2E_ENDPOINT=https://<preview worker>/v1/chat E2E_BASE_URL=http://localhost:<port> \
//     npx playwright test e2e/assistant-launch.e2e.ts
// It asks one T question (chips for numbers, none struck) and one held-class question (a refusal with its reason,
// no number from a held card). It does not score the bar: the scored run is AX-13's set (5 repeats) driven the same way.
import { test, expect, type Page } from '@playwright/test'

const ENDPOINT = process.env.ASSISTANT_E2E_ENDPOINT ?? ''
test.skip(!ENDPOINT, 'set ASSISTANT_E2E_ENDPOINT to the preview Worker chat URL (the flag-on build must be built against it)')

const T_QUESTION = 'How did Verstappen do against Perez in Bahrain 2024?' // AX-13 tr-2024_1-VER (class T)
const HELD_QUESTION = 'Where did Perez lose the race in Bahrain 2024?' // AX-13 h-race-lost-2024_1-PER (held, wake_calibration)
const ANSWER_TIMEOUT = 150_000 // real model, up to 5 Worker rounds

async function ask(page: Page, question: string) {
  await page.goto('/')
  await page.getByRole('button', { name: 'Ask', exact: true }).click()
  await expect(page.getByRole('dialog', { name: 'Ask the assistant' })).toBeVisible()
  const sent = page.waitForRequest((r) => r.method() === 'POST' && r.url().startsWith(ENDPOINT))
  await page.getByLabel('Your question').fill(question)
  await page.getByRole('button', { name: 'Send', exact: true }).click()
  await sent // the drawer talks to the endpoint under test, not a mock
}

/** Fail on any failure banner the drawer can show (network, paused, limit, updated, abuse check). */
async function expectNoErrorBanner(page: Page) {
  await expect(page.locator('[data-testid^="error-"]')).toHaveCount(0)
}

test.describe('launch run (real Worker)', () => {
  test('a T question: the answer has number chips linking to pages, and no struck number', async ({ page }) => {
    test.setTimeout(ANSWER_TIMEOUT + 60_000)
    await ask(page, T_QUESTION)
    const chips = page.getByRole('link', { name: /open the page that explains it/ })
    await expect(chips.first()).toBeVisible({ timeout: ANSWER_TIMEOUT })
    await expectNoErrorBanner(page)
    expect(await chips.count()).toBeGreaterThan(0)
    // 100% of numbers grounded: nothing is struck through and there is no ungrounded note
    await expect(page.getByTestId('struck-number')).toHaveCount(0)
    await expect(page.getByTestId('ungrounded-note')).toHaveCount(0)
    // A chip opens its details with the card id, and its link lands on a real page
    const first = chips.first()
    const href = await first.getAttribute('href')
    expect(href).toMatch(/^\//)
    await first.click()
    await expect(page).toHaveURL(new RegExp(href!.split('?')[0].replace(/[.*+?^${}()|[\]\\]/g, '\\$&')))
  })

  test('a held-class question: a refusal that names its reason, and no number from a held card', async ({ page }) => {
    test.setTimeout(ANSWER_TIMEOUT + 60_000)
    await ask(page, HELD_QUESTION)
    const log = page.getByRole('log', { name: 'Conversation' })
    // The held card is listed with its reason (a dash, never a value), or the answer itself says it is held.
    const held = page.getByTestId('unusable-card')
    await expect(async () => {
      const listed = await held.count()
      const text = (await log.innerText()).toLowerCase()
      expect(listed > 0 || /\b(held|not available|cannot|can't|unable)\b/.test(text)).toBe(true)
    }).toPass({ timeout: ANSWER_TIMEOUT })
    await expectNoErrorBanner(page)
    if ((await held.count()) > 0) {
      await expect(held.first()).toContainText(/held: \S+/)
      await expect(held.first()).not.toContainText(/\b0\b/)
    }
    await expect(page.getByTestId('struck-number')).toHaveCount(0)
  })
})
