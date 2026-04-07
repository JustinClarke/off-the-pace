import { expect, type Page } from '@playwright/test'

// A perf mark recorded by the observability layer (src/observability/index.ts → window.__OTP_PERF__).
// Always populated even with telemetry off, so the E2E can assert the heavy subsystems actually ran.
export interface PerfMark {
  name: string
  value: number
  unit: 'millisecond' | 'none'
  ts: number
}

/**
 * Wait until the app has recorded a finite perf mark with the given name and return its value.
 * This is the deterministic signal that a client subsystem booted:
 *   duckdb_init → DuckDB-wasm instantiated · first_query → a parquet query resolved ·
 *   onnx_warmup → an ONNX InferenceSession was created and is serving.
 */
export async function waitForPerfMark(
  page: Page,
  name: string,
  timeout = 75_000,
): Promise<number> {
  const handle = await page.waitForFunction(
    (markName) => {
      const marks = (window as unknown as { __OTP_PERF__?: PerfMark[] }).__OTP_PERF__ ?? []
      const hit = marks.find((m) => m.name === markName && Number.isFinite(m.value))
      return hit ? hit.value : null
    },
    name,
    { timeout, polling: 250 },
  )
  const value = (await handle.jsonValue()) as number
  expect(value, `perf mark "${name}" should be finite`).toBeGreaterThanOrEqual(0)
  return value
}

/** Assert the feature did not fall into the DataBoundary query-error state. */
export async function expectNoQueryError(page: Page): Promise<void> {
  await expect(page.getByText('Query failed', { exact: false })).toHaveCount(0)
}

/** Navigate to a data route and wait for its FeaturePage <h1> title to render. */
export async function gotoFeature(page: Page, path: string, title: string | RegExp): Promise<void> {
  await page.goto(path)
  await expect(page.getByRole('heading', { level: 1, name: title })).toBeVisible()
}
