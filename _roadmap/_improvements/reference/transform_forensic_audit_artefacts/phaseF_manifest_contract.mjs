// Replicates the exact field reads app/src/ml/featureVector.ts:57-58,67 and infer.ts:101 perform,
// against the SHIPPED app/public/models/manifest.json. No app code is executed.
import { readFileSync } from 'node:fs'
const m = JSON.parse(readFileSync('/Users/justin/github/off-the-pace/app/public/models/manifest.json', 'utf8'))
console.log('manifest model_version:', m.model_version)
console.log('input keys:', Object.keys(m.input))
console.log('input.n_features   ->', m.input.n_features)
console.log('input.feature_order ->', m.input.feature_order)
try { const vec = new Float32Array(m.input.n_features); console.log('new Float32Array(n_features).length =', vec.length);
      for (let i = 0; i < m.input.feature_order.length; i++) {} }
catch (e) { console.log('buildFeatureVector would throw:', e.constructor.name, e.message) }
console.log('per-model widths:', m.models.map(x => `${x.name}:${x.n_features}`).join(', '))
