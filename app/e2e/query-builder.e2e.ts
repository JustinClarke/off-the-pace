// AX-06: the real query_data engine in a browser. Needs a Vite DEV server (the dev-only module
// import below is unavailable in a production bundle) whose /data serves an AX-05 scratch export,
// so it is skipped unless AX06_E2E=1. Run (see AX-06 PROVENANCE.txt):
//   VITE_DATA_BASE="" npx vite --config <scratch>/e2e/vite.config.ts   # publicDir with data -> export
//   AX06_E2E=1 E2E_BASE_URL=http://localhost:5199 npx playwright test e2e/query-builder.e2e.ts
import { test, expect } from '@playwright/test'

test.skip(!process.env.AX06_E2E, 'set AX06_E2E=1 and serve a scratch export through the dev server')

type Hook = {
  queryData: (req: unknown) => Promise<Record<string, unknown>>
  runSlow: (ms: number) => Promise<{ outcome: string; elapsed: number; after: { x: number }[] }>
}

test('query_data runs on the real engine, and a cancelled query leaves a usable connection', async ({ page }) => {
  test.setTimeout(120_000)
  await page.goto('/')
  await page.evaluate(async () => {
    await import(/* @vite-ignore */ '/src/assistant/queryBuilder/realEngine.ts')
  })
  const out = await page.evaluate(async () => {
    const hook = (window as unknown as { __axQueryBuilder: Hook }).__axQueryBuilder
    return hook.queryData({
      view: 'qv_laps',
      filters: [{ col: 'season', op: 'eq', val: 2024 }, { col: 'race_id', op: 'eq', val: '2024_8' }],
      group_by: ['driver_id'],
      aggregate: { fn: 'median', col: 'lap_time_s' },
      order: 'value_asc',
      limit: 5,
    })
  })
  expect(out.status).toBe('ok')
  expect(out.label).toBe('computed_not_card')
  expect(out.rows_shown).toBe(5)

  const slow = await page.evaluate(async () => {
    const hook = (window as unknown as { __axQueryBuilder: Hook }).__axQueryBuilder
    return hook.runSlow(60)
  })
  expect(slow.outcome).toBe('timeout')
  expect(slow.elapsed).toBeLessThan(10_000)
  expect(slow.after).toEqual([{ x: 42 }])

  const again = await page.evaluate(async () => {
    const hook = (window as unknown as { __axQueryBuilder: Hook }).__axQueryBuilder
    return hook.queryData({ view: 'qv_stints', filters: [{ col: 'season', op: 'eq', val: 2024 }], aggregate: { fn: 'count', col: 'stints' } })
  })
  expect(again.status).toBe('ok')
})
