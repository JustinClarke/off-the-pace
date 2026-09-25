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

**Build finding (2026-09-25): F12 was not fixed here, and the text above cannot deliver its own
definition of done.** T15 is a guard, and `WI-07` owns it (its "T15 (baseline re-snapshot)"); it
cannot flip the F12 check. That check measures the share of 2018 training-eligible rows whose
`gap_ahead_min_s` is NULL (9.18% in 2018 against 0.00-0.04% in every other season on the
2026-09-25 dev build, so the check reads 0.0917), a property of which laps have telemetry that no
edit to the COALESCE changes. Removing the fabrication itself (NULL instead of `'free_air'` / `0.0` on a lap
with no telemetry) puts NULL into `dirty_air_share_lap`, which feeds the dirty-air tax and so the
residual and both labels: it belongs with `WI-01` / `WI-15a`, not in a cleanup bundle. Left PRESENT
pending a ruling on what "cleared" means; see the build's open question.

## F13 — `race_id` loaded as INTEGER

`SELECT typeof(race_id), race_id FROM raw_dim_events LIMIT 5` → `('INTEGER', 202110)`. Confirmed
`dbt_project.yml` has no `+column_types` override for `raw_dim_events`, while its two siblings
(`seed_manual_lap_exceptions`, `race_to_track`) both explicitly declare `race_id: varchar` — this
seed was simply missed when that pattern was applied elsewhere. Impact confirmed nil (current
consumers — `useRaces.ts`, `fit_compound_cliff.py:136`'s `forced_stop_flag` — are already
unused/dead, not because this bug is harmless, but because nothing live currently depends on it).
**Fix:** trivial one-line addition of the same `+column_types` entry used for its two siblings.

*Build note:* a `+column_types` change does not retype an existing seed table, so the dev
warehouse needed `dbt seed --select raw_dim_events --full-refresh` and a rebuild of `stg_events` /
`dim_events` before the check flipped. With the id now matching, `fit_compound_cliff.py`'s
`forced_stop_flag` can be TRUE (VER's two 2021_14 stints); nothing reads the `forced_stop` key
(`grep` over `transform/tasks`), so the seed is unaffected. Added a `dbt_expectations` regex test on
`dim_events.race_id` (it fails 6 rows on the pre-fix build).

## F14 — three DSQs read as classified finishers

`stg_results.sql`'s `is_dnf` logic requires `TRY_CAST(classifiedposition AS INTEGER) IS NULL`.
Confirmed live: HAM/LEC (2023_18) and RUS (2024_14) all have `status='Disqualified',
is_classified=TRUE, is_dnf=FALSE, dnf_cause=NULL`, while the other 13 DSQs in the window correctly
resolve. **Fix:** route `status = 'Disqualified'` explicitly ahead of the classifiedposition parse —
a one-line CASE addition, no downside.

*Build note:* done as one parsed rank (a `ranked` CTE) that `is_classified`, `is_dnf` and
`dnf_cause` all read, rather than a CASE in each; exactly the 3 rows change. T13 is at default
(error) severity, not the audit's warn: bronze can no longer trip it, only a change to the flags
can. `fct_ghost_race_finish` is a table, so on the dev warehouse it stays stale for those 3 rows
(finish position, `actual_is_dnf`) until rebuilt.

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

*Build note:* documented in the `stg_laps` model description (`transform/models/staging/schema.yml`).
Re-checked on the dev build: bronze laps end at 68, race control's CHEQUERED flag is on 71,
`race_scheduled_laps` says 71, and no other race with a chequered flag on record ends short of it.
The Jolpica +4/+5 pit-lap offset is the audit's figure and was not re-run.

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

Full write-up in `../reference/new-findings.md`. The concrete guard F17's slow-rot flag needs: a warn-level dbt
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
   *Build correction:* the circuit precedent does not transfer as stated.
   `macros/circuit_id_from_name.sql` slugifies the circuit's display name, which is stable across
   event renames; constructors have no stable name to slugify (`Sauber` → `Alfa Romeo Racing` →
   `Kick Sauber` share nothing), so an entity key needs a new alias table and decisions about entity
   granularity and whether `pu_family` is per season. **Done here:** the three missing rows added
   to `pu_mapping` (clears the F17 check) plus `assert_pu_family_coverage` (warn). **Not done:** the
   entity-keyed rewrite, held as an open question. Also fixed under F17, from the audit's own
   remediation list though not in this Method: `dim_drivers.driver_number` (VER, DEV and LAW were
   stale). Not touched: the duplicate `constructor_power/aero_pace_index_final` columns, which
   need a contract decision (drop, or relabel).
4. F18: document only, per charter (bronze-scoped).
5. F19: correct the yml to state what the code does today (nothing); add a dbt source test that
   fails if any race-depth glob file contains a non-'R'/non-NULL `session_type` — cheap insurance
   ahead of `02f`.
   *Build note:* built as a singular test (`assert_raw_laps_race_depth_is_race_only.sql`), not a
   column-level source test: race files have no `session_type` column, so a generic test on it
   fails to bind. It reads the raw files with `union_by_name` so a column in any file is seen. The
   yml fix removes the `session_type` column from `raw_laps` (which is what the audit's check
   looks for) and states the directory-depth rule in the table description.
6. F20: delete "not yet in X" prose the moment X happens, going forward; fix the 7 confirmed
   instances now.
   *Build note:* the seven are the six named in the F20 section above plus the model-card summary
   (`ml/src/card.py:241-242`, `ml/model_card.yml:6-7`: "powertrain, weather" families dropped in
   Phase 9, and "Trained on 2018–2024"). The first six are fixed. The card summary is not: its
   second half is `WI-03`'s (it names `card.py:242` and `model_card.yml:7` as stale holdout prose,
   and the true wording depends on `FD4`), and fixing it means regenerating four checked-in
   copies (`ml/model_card.yml`, `ml/models/model_card.json`, `app/public/models/model_card.json`,
   `docs/reference/ml/degradation-model.mdx`). Held as an open question. The same pass found and
   fixed three more of the same class in `fct_cliff_prediction_features.sql`: two more "PRIMARY"
   claims for the detrended 1-lap target (the C1 comment and the final SELECT) and "02b's seven ...
   hold until their arms rule" in the 02d block.

## Acceptance

Each item's specific claim (a comment, a type, a classification rule) matches what the code actually
does, verified by the query or grep the corresponding audit finding already specifies.

## Tests to add

T13 (F14), new source test for F19 (no non-R/NULL `session_type` at race depth), `assert_pu_family_
coverage` (F54, warn-level).

## Definition of done

`verify_findings.py`'s F13, F14, F17, F19, F20 checks flip to CLEARED (F18 stays PRESENT and
documented, since the fix is out of scope per the charter); F54's new test is wired in.

**Split (2026-09-25):** F12 is carried by `WI-09b` (blocked on `FD6`, the ruling above), and F20's
seventh instance (the model-card summary) moved to `WI-03`. `WI-09` itself is complete against this
definition of done.
