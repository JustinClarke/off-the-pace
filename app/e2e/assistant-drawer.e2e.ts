// AX-14: the assistant chat drawer in a real browser, with the Worker mocked (no network, no model).
// The drawer exists only in a build with VITE_ASSISTANT_ENABLED=true, and it reads its cards and queries from the
// served data, so the spec needs a flag-on build served over a FINALIZED export (assistant block + card parquet):
//   VITE_DATA_BASE="" VITE_ASSISTANT_ENABLED=true VITE_ASSISTANT_WORKER_URL=/mock-worker/v1/chat vite build --outDir <scratch>/on
//   (point <scratch>/on/data at a finalized export), vite preview it, then
//   AX14_E2E=on E2E_BASE_URL=http://localhost:<port> npx playwright test e2e/assistant-drawer.e2e.ts
// AX14_E2E=off runs the flag-off checks against a default build: no launcher, no assistant request, no drawer chunk.
// The Worker is a page.route on /mock-worker/v1/chat, so there is no CORS and no real service.
import { test, expect, type Page, type Route } from '@playwright/test'

const MODE = process.env.AX14_E2E
test.skip(MODE !== 'on' && MODE !== 'off', 'set AX14_E2E=on (flag-on build, finalized export) or AX14_E2E=off (flag-off build)')

const WORKER = '**/mock-worker/v1/chat'
const OPENER = 'VER made 2 stops in the 2024 opener (driver_race.pit_stops:2024_1:VER), and his 2024 era rating is -0.357 s. He also gained 7.77 s.'

interface Seen {
  headers: Record<string, string>
  messages: number
  lastTool: string
}

/** Round 1 asks for cards, round 2 (and any repair turn) answers. Mimics the Worker's header checks. */
async function mockWorker(page: Page, answer: string, seen: Seen[] = []) {
  await page.route(WORKER, async (route: Route) => {
    const req = route.request()
    const headers = req.headers()
    const body = JSON.parse(req.postData() ?? '{}') as { messages: unknown[] }
    const tool = [...(body.messages as { role: string; content: string }[])].reverse().find((m) => m.role === 'tool')
    seen.push({ headers, messages: body.messages.length, lastTool: tool?.content ?? '' })
    const n = seen.length
    if (process.env.AX14_DEBUG && n === 2) console.log('TOOL RESULT', seen[1].lastTool)
    if (!headers['x-catalogue-version']) return route.fulfill({ status: 409, json: { error: 'app_updated' } })
    if (n > 1 && headers['x-question-ticket'] !== 'T1') return route.fulfill({ status: 403, json: { error: 'abuse_check_failed' } })
    const message =
      n === 1
        ? {
            role: 'assistant',
            content: null,
            tool_calls: [
              { id: 'call_1', type: 'function', function: { name: 'get_fact_cards', arguments: JSON.stringify({ scopes: [{ race_id: '2024_1', driver_id: 'VER' }], kinds: ['driver_race.pit_stops'] }) } },
              { id: 'call_2', type: 'function', function: { name: 'get_fact_cards', arguments: JSON.stringify({ scopes: [{ season: 2024, driver_id: 'VER' }], kinds: ['era_rating.season'] }) } },
            ],
          }
        : { role: 'assistant', content: answer }
    return route.fulfill({ json: { message, usage: { prompt_tokens: 900, completion_tokens: 60 }, ticket: 'T1' } })
  })
}

async function openDrawer(page: Page) {
  await page.goto('/')
  await page.getByRole('button', { name: 'Ask', exact: true }).click()
  await expect(page.getByRole('dialog', { name: 'Ask the assistant' })).toBeVisible()
}

async function ask(page: Page, q = 'How did VER do in the opener?') {
  await page.getByLabel('Your question').fill(q)
  await page.getByRole('button', { name: 'Send', exact: true }).click()
}

async function noHorizontalScroll(page: Page) {
  const r = await page.evaluate(() => ({ doc: document.documentElement.scrollWidth, win: window.innerWidth }))
  expect(r.doc).toBeLessThanOrEqual(r.win)
}

if (MODE === 'off') {
  test('flag off: no launcher, no dialog, no assistant request, no drawer chunk', async ({ page }) => {
    const requests: string[] = []
    page.on('request', (r) => requests.push(r.url()))
    await page.goto('/')
    await page.waitForLoadState('networkidle')
    await expect(page.getByRole('button', { name: 'Ask', exact: true })).toHaveCount(0)
    await expect(page.getByRole('dialog')).toHaveCount(0)
    expect(requests.filter((u) => /mock-worker|workers\.dev|challenges\.cloudflare|assistant\/cards|AssistantLauncher|ChatDrawer/i.test(u))).toEqual([])
  })
}

