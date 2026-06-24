import { test, expect } from '@playwright/test'
import { gotoFeature, waitForPerfMark, expectNoQueryError } from './_helpers'

// Subsystem 1: DuckDB-wasm init + a real parquet query. The Data Quality Audit route runs a
// season-scoped aggregate query against CDN parquet and renders the result as a ranked table.
// `first_query` firing proves the cold path closed: worker boot → parquet registration → query.
test('DuckDB-wasm initialises and a real query renders a table', async ({ page }) => {
  await gotoFeature(page, '/data-quality', /Data Quality Audit/i)

  // The engine boots and the first query resolves with a finite latency.
  await waitForPerfMark(page, 'duckdb_init')
  await waitForPerfMark(page, 'first_query')

  // The query result is materialised in the DOM (RankedTable → <table> with data rows).
  await expect(page.getByRole('heading', { name: /Lap quality by race/i })).toBeVisible()
  await expect(page.locator('table tbody tr').first()).toBeVisible()
  expect(await page.locator('table tbody tr').count()).toBeGreaterThan(0)

  await expectNoQueryError(page)
})
