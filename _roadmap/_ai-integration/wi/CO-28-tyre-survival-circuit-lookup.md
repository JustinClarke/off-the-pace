# CO-28 — Tyre Cliff Survival page never finds its compound profile

**Status:** SPEC (nothing run). **Group:** 1 data settled · **Depends on:** none · **Blocker:** none. Raised 2026-10-23 from the CO-26 parquet trace.

**Sources:** `app/src/features/tyre-cliff-survival/page.tsx`, `app/src/features/tyre-cliff-survival/transform.test.ts`, `app/src/features/degradation-simulator/queries.ts`, `app/src/data/hooks/useRaces.ts`, `transform/models/reference/dim_events.sql`, `transform/models/marts/schema.yml`.

## Problem

`page.tsx:93` does `profiles.find(p => p.circuit_key === raceId ...)`. `dim_compounds_season.circuit_key` holds a circuit name (`australian_grand_prix`); `raceId` from the URL is a race id (`2023_1`). On the published data 0 of 512 race/compound pairs match; 499 would through `race_to_track`. So `profile` is always null: the "Model onset / Severity / Wear rate" chips (`page.tsx:161-170`) never render, and the fit date and data window fall back to defaults. The test fixture (`transform.test.ts:116`) uses `circuit_key: '2023_1'`, which hides it.

Found on the same trace, same family of mix-up:

- `app/src/data/hooks/useRaces.ts` queries `season` and `round` on `dim_events`, which has neither; nothing imports it.
- `dim_events`' header and schema text say `fct_lap_residuals` and `int_lap_anomaly_flags` consume it; neither does.

## Method

1. Resolve the race's circuit through `race_to_track.track_id`, as `degradation-simulator/queries.ts:288` does, then match the profile on that.
2. Fix the test fixture to use a real circuit name, and add a test that fails on the old lookup.
3. Delete `useRaces.ts` (dead and broken) and correct the `dim_events` consumer text.

## Definition of done

The chips render on a race page for every race/compound with a profile (spot-check three races in the running app); the new test fails on the old code and passes on the new. Do not commit.