if (MODE === 'on') {
  test.describe('assistant drawer (flag on, Worker mocked)', () => {
    test('opens from the launcher; a canned answer shows chips, a struck number and a note; a chip link lands on its page', async ({ page }) => {
      test.setTimeout(180_000)
      const seen: Seen[] = []
      await mockWorker(page, OPENER, seen)
      await page.goto('/')
      // nothing assistant-related is fetched before the drawer is used
      await expect(page.getByRole('dialog')).toHaveCount(0)
      await page.getByRole('button', { name: 'Ask', exact: true }).click()
      await ask(page)

      const stops = page.getByRole('link', { name: /^2, measured/ })
      await expect(stops).toBeVisible({ timeout: 120_000 })
      // Two chips (2 stops; -0.357 modelled), one struck number (7.77)
      const era = page.getByRole('link', { name: /0\.357.*modelled/ })
      await expect(era).toBeVisible()
      expect(await era.getAttribute('style')).toContain('repeating-linear-gradient')
      await expect(page.getByTestId('struck-number')).toHaveText(/7\.77/)
      await expect(page.getByTestId('ungrounded-note')).toContainText('not backed by a card or a query result')
      // The Worker saw the catalogue version, then the ticket from round 1
      expect(seen[0].headers['x-catalogue-version']).toMatch(/^[0-9a-f]{16,}$/)
      expect(seen[0].headers['x-question-ticket']).toBeUndefined()
      expect(seen[1].headers['x-question-ticket']).toBe('T1')
      if (process.env.AX14_DEBUG) console.log('TOOL RESULT', seen[1].lastTool)

      // Details popover
      await page.getByRole('button', { name: 'Details for 2', exact: true }).click()
      await expect(page.getByTestId('chip-details')).toContainText('driver_race.pit_stops:2024_1:VER')

      // The chip link lands on the pit-gantt page with the race selected
      await stops.click()
      await expect(page).toHaveURL(/\/tyre-strategy\/pit-gantt\?.*race_id=2024_1/)
      await expect(page.getByRole('dialog')).toHaveCount(0)
      const sel = page.locator('select', { has: page.locator('option[value="2024_1"]') }).first()
      await expect(sel).toHaveValue('2024_1', { timeout: 60_000 })
    })

    test('keyboard only: open, type, send, Escape closes and focus returns to the launcher; roles and names are exposed', async ({ page }) => {
      test.setTimeout(180_000)
      await mockWorker(page, 'Nothing to add.')
      await page.goto('/')
      const opener = page.getByRole('button', { name: 'Ask', exact: true })
      await opener.focus()
      await page.keyboard.press('Enter')
      const dialog = page.getByRole('dialog', { name: 'Ask the assistant' })
      await expect(dialog).toBeVisible()
      await expect(page.getByLabel('Your question')).toBeFocused()
      const snap = await dialog.ariaSnapshot()
      expect(snap).toContain('textbox "Your question"')
      expect(snap).toContain('button "Send"')
      expect(snap).toContain('button "Close the assistant"')
      expect(snap).toContain('log "Conversation"')
      // Tab stays inside the dialog
      for (let i = 0; i < 8; i++) {
        await page.keyboard.press('Tab')
        expect(await page.evaluate(() => !!document.activeElement?.closest('[role="dialog"]'))).toBe(true)
      }
      await page.getByLabel('Your question').focus()
      await page.keyboard.type('anything')
      await page.keyboard.press('Enter')
      await expect(page.getByText('Nothing to add.')).toBeVisible({ timeout: 120_000 })
      await page.keyboard.press('Escape')
      await expect(dialog).toHaveCount(0)
      await expect(opener).toBeFocused()
    })

    for (const width of [320, 390]) {
      test(`phone width ${width}: no horizontal scroll with an answer open`, async ({ page }) => {
        test.setTimeout(180_000)
        await page.setViewportSize({ width, height: 720 })
        await mockWorker(page, OPENER)
        await openDrawer(page)
        await noHorizontalScroll(page)
        await ask(page)
        await expect(page.getByTestId('struck-number')).toBeVisible({ timeout: 120_000 })
        await noHorizontalScroll(page)
        const box = await page.getByRole('dialog').boundingBox()
        expect(box!.x).toBeGreaterThanOrEqual(0)
        expect(box!.x + box!.width).toBeLessThanOrEqual(width + 1)
      })
    }

    test('reduced motion turns the slide animation off', async ({ page }) => {
      await page.emulateMedia({ reducedMotion: 'reduce' })
      await openDrawer(page)
      expect(await page.getByRole('dialog').evaluate((el) => getComputedStyle(el).animationName)).toBe('none')
    })

    test('proxy down: a plain message, and navigation still works', async ({ page }) => {
      test.setTimeout(180_000)
      await page.route(WORKER, (route) => route.abort('connectionrefused'))
      await openDrawer(page)
      await ask(page)
      await expect(page.getByTestId('error-network')).toContainText('could not be reached', { timeout: 120_000 })
      await page.getByRole('button', { name: 'Close the assistant' }).click()
      const link = page.locator('a[href^="/"]:visible').nth(1)
      const href = await link.getAttribute('href')
      await link.click()
      await expect(page).toHaveURL(new RegExp(`${href!.split('?')[0]}`))
    })

    for (const [status, body, testid, text] of [
      [503, { error: 'paused', message: 'x' }, 'error-paused', 'paused for today'],
      [429, { error: 'visitor_limit', message: 'daily question limit reached' }, 'error-limit', 'daily question limit'],
      [409, { error: 'app_updated' }, 'error-updated', 'Reload'],
    ] as const) {
      test(`Worker ${status} shows its message`, async ({ page }) => {
        test.setTimeout(180_000)
        await page.route(WORKER, (route) => route.fulfill({ status, json: body }))
        await openDrawer(page)
        await ask(page)
        await expect(page.getByTestId(testid)).toContainText(text, { timeout: 120_000 })
        if (status === 409) await expect(page.getByRole('button', { name: 'Reload' })).toBeVisible()
      })
    }
  })
}
