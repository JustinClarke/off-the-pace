# CO-11 — Relabel the experimental chance number

**Status:** SPEC (nothing run). **Group:** D carry-over · **Depends on:** none · **Blocker:** none.

**Sources:** `app/src/ml/flagChance.ts`, `app/src/features/degradation-simulator/DegradationSimulatorChart.tsx`, `app/src/features/degradation-simulator/methodology.tsx`, `docs/app/degradation-simulator.mdx`, `app/public/models/flag_chance_lookup.json`.

## Why

The shipped lookup matches an expanding-window refit of the v14 configuration exactly (`CO-08` / the 2026-10-17 rebuild check). It was not computed from the served v14 booster, which was trained on 2018–2025. Page text and the lookup's `model_version` say `v14`, which overstates it.

## Method

1. Change the page label and methodology text to "refit of the v14 configuration, expanding-window folds, 2018–2024".
2. Change the lookup's `model_version` stamp to match. Do not change the lookup's values; its sha256 must stay `5339d041…fefe1` unless the owner rules otherwise.
3. Keep the 2025 figures and the "provisional until 2026" note.

## Definition of done

Page and methodology text say refit, not v14; lookup stamp updated; the sha256 of the values is recorded; app tests pass with counts reported.
