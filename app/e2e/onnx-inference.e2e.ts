import { test, expect } from '@playwright/test'
import { gotoFeature, waitForPerfMark, expectNoQueryError } from './_helpers'

// Subsystem 2: in-browser ONNX inference. The Degradation Simulator scores a default stint through
// onnxruntime-web on mount (predictLaps → getSession), so `onnx_warmup` firing proves an
// InferenceSession was created from the live CDN model and ran without a wasm/runtime fault. The
// chart panel rendering confirms the inference output reached the UI.
test('onnxruntime-web warms a session and serves an inference', async ({ page }) => {
  const consoleErrors: string[] = []
  page.on('console', (msg) => {
    if (msg.type() === 'error') consoleErrors.push(msg.text())
  })

  // H1 is "Build Your Own Stint" (the Degradation Simulator's display title).
  await gotoFeature(page, '/ml/simulator', /Build Your Own Stint/i)

  // DuckDB feeds the simulator its history; ONNX then warms and scores the stint.
  await waitForPerfMark(page, 'duckdb_init')
  await waitForPerfMark(page, 'onnx_warmup')

  // The simulator renders a chart (Recharts → <svg>) once history + predictions resolve.
  await expect(page.locator('svg').first()).toBeVisible()
  await expectNoQueryError(page)

  // A failed ONNX run surfaces as a "Session already started" / ort error in the console.
  const ortErrors = consoleErrors.filter((t) => /ort|onnx|session already started/i.test(t))
  expect(ortErrors, `ONNX runtime errors: ${ortErrors.join('\n')}`).toEqual([])
})
