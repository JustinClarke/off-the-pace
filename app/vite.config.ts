import { defineConfig, Plugin } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'
import fs from 'fs'

// onnxruntime-web (1.26) loads its threaded proxy worker by calling import() on the self-hosted
// /ort/*.mjs assets. Vite's dev server intercepts any import() of a /public .mjs, appends ?import,
// runs it through import-analysis, and 500s ("should not be imported from source code"). The
// production build is unaffected (assets are copied and fetched as-is). This dev-only middleware
// serves /ort/*.mjs as raw JS, short-circuiting import-analysis so the worker loads.
// See _roadmap/_issue_logs/infrastructure/high/onnxruntime_web_vite_dev_mjs_import.md.
function serveOrtMjsRaw(): Plugin {
  return {
    name: 'serve-ort-mjs-raw',
    apply: 'serve',
    configureServer(server) {
      server.middlewares.use((req, res, next) => {
        const url = req.url ?? ''
        if (url.startsWith('/ort/') && url.includes('.mjs')) {
          const rel = url.split('?')[0]
          const file = path.join(server.config.root, 'public', rel)
          if (fs.existsSync(file)) {
            res.setHeader('Content-Type', 'text/javascript')
            // The page is cross-origin-isolated (COEP require-corp); the worker module must
            // carry CORP or COEP blocks it (ERR_BLOCKED_BY_RESPONSE).
            res.setHeader('Cross-Origin-Resource-Policy', 'same-origin')
            res.setHeader('Cross-Origin-Embedder-Policy', 'require-corp')
            res.end(fs.readFileSync(file))
            return
          }
        }
        next()
      })
    },
  }
}

function injectCoopCoepHeaders(): Plugin {
  return {
    name: 'inject-coop-coep-headers',
    apply: 'serve',
    configureServer(server) {
      server.middlewares.use((_req, res, next) => {
        res.setHeader('Cross-Origin-Opener-Policy', 'same-origin')
        res.setHeader('Cross-Origin-Embedder-Policy', 'require-corp')
        next()
      })
    },
  }
}

export default defineConfig({
  plugins: [injectCoopCoepHeaders(), serveOrtMjsRaw(), react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  optimizeDeps: {
    // onnxruntime-web dynamically imports its threaded proxy (.jsep.mjs) from the self-hosted
    // /ort/ assets at runtime; excluding it from dep pre-bundling stops Vite's dev server from
    // trying to resolve that /public .mjs as a source module (which 500s). See
    // _roadmap/_issue_logs/infrastructure/high/onnxruntime_web_vite_dev_mjs_import.md.
    exclude: ['@duckdb/duckdb-wasm', 'onnxruntime-web'],
  },
  server: {
    headers: {
      'Cross-Origin-Opener-Policy': 'same-origin',
      'Cross-Origin-Embedder-Policy': 'require-corp',
    },
  },
  worker: {
    format: 'es',
  },
})
