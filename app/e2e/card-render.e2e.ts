import { test, expect, type Page } from '@playwright/test'
import { readFileSync } from 'node:fs'

// AX-04: the rendered pages show the numbers the headless runner computed. Reads each page's
// "Export CSV" (the page's own query + transform output, as rendered) and compares it with the
// values headless.parity.test.ts wrote to AX04_EXPECT. Needs the app served over the SAME data
// as the headless run (a VITE_DATA_BASE="" build whose /data is the scratch export). Skips when
// AX04_EXPECT is unset.
const EXPECT = process.env.AX04_EXPECT
test.skip(!EXPECT, 'set AX04_EXPECT to the JSON headless.parity.test.ts writes (AX04_EXPECT_OUT)')

type Exp = {
  eraAll: { driver_id: string; season: number; value: number; low: number; high: number }[]
  raceLost: { season: number; race_id: string; driver_id: string; csv: Record<string, string>[] }
  pit: { season: number; race_id: string; csv: Record<string, unknown>[] }
}
const exp: Exp = EXPECT ? JSON.parse(readFileSync(EXPECT, 'utf8')) : ({} as Exp)

async function exportCsv(page: Page): Promise<Record<string, string>[]> {
  const button = page.getByRole('button', { name: /Export CSV/i })
  await expect(button).toBeVisible()
  const [download] = await Promise.all([page.waitForEvent('download'), button.click()])
  const text = readFileSync(await download.path(), 'utf8')
  const [head, ...lines] = text.trim().split('\n')
  const delim = head.includes(';') && !head.includes(',') ? ';' : ','
  const keys = head.split(delim)
  return lines.map((l) => Object.fromEntries(l.split(delim).map((v, i) => [keys[i], v])))
}

test('race-lost renders the headless component totals (4 dp)', async ({ page }) => {
  const { season, race_id, driver_id, csv } = exp.raceLost
  await page.goto(`/lap-decomposition/race-lost?season=${season}&race=${race_id}&driver=${driver_id}`)
  const rows = await exportCsv(page)
  expect(rows.map((r) => [r.component, r.total_s])).toEqual(csv.map((r) => [r.component, r.total_s]))
})

test('era ratings timeline renders the headless ratings and CIs (4 dp CSV)', async ({ page }) => {
  await page.goto('/drivers/ratings-timeline')
  const rows = await exportCsv(page)
  expect(rows.length).toBeGreaterThan(0)
  for (const r of rows) {
    const e = exp.eraAll.find((x) => x.driver_id === r.driver_id && x.season === Number(r.season))
    expect(e, `${r.driver_id} ${r.season}`).toBeTruthy()
    expect(r.era_adjusted_rating_s).toBe(e!.value.toFixed(4))
    expect(r.ci_low_s).toBe(e!.low.toFixed(4))
    expect(r.ci_high_s).toBe(e!.high.toFixed(4))
  }
})

test('pit-gantt renders the headless stints (laps)', async ({ page }) => {
  const { season, race_id, csv } = exp.pit
  await page.goto(`/tyre-strategy/pit-gantt?season=${season}&race_id=${race_id}`)
  const rows = await exportCsv(page)
  const pick = (r: Record<string, unknown>) => [r.driver_id, String(r.stint_number), String(r.start_lap), String(r.end_lap), String(r.optimal_pit_lap_in_stint ?? '')]
  expect(rows.map(pick)).toEqual(csv.map(pick))
})
