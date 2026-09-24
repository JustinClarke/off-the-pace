# WI-04 — Browser inference per-model feature vectors

**Group:** 06 publication / app · **Depends on:** nothing · **Blocker:** none.

**Findings folded in:** F3 (High, shipped surface).

**Reverification:** CONFIRMED-AS-STATED. Reconfirmed the manifest shape and the throw path directly;
no commits have touched `app/src/ml/` since the audit ran (last relevant commit predates it).

---

## The defect, reconfirmed

`app/public/models/manifest.json` (v14, identical to `ml/models/manifest.json`) has an `input` object
with keys `{tensor_name, dtype, feature_union, per_model_feature_order, encoding}`. There is **no**
`n_features` and **no** `feature_order` at the top level — those moved to per-model entries under
`models[]` when v13 made the contract per-model (5 widths: 32/32/32/39/32).

`app/src/ml/featureVector.ts:57-58,67,70` and `app/src/ml/infer.ts:101-105` still dereference the
old top-level keys. Reproduced directly (plain Node, no app code executed):
`buildFeatureVector` throws `TypeError: Cannot read properties of undefined (reading 'length')`.
`featureVector.test.ts:79-80` still asserts `n_features == 32` against the real shipped manifest and
would fail if run.

**Even a naive fix wouldn't be enough:** `predictLaps` currently builds **one** shared feature matrix
and feeds it to all five models — but the five models now have two different widths (32 and 39). The
fix has to build one vector per model, not just read a different manifest key.

## Fix assessment (from reverification)

The report's fix ("read `models[i].feature_order`") is correct but easy to under-implement as "read
from a different path, same single-vector logic." The actual requirement is **one vector per model**,
built from that model's own `feature_order`, since widths genuinely differ across the five model
families in the current contract (`cliff_classifier` = 39, the other four = 32).

No app-side CI currently catches this because no app PR has touched this path since the manifest
changed (2026-09-21/23) — `featureVector.test.ts` exists but wasn't run against the new manifest as
part of that change.

## Method

1. Rewrite `buildFeatureVector` to take a model identifier and read that model's
   `feature_order`/width from `models[i]`, not from a shared top-level `input.n_features`.
2. Rewrite `predictLaps`/`infer.ts` to build a distinct vector per model rather than one shared
   matrix.
3. Update `featureVector.test.ts` to assert against the real per-model widths (32/32/32/39/32), not
   the retired top-level keys.
4. Add T7: a Node/vitest test that runs `buildFeatureVector` per model against the actual shipped
   manifest in CI, so any future manifest shape change fails the build immediately instead of
   silently shipping a broken Degradation Simulator.

## Acceptance

- The Degradation Simulator and `verifyParity`/`make app-parity` run without throwing against the
  current shipped manifest.
- Each of the five models is scored with a vector built from its own declared `feature_order` and
  width.
- A manifest-shape regression (e.g. the next contract change) fails CI via T7 rather than shipping
  silently, closing the gap this defect exploited.

## Tests to add

T7.

## Definition of done

`make app-parity` passes against the current shipped manifest; T7 is wired into app CI;
`verify_findings.py`'s F3 check flips to CLEARED.

**CDN check (done 2026-09-24):** `https://storage.googleapis.com/off-the-pace-cdn/models/manifest.json`
(`MODELS_BASE`) currently serves **v11** with the old top-level `input.n_features` / `input.feature_order`
shape. Production works today; the defect is latent. **This fix must land before the v14 manifest is
published to the CDN, not after** — publishing first would make the Degradation Simulator throw
`TypeError` for every user. Also confirmed locally: 3 of 14 tests in `featureVector.test.ts` fail
against the shipped v14 manifest today.
