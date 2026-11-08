// AX-04 seam: stands in for data/manifest.ts when the headless runner loads a feature. Everything
// but the fetch is the real module (path building, version stamping); loadManifest reads the
// scratch export's _manifest.json instead of the CDN.
import { headless } from './adapter'
import type { DataManifest } from '../../../data/manifest'

export * from '../../../data/manifest'

export async function loadManifest(): Promise<DataManifest> {
  return headless().loadManifest()
}

export function peekManifest(): DataManifest | null {
  return headless().peekManifest()
}
