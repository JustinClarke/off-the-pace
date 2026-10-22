# CO-21 — Proximity: unmeasured laps read as "no car near"

**Status:** SPEC (nothing run). **Group:** 1 data settled · **Depends on:** none · **Blocker:** none. Raised 2026-10-22 from the transform audit. `CO-18` (retrain) depends on it.

**Sources:** `transform/models/intermediate/int_lap_proximity.sql`, `transform/models/marts/fct_cliff_prediction_features.sql`, `ml/src/schema.py`.

## Problem

`int_lap_proximity.sql` (about lines 443-466) writes the six exposure columns (`share_lap_within_1s/2s/3s`, `time_within_1s`, `share_lap_in_train`, `share_lap_behind_within_1s`) as `COALESCE(x, 0.0)`. A lap with no position telemetry therefore reads as 0.0, "no car near", which is a measurement, not an absence. Audit counts (not re-run): about 1,994 laps; about 1,283 of them training-eligible in `fct_cliff_prediction_features`. FD6 and CO-04 ruled "NULL, not a guess" for the dirty-air block; this block was left as it was.

Folded in: the comment in `fct_cliff_prediction_features.sql` (about lines 403-407) says this block "is not in the ML contract". `ml/src/schema.py` (about lines 198-202) lists these columns in the `proximity` family, so the comment is wrong.

## Method

1. Confirm the counts on a current build (dev is stale until CO-17; say which build).
2. Keep an unmeasured lap NULL (2026-10-23, owner: unmeasured wins over neutralised, as in CO-04 / FD6, so an unmeasured lap is NULL whatever the track status; this supersedes the earlier "neutralised laps stay 0.0". The trace found the 163 affected laps reach no parquet, model feature or app page.). Check every consumer handles NULL (XGBoost reads NULL natively; check the dbt tests and app exports).
3. Correct the stale comment.
4. This moves features the models read: land it before CO-17's rebuild, or re-run that rebuild after it, so CO-18 trains on it.

## Definition of done

Model and comment changed in the working tree; the NULL count matches the unmeasured-lap count on the named build; dbt tests on the touched models pass. Do not commit.
