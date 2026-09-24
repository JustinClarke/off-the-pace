# WI-09 — Cleanup bundle: identity, contract text, bronze-scoped low-severity items

**Group:** 08 foundations (low) · **Depends on:** nothing · **Blocker:** none.

**Findings folded in:** F12, F13, F14, F17, F18, F19, F20 (all Low), **F54** (new, Low).

**Reverification:** all CONFIRMED-AS-STATED. No severity disagreements, but two items are worth a
closer read than "Low" implies for how they'll age.

---

## F12 — 2018 fabricated free air

`int_lap_air_state.sql`'s `with_stint` CTE: `COALESCE(a.air_state_dominant, 'free_air')`,
`COALESCE(a.dirty_air_share_lap, 0.0)`; `int_lap_proximity.sql:406-426` same pattern for proximity
shares. Mechanism confirmed live; the 14.9%-vs-5.5% season comparison wasn't independently rerun but
the producing code matches exactly. Fix: T15 (per-season null/zero tolerance in the drift baseline).

## F13 — `race_id` loaded as INTEGER

`SELECT typeof(race_id), race_id FROM raw_dim_events LIMIT 5` → `('INTEGER', 202110)`. Confirmed
`dbt_project.yml` has no `+column_types` override for `raw_dim_events`, while its two siblings
(`seed_manual_lap_exceptions`, `race_to_track`) both explicitly declare `race_id: varchar` — this
seed was simply missed when that pattern was applied elsewhere. Impact confirmed nil (current
consumers — `useRaces.ts`, `fit_compound_cliff.py:136`'s `forced_stop_flag` — are already
unused/dead, not because this bug is harmless, but because nothing live currently depends on it).
**Fix:** trivial one-line addition of the same `+column_types` entry used for its two siblings.

## F14 — three DSQs read as classified finishers

`stg_results.sql`'s `is_dnf` logic requires `TRY_CAST(classifiedposition AS INTEGER) IS NULL`.
Confirmed live: HAM/LEC (2023_18) and RUS (2024_14) all have `status='Disqualified',
is_classified=TRUE, is_dnf=FALSE, dnf_cause=NULL`, while the other 13 DSQs in the window correctly
resolve. **Fix:** route `status = 'Disqualified'` explicitly ahead of the classifiedposition parse —
a one-line CASE addition, no downside.

## F17 — `pu_family`/`driver_number` wrong, but currently unread by anything that computes

`unknown_pu` on 3 of 19 constructors (`Alfa Romeo Racing`, `Kick Sauber`, `Racing Bulls` — all
post-rename entities missing from the hardcoded 16-row `pu_mapping`). `dim_drivers.driver_number` is
a lexicographic `MAX` on a VARCHAR (VER → `'33'`, four years stale even before the string-ordering
bug). `fct_driver_skill_features.sql:153-154` aliases the same column twice as "aero" and "power"
pace indices. **Reverification flag: this is slow rot, not a static harmless bug** — `unknown_pu` is
already ~16% of constructors purely from F1 team renames (a normal cadence), with zero test
asserting coverage. See **F54** below for the concrete guard.

## F18 — 2020_1 lap numbering (bronze)

`stg_laps` caps at lap 68; `stg_race_control`'s CHEQUERED flag is at lap 71; Jolpica pit laps run +4
to +5 vs. `stg_pits`. Both `stg_laps.sql` and `stg_race_control.sql` are direct, uncorrelated
CAST-only passthroughs of bronze columns with no join between them — the disagreement between two
independently-ingested bronze feeds cannot originate in the transform layer, correctly scoped as
bronze per the charter. No fix proposed beyond documenting the impact (single-race distortion of
`lap_number`/`fuel_mass_kg`), which is the right level of effort for a bronze-scoped, single-race
defect.

## F19 — `session_type` declared, absent — and the doc is worse than "stale"

`stg_laps.sql` has zero references to `session_type` anywhere (no read, no filter, no COALESCE). Yet
`src_formula1.yml:16-19`'s column description doesn't just go silent — it **affirmatively asserts a
safeguard that was never built**: "Existing race files have no session_type column and read NULL
(coalesced to 'R' in stg_laps)." That coalesce does not exist anywhere in the code. This is worse
than silence: a future engineer reading the yml before item `02f` (FP1/2/3 ingestion) lands would
reasonably assume a guard already exists and skip building one. **Currently structurally clean**
(173 race-depth files, 173 `session=Q` directories, `lap_id` unique, laps contiguous — confirmed) but
severity rises to critical the day `02f` reopens.

## F20 — doc drift (7 confirmed instances)

`fct_cliff_prediction_features.sql:1-4` still names `next_lap_degradation_jump_detrended_s` PRIMARY
(actual target: `next_5_lap_cumulative_jump_s`, per `schema.py:283`). `:755` claims "42nd feature"
against the card's `feature_count: 32`. `:774-776` and `:834-840` call proximity and qualifying
features "not yet in the ML feature contract" — both have been live in `model_card.yml`'s
`features.columns` list for several versions. `features.py:598`'s docstring claims
`int_field_pace_curve` feeds `push_residual` — confirmed false by direct read of
`int_lap_thermal_proxy.sql`, which uses its own trailing median with zero reference to the field
curve. `reference/schema.yml:138`'s `pu_family` claim is false per F17. Each individually low-cost;
seven independently-confirmed instances in one read is a systemic pattern — there's a doc-freshness
CI gate for the model card (`gen_ml_reference.py --check`) but nothing equivalent for SQL header
prose, which is why this class of comment rots by design (nothing forces it to be revisited when the
thing it describes changes).

## F54 (new) — `dim_constructors.pu_mapping` has no completeness test

Full write-up in `NEW-FINDINGS.md`. The concrete guard F17's slow-rot flag needs: a warn-level dbt
test asserting `unknown_pu` share doesn't increase build-over-build, or (better, matching F17's own
recommended ruling) keying `pu_family` on the constructor *entity* using the same alias pattern
`macros/circuit_id_from_name.sql` already uses for circuits — rename-proof rather than
catch-after-the-fact.

## Method

Work these independently; none block each other or anything else in `_fixes/`.

1. F8/F13: one-line seed/type fixes.
2. F14: one CASE branch in `stg_results.sql`.
3. F17/F54: either the coverage test (cheap) or the entity-keyed rewrite (durable) — recommend the
   entity-keyed rewrite since the pattern already exists in-tree for circuits.
4. F18: document only, per charter (bronze-scoped).
5. F19: correct the yml to state what the code does today (nothing); add a dbt source test that
   fails if any race-depth glob file contains a non-'R'/non-NULL `session_type` — cheap insurance
   ahead of `02f`.
6. F20: delete "not yet in X" prose the moment X happens, going forward; fix the 7 confirmed
   instances now.

## Acceptance

Each item's specific claim (a comment, a type, a classification rule) matches what the code actually
does, verified by the query or grep the corresponding audit finding already specifies.

## Tests to add

T13 (F14), new source test for F19 (no non-R/NULL `session_type` at race depth), `assert_pu_family_
coverage` (F54, warn-level).

## Definition of done

`verify_findings.py`'s F12, F13, F14, F17, F18, F19, F20 checks flip to CLEARED (F18 stays PRESENT
and documented, since the fix is out of scope per the charter); F54's new test is wired in.
