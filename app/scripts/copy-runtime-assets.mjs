// Self-host the DuckDB-Wasm and ONNX Runtime Web binaries into public/ so COEP
// `require-corp` (AD-11) doesn't block them as cross-origin. Idempotent; run via
// the `predev` / `prebuild` npm hooks so a fresh checkout never hits jsDelivr.
import { copyFileSync, mkdirSync, existsSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

const root = join(dirname(fileURLToPath(import.meta.url)), '..')
const node = (...p) => join(root, 'node_modules', ...p)
const pub = (...p) => join(root, 'public', ...p)

// DuckDB-Wasm: only the EH bundle (client.ts pins EH; mvp/coi are never loaded).
const duckdbDist = node('@duckdb', 'duckdb-wasm', 'dist')
const duckdbFiles = [
  'duckdb-eh.wasm', 'duckdb-browser-eh.worker.js',
]

// ONNX Runtime Web: the threaded jsep build (default) + its non-jsep fallback.
const ortDist = node('onnxruntime-web', 'dist')
const ortFiles = [
  'ort-wasm-simd-threaded.jsep.wasm', 'ort-wasm-simd-threaded.jsep.mjs',
  'ort-wasm-simd-threaded.wasm', 'ort-wasm-simd-threaded.mjs',
]

function copyAll(srcDir, files, destDir, label) {
  if (!existsSync(srcDir)) {
    console.warn(`  ⚠️  ${label}: source missing (${srcDir}) run pnpm install`)
    return
  }
  mkdirSync(destDir, { recursive: true })
  for (const f of files) copyFileSync(join(srcDir, f), join(destDir, f))
  console.log(`  ✅  ${label}: ${files.length} files → ${destDir.replace(root + '/', '')}`)
}

copyAll(duckdbDist, duckdbFiles, pub('duckdb'), 'DuckDB-Wasm')
copyAll(ortDist, ortFiles, pub('ort'), 'ONNX Runtime Web')
