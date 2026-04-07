import { test, expect } from '@playwright/test'
import { gotoFeature, waitForPerfMark, expectNoQueryError } from './_helpers'

// Subsystem 3: the additive-identity UI. The Lap Time Decomposition waterfall reads fct_lap_residuals
// and renders the seven-term decomposition whose closure is a live integrity check (Σ components ==
// pace_delta). This is the "identity-check UI" the audit calls out it must boot end-to-end and draw.
test('the additive-identity waterfall loads and renders its chart', async ({ page }) => {
  await gotoFeature(page, '/lap-decomposition/waterfall', /Lap Time Decomposition/i)

  await waitForPerfMark(page, 'first_query')

  // The waterfall (Recharts → <svg>) draws once the residuals query resolves.
  await expect(page.locator('svg').first()).toBeVisible()
  await expectNoQueryError(page)
})
