import { test, expect } from '@playwright/test'

// Baseline reachability: the SPA shell boots, the home route renders without a runtime error, and
// client-side routing into a data feature works. Needs no DuckDB/ONNX that is covered by the
// dedicated subsystem specs. Cheap canary that the deploy is fundamentally up.
test.describe('app shell', () => {
  test('home page loads and renders the brand', async ({ page }) => {
    const errors: string[] = []
    page.on('pageerror', (e) => errors.push(String(e)))

    await page.goto('/')
    // The app mounts into #root; a non-empty root means React hydrated the shell.
    await expect(page.locator('#root')).not.toBeEmpty()
    await expect(page).toHaveTitle(/off the pace|f1|pace/i)
    expect(errors, `uncaught page errors: ${errors.join('\n')}`).toEqual([])
  })

  test('client-side navigation into a data route works', async ({ page }) => {
    await page.goto('/data-quality')
    await expect(page.getByRole('heading', { level: 1, name: /Data Quality Audit/i })).toBeVisible()
  })
})
