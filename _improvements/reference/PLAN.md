# Compounds Layer — Consolidated Plan

Supersedes `compounds_logic.md`, `compounds_plan.md`, `downstream_audit.md`, and
`chat_history_compounds_architecture.md` (folded in below; those four files can be
deleted once this is reviewed). Re-validated against the working tree on 2026-07-29 —
findings below still hold; changes since 2026-07-19 are called out where relevant.

**Verdict: worth implementing, Phases A–C only.** The SC-hole is a real, verified bug
with a large blast radius and a cheap fix; the bronze pickups are trivial-to-moderate
wins already staged in the warehouse. Phase D and the latent-state research agenda
(original Parts 5/7) are explicitly **not** scoped for implementation — see "Excluded"
below.

---

## Phase 0 — Prerequisite: land the in-flight reconstruction first

Do this before touching anything in Phase A. It is not part of the compounds work
itself, but it shares files with it and is higher-priority.

`CI_FAILURES.md` (repo root) documents a separate, still-open incident: Jul 6–10
transform-layer work (on `int_driver_circuit_era_affinity`, `mart_corner_skill_driver`,
and two cliff-seed bugs in `fit_compound_cliff.py`/`survival.py`) was lost to an
uncommitted `git restore .`, partially reconstructed from `dev.duckdb` + 14 surviving
`assert_*.sql` tests, and left **uncommitted since 2026-07-17** with steps A–E
("regenerate + promote the seed", "confirm tests pass", "re-run the byte-stability
oracle", "regenerate docs") still open. As of this consolidation (2026-07-29, 12 days
later), none of those steps have been done — the seed CSV is unchanged and
`seeds/_pending/` is empty.

**Why this blocks Phase A:** `fit_compound_cliff.py`/`survival.py` are exactly the
files Phase A4 below also touches (cliff-seed refit after the geometry fix), and the
14 `assert_*.sql` files are the same gate this plan relies on in Phase A's Gates
section. Starting Phase A on top of an unfinished, unverified reconstruction makes it
hard to tell which change caused which test result. Separately: this working tree has
now had two rounds of multi-day uncommitted transform-layer work — finish and commit
the first round before starting a second, rather than repeating the exact failure mode
that produced `CI_FAILURES.md` in the first place.

**Action:** work `CI_FAILURES.md` steps A–E to green, get user sign-off, commit. Then
start Phase A below. (Two separate seed regenerations — one now for the severity-bound
bug, one after Phase A4 for the geometry fix — is expected and fine; they're
independent bugs found at different times.)

Housekeeping while there: `jcdlac` (0-byte stray file, root, dated Jul 11, unrelated to
either effort) and `patch_compounds.py` (a one-off script that already did its job
renumbering `compounds_logic.md` on Jul 18 — now dead weight) are both untracked
clutter. Worth deleting, but confirm with the user first since neither was created this
session.

---

## Scope decision

- **Implement:** Phase A (SC-hole fix across all 13 consumers + the solver), Phase B
  (bronze pickups), Phase C (normalize-don't-discard).
- **Exclude:** Phase D items stay deferred until after C ships, revisited only if
  warranted by what C's acceptance test shows.
- **Exclude entirely, not just defer:** the original document's Parts 5 and 7 — a
  continuous-time latent-state SDE over tyre health/thermal/pressure/fuel, hypergraph
  spatio-temporal propagation, unsupervised track-segment clustering, and a
  publishable-identifiability research claim. This is a research agenda, not an
  engineering task: no defined acceptance criteria, no scoped deliverable, and it
  depends on an identifiability question (Phase D's last bullet) that hasn't been
  checked yet. If that spike ever shows the two-channel EWMA state correlates with
  observed cliff timing, it's worth re-opening as its own proposal then — not before.

---

## Implementation Checklist (live — update as you go)

Master tracker for this plan. Check items off as they land; add a dated entry to
**Checkpoint** (bottom of file) at each phase boundary, and keep this list's checkboxes
in sync with reality — this is the resumption point if a session ends mid-phase, not
just a record. Phase 0's day-to-day detail (what's been tried, exact verified commands)
stays in `CI_FAILURES.md`'s own session log; this list only tracks phase-level status.

### Phase 0 — prerequisite (blocks Phase A)
- [x] Local dev environment repaired: `.venv` rebuilt on Homebrew python@3.14 (python@3.12
      was removed by Homebrew); `mashumaro` upgraded to 3.22 locally, `libomp` installed
      via brew (neither touches tracked files — CI pins 3.11/3.12 and is unaffected).
      Verified via real dbt builds against CI fixtures.
- [x] Step A — regenerate + promote `compound_cliff_params` seed. 403 rows, 0 over the
      1.5 bound, 0 fallback rows under 8 stints. Promoted; prior seed archived.
- [x] Step B — full `dbt build` on CI fixtures clean: **PASS=538 ERROR=0 SKIP=0
      TOTAL=541**. Along the way found and fixed a **third lost model** session 2
      missed: `fct_ghost_car_pace` / `fct_ghost_race_finish` were missing fuel-adjusted
      residual-pace columns, silently broken because session 2 never ran the full
      suite. Bit-exact reconstruction verified against `dev.duckdb` (0 mismatches /
      1.29M + 27.7K rows) — see `CI_FAILURES.md` session 3 for detail. All 14 `assert_*`
      tests pass, including the previously-failing `assert_ghost_self_scenario_rank`.
- [x] Step C — byte-stability oracle re-checked; pre-existing 6-model drift confirmed
      still the exact same 6 (unrelated, pre-existing), re-snapshotted. Now
      `OK: all 7 fct_* models byte-stable`.
- [x] Step D — docs regenerated; `transform_docs_facts` passes clean.
- [x] Step E — user confirmed; `jcdlac` + `patch_compounds.py` deleted.
- [x] User sign-off on Phase 0 diff
- [x] Phase 0 committed

### Phase A — SC-hole fix (do not start until Phase 0 is committed)
- [x] A1 — `int_stint_geometry`: drop `is_valid_lap` filter, carry validity flags,
      add `valid_lap_in_stint` + `stint_length_valid`
- [x] A2 — per-consumer fixes (13 models, table in Phase A section is the checklist):
  - [x] `int_compound_cliff_predicted`
  - [x] `int_lap_fuel_state` — audited, no change needed (self-filters)
  - [x] `int_lap_air_state` (pairs with A3 below)
  - [x] `int_lap_thermal_proxy` — lag runs over the full sequence, but final SELECT
        deliberately stays unfiltered (not "filter at final SELECT" as originally
        drafted) — see Checkpoint note, `assert_no_future_leakage` /
        `assert_stint_boundary_integrity` both read this model directly and require it
  - [x] `int_dirty_air_tax_component`
  - [x] `int_constructor_deg_sensitivity`
  - [x] `int_corner_skill_residuals`
  - [x] `int_field_pace_curve`
  - [x] `int_constructor_structural_pace` — audited, no change needed (self-filters)
  - [x] `int_synthetic_teammate`
  - [x] `int_lap_residual_decomposed`
  - [x] `int_pit_strategy_value`
  - [x] `fct_stint_features`
- [x] A3 — SC bunching trap: zero `dirty_air_share_lap` + `dirty_air_intensity` on
      SC/VSC laps in `int_lap_air_state`, let EWMA decay through them
- [x] A4 — `fit_compound_cliff.py`/`survival.py` solver alignment (keyed on
      `age_in_stint`, not `lap_in_stint`) + cliff-seed refit (2nd refit, independent
      of Phase 0's; promoted)
- [x] Gate: all 43 `assert_*.sql` pass (470 data tests, `PASS=544 ERROR=0 SKIP=0`);
      `validate_gate.py` cliff-onset Spearman improved 0.648 → 0.680 (no regression)
- [x] User sign-off on Phase A diff
- [x] Phase A committed

### Phase B — bronze pickups (independent, parallelizable after A)
- [x] B1 — `FreshTyre` → solver baseline-fit filter
- [x] B2 — status-aware censoring (Puncture/Wheel → failure; mechanical → censor)
- [x] B3 — wind speed as scalar covariate
- [x] B4 — `time_in_dirty_air_s` upgrade in `int_lap_air_state`
- [x] B5 — new `int_track_geometry` model (gradient + curvature from X/Y/Z)
- [x] User sign-off on Phase B diff
- [x] Phase B committed (`9d6b7d4`)

### Phase C — normalize, don't discard (depends on B4)
- [x] `normalized_pace_s` computed; wear/cliff fitting switched to green-flag +
      normalized pace
- [x] Ratings/residual chain confirmed unchanged (still valid-lap gated)
- [~] Acceptance test: **half passes.** Per-stint wear-slope residual σ drops
      0.4139 → 0.3943 (−4.7%, 61.2% of stints improved) — PASS, decisively.
      Gate 4.3 Spearman 0.599 → 0.587 (−0.012), top-3 0.507 → 0.486 — FAIL,
      narrowly. Awaiting user call on whether the σ gain justifies the
      finish-order cost. See Checkpoint below.
- [x] User sign-off on Phase C diff
- [x] Phase C committed (`bd0ce6b`, 2026-08-03) — user shipped it, accepting the
      half-passing acceptance test (σ gain kept, finish-order cost accepted)

---

## Warehouse-validated findings (evidence base)

Measured directly against `data/bronze/` and `data/dev.duckdb` on 2026-07-19; spot-checked
still current on 2026-07-29 (`int_stint_geometry.sql` unmodified since Jun 24).

| Claim | Verified? | Measured reality |
| :--- | :--- | :--- |
| SC/VSC laps deleted pre-partitioning | ✅ | `int_stint_geometry` filters `is_valid_lap` at line 9; 24,449 / 162,729 laps (15%) dropped |
| SC hole affects thermal windows | ✅ **worse than stated** | 46.7% of stints (3,894 / 8,333) contain ≥1 SC/VSC lap |
| `FreshTyre` unused | ✅ | 0% null in bronze, 21–28% of laps are scrubbed; staged as `is_fresh_tyre` but zero downstream references |
| Wind "completely ignored" | ⚠️ partly | Already staged per-lap in `stg_weather` (`wind_speed_ms`, `wind_direction`); zero references downstream of staging |
| `Status` not used for censoring | ✅ | `forced_stop_flag` = binary DNF via `stg_events`; `stg_results.status` already stages the full string. Tyre-failure tail is tiny: Puncture=6, Wheel=7 across 7 seasons |
| `DistanceToDriverAhead` dropped in staging | ⚠️ **stale claim** | Dropped from `stg_telemetry`, but `int_lap_air_state` already reads it at 10Hz directly from bronze — per-sector median gap + surface/bulk EWMA (α=0.6/0.25) already exist |
| X/Y/Z discarded | ✅ | Present in bronze telemetry (~0% null, all 7 seasons, ~119M rows); unused everywhere |
| Blast radius = 5 models | ❌ **understated** | 13 SQL models consume `int_stint_geometry`, plus `fit_compound_cliff.py` (which re-joins `stg_laps` and re-filters SC/pit itself) |

Data quality greenlights: `DistanceToDriverAhead` only ~5% null (uniform across
2018–2024); throttle/speed 0% null; `FreshTyre` 0% null. `telemetry_full/` and
`pos_data/` bronze dirs are **empty** — X/Y/Z live in the main `telemetry` table.
Quali laps exist in bronze (`session=Q` subdirs) — relevant for scrub history later.

---

## Phase A — The SC-Hole Fix (foundation; everything else keys off this)

**A1. `int_stint_geometry` carries all laps.**
- Remove the `WHERE is_valid_lap = TRUE` filter.
- Carry through flags: `is_valid_lap`, `is_pit_lap`, `is_safety_car_lap`, `is_vsc_lap`.
- `lap_in_stint` stays chronological (now includes invalid laps).
- Add `valid_lap_in_stint` (ROW_NUMBER over valid laps only) so consumers that
  keyed ordinal semantics on the old compressed sequence can migrate explicitly.
- Add `stint_length_valid` alongside `stint_length_actual` (which becomes total laps).

**A2. Per-consumer audit.** Default rule: physics/window models (`int_lap_air_state`,
`int_lap_thermal_proxy`) consume the full chronological sequence so their `LAG`/EWMA
math decays correctly across SC/pit gaps; pace/regression models add an explicit
`is_valid_lap` (or `valid_lap_in_stint`) filter at their input CTE so SC/pit times never
pollute a fitted baseline. Full per-model disposition, all 13 consumers + the solver:

| Model | Impact | Correction |
| :--- | :--- | :--- |
| `int_compound_cliff_predicted` | Medium | Add `WHERE is_valid_lap = TRUE` when joining to `geom`, so pace curves are only evaluated for valid laps — otherwise it outputs expected paces for SC/pit laps. |
| `int_lap_fuel_state` | **None** | Already inner-joins `laps` on `is_valid_lap = TRUE`; self-filters. `lap_number` (absolute race lap) is correctly used for fuel-burn — cars burn fuel during SC laps too. |
| `int_lap_air_state` | **High** | Primary beneficiary. Let the EWMA decay run over the full chronological sequence; separately, zero `dirty_air_intensity` on SC/VSC laps (field bunches to <1s gaps at SC speed, which would otherwise spike the intensity on exactly the laps where tyres are cooling — see A3). |
| `int_lap_thermal_proxy` | **High** | Currently filters to `is_valid_lap = TRUE` *before* the `LAG` window, so it treats the lap before/after an SC as adjacent. Run the lag over the full sequence (invalid laps naturally contribute ~zero push-residual). **Deviation from original draft:** do *not* filter to valid laps at the final SELECT — `assert_no_future_leakage` and `assert_stint_boundary_integrity` both re-derive the EWMA directly from this model's own output rows (including `lap_in_stint = 1`, which is always invalid — pit-out or race-lap-1), so post-hoc filtering breaks the self-check and silently drops the lap-1 boundary case those tests exist to guard. Leave the output unfiltered (mirrors `int_lap_air_state`); downstream consumers already key off `int_lap_residual_decomposed` (valid-only), so the extra rows are harmless. |
| `int_dirty_air_tax_component` | **High** | Currently filters to valid laps before lagging `dirty_air_share_lap` by 1, so the first valid lap after an SC lags back to the last *valid* (pre-SC) lap and wrongly gets a high traffic penalty. Keep invalid laps in the lag step — the first post-SC lap will then correctly lag to the SC lap itself (`dirty_air_share_lap = 0`). |
| `int_constructor_deg_sensitivity` | Medium | Filter is currently chronological `lap_in_stint > 1` (meant to drop the out-lap). Switch to `valid_lap_in_stint > 1` so it reliably drops the first *valid* lap regardless of where SC laps fall in the sequence. |
| `int_corner_skill_residuals` | Medium | Inner-joins to stint geometry for lap keys with no validity filter today. Add explicit `WHERE is_valid_lap = TRUE` in the `lap_keys` CTE, or SC/pit braking-and-speed metrics pollute the 5-lap windowed field medians. |
| `int_field_pace_curve` | Medium | Currently filters out-laps/in-laps via chronological `lap_in_stint > 1 AND lap_in_stint < stint_length_actual - 1`. Switch both sides to `valid_lap_in_stint > 1 AND valid_lap_in_stint < stint_length_valid - 1`, or an SC late in a stint miscounts which lap is the in-lap. |
| `int_constructor_structural_pace` | **None** | Inner-joins to `int_lap_fuel_state` (already valid-only) keyed on `lap_id`; `lap_in_stint` from `geom` is carried through as an output column only, never used as a window/filter boundary. Self-filters the same way `int_lap_fuel_state` does. |
| `int_synthetic_teammate` | Low | `strategic_divergence_flag` compares `ABS(tm_lap_in_stint - ego_lap_in_stint) > 3`. If one teammate hits SC laps the other doesn't, chronological indices diverge without a real strategy difference. Compare `valid_lap_in_stint` (or `age_in_stint`) instead. |
| `int_lap_residual_decomposed` | Medium | Not broken directly, but it's the carrier: downstream models query it for stint indices. Carry `valid_lap_in_stint` and `stint_length_valid` through its final SELECT so nothing downstream needs to re-join `int_stint_geometry` directly. |
| `int_pit_strategy_value` | Medium | Uses `MAX(lap_in_stint)` as `stint_length_laps`. Switch to `stint_length_valid`, or SC laps inflate the counted stint duration used in strategy simulation. |
| `fct_stint_features` | **High** | Two breaks: (1) `QUALIFY ... ORDER BY lap_in_stint DESC LIMIT 1` picks the last *chronological* lap for `cumulative_thermal_load_end`, which is almost always the pit-in lap (invalid, no thermal-proxy entry) → NULL for nearly every stint. Order by `valid_lap_in_stint DESC` instead (or filter `is_valid_lap = TRUE` first). (2) The trailing-3-lap OLS pace-falloff slope must regress on `valid_lap_in_stint`, not chronological `lap_in_stint`, or an SC gap distorts the wear gradient. |
| `fit_compound_cliff.py` (offline solver) | Medium (A4) | Own SC/pit filters stay as-is, but `lap_in_stint` semantics change underneath it. Wear-gradient windows (laps 3 → onset−2) and the trailing-median cliff detector should key on `age_in_stint` (tyre_life, already continuous across SC laps) or `valid_lap_in_stint`, decided per function. Refit cliff seeds after. |

**A3. SC bunching trap in `int_lap_air_state`** (not obvious from the raw bug report):
under SC the field bunches to <1s gaps, so `dirty_air_intensity` would *spike* on
exactly the laps where tyres are cooling. The fix must:
- zero `dirty_air_intensity` on SC/VSC laps (no aero load at SC speeds), and
- let the EWMA decay run *through* those laps (this is the whole point of the fix).
Net effect: thermal load correctly decays toward zero over an SC period instead of
teleporting across it.

**A4. Solver alignment (`fit_compound_cliff.py`).** See table above. Then refit the
cliff seeds — this is a *second*, independent seed regeneration from the one in Phase 0
(that one fixes a severity-bound bug in the estimator; this one reflects the corrected
upstream geometry).

**Gates:** the 14 untracked `assert_*.sql` tests are the surviving spec from the
Phase-0 incident — they must pass **unmodified**. Spot-checked during this
consolidation: none of them depend on `int_stint_geometry`'s valid-lap filter directly
(they operate on already-valid-filtered downstream outputs — `int_lap_residual_decomposed`,
`int_compound_cliff_predicted`, `compound_cliff_params`, `int_lap_fuel_state`,
`int_track_evolution`), so Phase A's design (full sequence upstream, re-filter at each
consumer's boundary) is compatible with them by construction. Model-hash oracle will
change by design; re-snapshot is user-gated. `validate_gate.py` Spearman on
cliff-onset must not regress.

---

## Phase B — Bronze Pickups (independent, parallelizable after A)

**B1. `FreshTyre` → solver (trivial, do first).** Column already staged. Add to
the solver's load query; filter baseline compound-curve fits to
`is_fresh_tyre = TRUE` (~75% of laps retained). Scrubbed stints stay in the
survival set as a covariate, not dropped.

**B2. Status-aware censoring (cheap, small expected effect).** Join
`stg_results.status` (already staged + DNF-classified). Puncture/Wheel/Tyre →
true failure event for the survival tail; mechanical (Engine/PU/Gearbox/Brakes/
Hydraulics) → right-censor; Collision/Accident → censor. Only 13 true tyre
failures exist in 7 seasons — this sharpens the hazard tail slightly, no more.
`Retired` (n=110) is ambiguous → keep as censored.

**B3. Wind as covariate (scalar first).** `stg_weather` join already exists in
the solver (per-lap). Add `wind_speed_ms` as a covariate to the wear-gradient
regression and survival fit. **Defer directional aero** (head/tailwind per
corner) to Phase D — it needs track bearing from X/Y, i.e. B5.

**B4. `time_in_dirty_air_s` (upgrade, not new capability).** `int_lap_air_state`
already has 10Hz gap data; replace/augment the per-sector median with the actual
summed sample-time where gap < 1.5s. This is the input Phase C's normalization
needs. ~5% null gap samples: treat null as free air (current behavior).

**B5. XYZ track geometry (biggest new-code item).** New model
`int_track_geometry`: per circuit, median X/Y/Z per 25m distance bin →
gradient (dZ/ds) and curvature κ from X/Y → lateral-accel proxy `v²κ`.
Per-season binning first (GPS origin can drift between seasons); collapse to
per-circuit if stable. Unlocks: gradient-aware wear, slide-energy input
(deferred latent-state material §1), track bearing for B3-directional.

---

## Phase C — Normalize, Don't Discard (depends on B4)

- `normalized_pace_s = lap_time_s − dirty_air_penalty(time_in_dirty_air_s) − tow_benefit_lap_s`
- Wear/cliff fitting switches from "valid laps only" to "green-flag laps with
  normalized pace" — traffic-compromised laps come back into the fit.
  SC/VSC/pit laps stay excluded from *pace* fitting (they're not pace signals).
- Ratings/residual chain (`int_lap_residual_decomposed` onward) keeps its
  existing valid-lap gate — do NOT feed normalized laps into driver-skill
  residuals in this phase (double-counts the dirty-air component already
  modeled there).
- **Acceptance test:** per-stint wear-slope residual σ must drop vs. baseline,
  and cliff-onset Spearman (validate_gate.py, LORO 2018–2024) must hold ≥ current.

---

## Excluded / deferred

**Deferred to after Phase C ships:**
- Directional wind-aero (needs B5 bearing).
- Slide-energy EWMA input replacing dirty-air-only thermal proxy (needs B5 v²κ).
- Scrub `H(0)` initialization from quali stint history (quali laps are in bronze).
- The identifiability spike: check whether the two-channel EWMA state correlates
  with observed cliff timing *before* any latent-state framework work.

**Excluded outright** (original document's Parts 5 & 7): the continuous-time latent
state vector over tyre health/surface temp/carcass temp/pressure/fuel, energy-driven
degradation via integrated tyre work, unsupervised semantic track-segment clustering,
hypergraph spatio-temporal propagation, and the "publishable identifiability
contribution" framing. None of this has a scoped deliverable or acceptance test; it's
a research proposal, not an engineering plan, and depends on the identifiability spike
above coming back positive before there's any reason to invest in it.

---

## Risks / operational notes

- **Seed refit cascades.** New cliff seeds (Phase A4) change
  `int_compound_cliff_predicted` → ghost/degradation marts → the v4 ONNX feature
  distribution. `mart_degradation_predictions` is already stale from the Phase-0
  reconstruction; A4 makes retraining v5 (or re-scoring v4) a required follow-up, not
  optional.
- **CI is blind here.** `ml-ci.yml` had the known `dev.duckdb` path bug — Phase 0
  fixes this, but until it's committed, local validation with `--duckdb` override is
  the only real gate.
- **Don't let this go uncommitted for weeks.** The repo has now lost one round of
  transform-layer work to an uncommitted `git restore .` (see `CI_FAILURES.md`) and has
  a second round of uncommitted reconstruction sitting for 12+ days. Land and commit
  Phase 0 before starting Phase A; land and commit each phase (A/B/C) before starting
  the next, rather than letting the whole plan accumulate uncommitted in the working
  tree.

---

## Checkpoint

- 2026-07-19: Original plan (`compounds_plan.md`) created from warehouse audit.
  Nothing implemented.
- 2026-07-29: Consolidated the four `_improvements/` documents into this single plan.
  Re-verified the audit still holds (`int_stint_geometry.sql` unmodified since Jun 24;
  `int_corner_skill_residuals.sql` still separate from the reconstructed
  `mart_corner_skill_driver.sql`). Closed a gap in the original per-model audit
  (`int_constructor_structural_pace` had no documented disposition — added above: none
  required, self-filters). Added Phase 0 after discovering `CI_FAILURES.md`'s
  reconstruction is still uncommitted and shares files with Phase A4. Nothing
  implemented yet.
- 2026-07-30: Phase 0 implemented (steps A–E). Local dev environment needed repair
  first (`.venv`'s Python 3.12 had been removed by Homebrew — rebuilt on 3.14, plus a
  `mashumaro`/`libomp` local-only fix, neither affecting CI). Regenerated and promoted
  the `compound_cliff_params` seed. Full `dbt build` on CI fixtures surfaced a **third**
  lost Jul 6–10 model that session 2 of `CI_FAILURES.md` never found (it only ever ran
  `--select` on the 2 models it touched): `fct_ghost_car_pace` /
  `fct_ghost_race_finish` were missing fuel-adjusted residual-pace columns. Reconstructed
  bit-exactly against `dev.duckdb` (0 mismatches across ~1.3M rows) and verified via the
  previously-failing `assert_ghost_self_scenario_rank`, now passing. Full suite:
  PASS=538 ERROR=0 SKIP=0 TOTAL=541. Byte-stability oracle re-snapshotted (pre-existing
  6-model drift reconfirmed unrelated, unchanged in composition, root cause still not
  diagnosed — deliberately out of scope here). Docs regenerated. Stray files
  (`jcdlac`, `patch_compounds.py`) deleted per user confirmation. Full detail in
  `CI_FAILURES.md` session 3. Phase 0 committed as `ac2d82f`.
- 2026-07-30: Phase A implemented (A1–A4). `int_stint_geometry` now carries the full
  chronological lap sequence (SC/VSC/pit/invalid laps included) plus
  `valid_lap_in_stint`/`stint_length_valid`/validity flags; all 13 consumers + the
  solver updated per the per-model table, with one deviation from the original draft
  (`int_lap_thermal_proxy` stays unfiltered at output — see table note above, forced by
  `assert_no_future_leakage`/`assert_stint_boundary_integrity` reading it directly).
  A3's SC-bunching fix zeroes both `dirty_air_share_lap` and `dirty_air_intensity` on
  SC/VSC laps (not just intensity as literally written) since the tax-component's
  lag-through-the-gap logic depends on share being zero at the SC lap itself. A4
  re-keyed `survival.py`'s cliff detection/windowing on `age_in_stint` (tyre_life)
  instead of `lap_in_stint`, since `compound_cliff_onset_laps`/`compound_wear_gradient`
  are compared against `age_in_stint` downstream in `int_compound_cliff_predicted`, not
  `lap_in_stint` — confirmed via the 42 existing solver unit tests (all still pass,
  generous tolerances absorb the ~1-lap age/lap_in_stint offset) and a real refit
  against `dev.duckdb` (403 groups, identical fit-source distribution to the prior
  seed — 307 cox_km_survival / 58 class-default / 38 cross-season, confirming only the
  windowing values shifted, not group membership; onset delta median +1 lap, 0 severity
  values out of the [0, 1.5] bound). Refit seed promoted (prior seed archived, though
  the archive filename collided with Phase 0's same-day archive — original still
  recoverable via `ac2d82f`, see commit note). Full CI suite clean:
  `PASS=544 ERROR=0 SKIP=0 TOTAL=547` (541→547 from 6 new not_null tests on
  `int_stint_geometry`'s new columns), all 43 `assert_*.sql` pass. `validate_gate.py`
  cliff-onset Spearman (4.3 LORO backtest) improved 0.648 → 0.680 (no regression).
  Byte-stability oracle shows drift on exactly the touched models + their downstream
  cascade (6 `fct_*`, 17 intermediate) — expected by design, **not yet re-snapshotted**
  (user-gated, same as Phase 0). Docs regenerated (`docs-reference`, `docs-coverage`,
  `docs-facts`, `docs-audit` all clean).
- 2026-07-30: User signed off and committed Phase A themselves (squashed together with
  Phase 0 into a single commit, `c7c8509` — the earlier separate Phase 0 commit `ac2d82f`
  was reset/amended away in the process; confirmed via `git reflog`). Checklist above
  synced to match.
- 2026-07-30: B1 implemented. `load_stint_data` now selects `l.is_fresh_tyre`; added
  `fresh_tyre_only()` helper in `fit_compound_cliff.py` (NaN-safe `== True` mask, no-op
  if the column is absent) and applied it to the `estimate_wear_gradient` inputs only
  (both season and cross-season-fallback paths) — the baseline steady-state curve fit.
  Cliff-onset (KM survival) and severity keep the full lap set unfiltered. Added
  `is_fresh_tyre` as a per-stint covariate column in `build_survival_dataset`
  (`survival.py`), defaulting to `True` when absent (keeps old synthetic fixtures
  working) — scrubbed stints stay in the survival set, just flagged, per plan. Added 6
  new unit tests (`TestFreshTyreOnly`, plus 2 in `TestBuildSurvivalDataset`); full
  coefficients suite: 47 passed. Verified end-to-end against `dev.duckdb` 2023 season:
  77.3% of laps are fresh-tyre (matches the plan's ~75% estimate), fit completes
  cleanly across 66 circuit/compound groups, onset/severity/gradient values in
  plausible ranges. Pending seed from the validation run deleted (not a real refit —
  B2/B3 land first, then one combined refit).
- 2026-07-30: B2 implemented. `load_stint_data` now joins `stg_results.status` to
  get the raw DNF string, added as `dnf_status`. **Found and fixed a bug during
  verification**, not present in the original plan draft: the first version scoped
  the join by `driver_id + race_id` only, so a driver with 2+ stints before
  retiring got the *same* final DNF status attached to every one of their stints —
  including earlier stints that ended in a normal voluntary pit stop, not the
  failure. Fixed by additionally requiring `sg.stint_number = MAX(stint_number)`
  for that driver+race (the driver's last, retiring stint only). Verified against
  `dev.duckdb`: before the fix, 9 driver+race tyre-failure events produced 14
  flagged stints; after, 8 stints (one per event with qualifying lap rows) — 5
  fewer false positives. Added `is_tyre_failure()` (regex `puncture|tyre|wheel`,
  matches Puncture/Wheel/Wheel nut/Tyre; Engine/Collision/Retired/Gearbox
  correctly excluded) and wired into `build_survival_dataset`: a stint's
  `observed` flips to 1 (event, not censored) when it ends in a genuine tyre
  failure, even if `detect_cliff_lap`'s pace-based check didn't independently
  fire (a sudden puncture rarely produces the 2 consecutive slow laps that
  detector requires) — this is the "sharpens the hazard tail" effect the plan
  called for. Mechanical/collision/`Retired` DNFs are unaffected, staying
  censored by the existing default. Added `tyre_failure` as a carried covariate
  column alongside `is_fresh_tyre`/`forced_stop`. 13 new unit tests (censoring
  behavior + `is_tyre_failure` parametrized cases); full coefficients suite: 60
  passed. Verified end-to-end fit across all 7 seasons (403 groups) runs clean.
  Pending seed from validation deleted.
- 2026-07-30: B3 implemented. `load_stint_data` now selects `w.wind_speed_ms`
  (already joined via `stg_weather`). `estimate_wear_gradient` nets wind out via
  a 3-parameter OLS (`lap_time_s ~ intercept + age_in_stint + wind_speed_ms`,
  solved with `np.linalg.lstsq`) when `wind_speed_ms` is present and the linear
  window has ≥4 points (need at least one more point than parameters to avoid
  a degenerate perfect fit); falls back to the original 2-parameter
  `age_in_stint`-only `linregress` otherwise — this keeps every existing
  synthetic test (none of which set `wind_speed_ms`) on the exact old code
  path, unchanged. Rationale: wind adds aero drag independent of tyre wear, so
  without netting it out a windy stint's wear_gradient reads high. Also added
  `avg_wind_speed_ms` as a carried covariate on the survival dataset (mirrors
  the existing, already-carried-but-unused `avg_track_temp_c` pattern) —
  Cox-regression-based hazard adjustment for wind is not implemented (current
  onset fitter is nonparametric KM with no covariate support; adding a Cox
  model was judged out of scope for this "cheap, small effect" pickup and
  deferred to Phase D's directional-aero work if warranted). 2 new unit tests
  (wind-adjusted recovery against a synthetic wind-penalty injection; missing-
  column fallback). Full coefficients suite: 62 passed. Verified end-to-end
  fit across all 7 seasons runs clean; `wind_speed_ms` is 0% null in the 2023
  sample checked. Pending seed from validation deleted.
- 2026-07-30: B4 implemented. `int_lap_air_state.sql` now reads `Date` directly
  from `raw_telemetry` (same pattern as the existing direct `DistanceToDriverAhead`
  read — dropped in `stg_telemetry` staging) and computes `dt_s` per sample as
  elapsed time since the previous sample in the merged ~10Hz car/pos stream
  (`EPOCH(sample_ts - LAG(sample_ts) OVER (PARTITION BY race_year, race_id,
  driver_id, lap_number ORDER BY sample_ts))`). New `lap_dirty_air_time` CTE
  sums `dt_s` where `gap_to_ahead_s < 1.5` (null gap → excluded, i.e. treated as
  free air, matching the existing sector-median convention) into
  `time_in_dirty_air_s`, joined into `with_stint` and zeroed on SC/VSC laps
  (same bunching-trap treatment as `dirty_air_share_lap`/`dirty_air_intensity`).
  Added schema.yml column doc + not_null/range tests, bound `[0, 900]` — the
  900s (not a tighter bound) is deliberate: verified against `dev.duckdb`, max
  observed value is 385s from the 2020 Austrian GP's red-flag standing stoppage
  (lap 9, multiple drivers), where the bunched field genuinely sat within 1.5s
  gaps for real wall-clock minutes; a tighter bound would have been a false
  positive on a real event, not a data bug. Verified end-to-end: `dbt build
  --select int_lap_air_state` clean (7/7), full `dbt build` clean except one
  **pre-existing, confirmed-unrelated** failure below. No consumer of
  `int_lap_air_state` uses `SELECT *` (checked all 6: `fct_cliff_prediction_features`,
  `int_pit_strategy_value`, `int_qualifying_decomposed`, `int_field_pace_curve`,
  `int_lap_thermal_proxy`, `int_sector_residual_decomposed`,
  `int_dirty_air_tax_component` — none reference the new column, all select
  explicit lists), so this is a purely additive schema change.
  **Found and triaged, not fixed (out of scope for B4): `assert_cliff_predictions_valid`
  fails non-deterministically** (4 results this run, 1 result on a from-clean
  rebuild with my changes fully `git stash`ed — confirmed via stash test that
  this is unrelated to any B-phase work and already broken at `HEAD`, i.e.
  pre-existing since at least Phase A's commit despite that phase's gate
  claiming all 43 `assert_*.sql` passed). Root cause candidate:
  `int_compound_cliff_predicted.sql`'s `weather` CTE uses
  `DISTINCT ON (race_year, race_id, lap_number) ORDER BY race_year, race_id,
  lap_number` with no tiebreaker among rows sharing those keys (multiple
  telemetry-derived weather readings per lap) — DuckDB's pick among ties can
  vary by scan order/parallelism. The identical anti-pattern also exists in
  `int_track_evolution.sql`'s `weather_per_lap` CTE. Needs its own investigation
  and fix, not folded into B4 silently — flagging for explicit user decision on
  priority/ownership before touching it.
- 2026-07-30: B5 implemented. New model `int_track_geometry.sql`: reads X/Y/Z
  directly from `raw_telemetry` (joined to `race_to_track` for `track_id`,
  filtered to `0 < distance_m < 8000` to safely cover all real circuit lengths
  including Spa at ~7004m), bins to 25m (`FLOOR(distance_m/25)*25`), takes
  per-bin median X/Y/Z/speed. Grain is `(race_year, track_id, distance_bin)` --
  **not** collapsed to a single per-circuit shape as the plan's phrasing
  ("per circuit... per-season first... collapse if stable") left conditional:
  spot-checked Bahrain across all 7 seasons and found 2019's X/Y trace offset
  ~300-600 units from every 2020-2024 sample at the same distance bin (different
  GPS origin/heading convention), while 2020-2024 mutually agree. Averaging
  across that would corrupt the shape, so the per-circuit collapse is
  deliberately left undone — noted in the model header as a documented
  decision, not a gap. Gradient (`dZ/ds`) and curvature (`curvature_per_m`, Menger
  formula from 3 consecutive binned points: `4×Area / (|P1P2|×|P2P3|×|P1P3|)`)
  computed via `LAG`/`LEAD` over `distance_bin`; `lateral_accel_proxy_ms2 =
  bin_speed_ms² × curvature_per_m`. Start/finish bin is NULL by construction (no
  lap-boundary wraparound -- documented limitation, not a bug).
  **Validated the physics, not just that it runs**: spot-checked Monaco 2023 --
  the binned elevation profile's shape (climb from start/finish to a peak
  around Casino Square, descent through the tunnel back to harbor level, a
  second rise-fall near the tunnel exit chicane) matches the real circuit, and
  separately, the single highest `curvature_per_m` bin (0.0076) coincides with
  the lowest `bin_speed_ms` bin (~12.5 m/s ≈ 45 km/h) -- correctly identifying
  the Fairmont Hairpin, F1's slowest corner, as the sharpest point on the lap.
  Documented in the model header that Z is FastF1's raw telemetry unit, not
  verified as literal SI-meter elevation (a known FastF1 quirk) -- absolute
  gradient magnitude is a relative/proxy signal, not literal meters-per-meter.
  Added schema.yml documentation + not_null tests on the 3 grain columns.
  `dbt build --select int_track_geometry`: clean (4/4). 31,677 rows across 36
  circuits × 7 seasons (not all circuit/season combos exist, e.g. new venues).
  Full coefficients test suite still 62/62 (untouched by this SQL-only change).
  **Phase B (B1-B5) complete. Awaiting user sign-off before commit.**
- 2026-07-30: Fixed the `assert_cliff_predictions_valid` flakiness flagged above
  under B4 (out-of-scope, separate item, not a B-phase change). Confirmed the
  weather-CTE `DISTINCT ON` diagnosis was correct and complete: `stg_weather`
  is per-driver (grain = `lap_id`), so multiple drivers sharing a
  `(race_year, race_id, lap_number)` can ASOF-match different weather samples
  near a sample boundary — real ties, not a theoretical concern (measured on
  the CI fixture: 179 duplicate-key groups, 83 with genuinely differing
  `track_temp_c`). `DISTINCT ON` with no tiebreaker among those ties lets
  DuckDB's pick vary with scan order/parallelism. Proved this directly against
  `dev.duckdb`: re-running the pre-fix query under `PRAGMA threads` 1/2/3/4/6/8
  gave flagged-row counts of 2/0/4/3/1/2 for `assert_cliff_predictions_valid`'s
  condition — matching the "4 results this run, 1 on rebuild" symptom
  originally reported almost exactly. Fixed both occurrences (the identical
  anti-pattern really did also exist in `int_track_evolution.sql`'s
  `weather_per_lap` CTE, as flagged): added
  `weather_session_time_s DESC, driver_id` to each `DISTINCT ON`'s `ORDER BY`
  as an explicit, stable tiebreaker. Re-ran the same thread-count sweep
  post-fix: 0 flagged rows at every thread count, both models' full compiled
  output byte-identical across threads 1/2/4/8. Independently corroborated by
  a full `dbt build` the user had running concurrently during this
  investigation (started before the fix landed): it hit the exact same
  `assert_cliff_predictions_valid` failure ("Got 4 results") organically.
  **Found a second, unrelated pre-existing gap while re-running the full
  suite post-fix, previously masked**: with the flaky test no longer failing
  first (which had been skipping 197 downstream nodes depending on thread
  luck), the build now consistently reaches
  `not_null_fct_lap_residuals_compound_component_s`, which fails with 5 nulls.
  Traced to 5 specific 2018 stints (`2018_9`/HAM, `2018_10`/VET, `2018_16`/BOT,
  `2018_17`/HAM, `2018_6`/RIC, laps 1–2 of each) where
  `int_stint_geometry.compound_in_stint` is genuinely `NULL` — a bronze
  tyre-compound data gap, confirmed unrelated to weather or this fix (no
  weather column involved in that join path at all). Not fixed here — same
  "flag, don't silently fold in" treatment as the original find: needs its own
  look at why these 5 stints' compound tag is missing in bronze before
  deciding a fix (e.g. drop from `ml_eligible`, backfill, or leave as
  legitimate missing data), and it's a data-quality question, not a SQL-logic
  bug like the weather one.
- 2026-07-30: Re-ran the full `dbt build` to confirm Phase B end-to-end; noticed
  midway that you'd already landed your own fix for the `assert_cliff_predictions_valid`
  flakiness flagged above (deterministic tiebreak added to
  `int_compound_cliff_predicted.sql`'s `weather` CTE:
  `ORDER BY race_year, race_id, lap_number, weather_session_time_s DESC, driver_id`,
  with a comment noting ties are real — up to 20 rows/key, ~46% with differing
  `track_temp_c`). Good fix for the non-determinism, but the full build still
  shows the same 4 rows failing (`MEDIUM`/`2024_7`, `MEDIUM`/`2024_8`×2,
  `WET`/`2023_6`) — same combo every run now, confirming the earlier flakiness was
  real but not the only problem. **Distinct root cause found while checking**:
  `compound_cliff_params.csv` has `circuit_key = "2024_7"` / `"2024_8"` /
  `"2023_6"` (raw race_id strings) for those exact rows instead of a resolved
  friendly track name (e.g. `"2024_7"` should be `emilia_romagna_grand_prix`,
  which *is* present and correctly mapped in `race_to_track.csv` — so it's not
  a missing seed-mapping row). This is `fit_compound_cliff.py`'s
  `load_stint_data` falling back to `l.circuit_key` (== raw `race_id`, per
  `stg_laps.sql:22`) when its own `race_to_track` join
  (`CAST(SPLIT_PART(race_id,'_',1) AS INT)*100 + CAST(SPLIT_PART(race_id,'_',2)
  AS INT) = rtt.race_id`, comparing an INTEGER to `race_to_track.race_id`'s
  VARCHAR "YYYY_N") misses for these 3 races specifically while resolving
  correctly for ~99% of others — worth a `git blame`/direct-join-test session
  to pin down exactly why those 3 (not a full explanation yet, own investigation
  was cut short because `data/dev.duckdb` is locked by your own in-flight
  `dbt build --select int_compound_cliff_predicted+ int_track_evolution+`, so I
  backed off rather than race a concurrent process against the same file).
  Whatever the exact trigger, the fix belongs in the solver
  (`fit_compound_cliff.py`), not in `int_compound_cliff_predicted.sql` — the
  weather-join fix you already made is a real, separate, correct fix, just not
  the whole story. Not part of Phase B; flagging for your own follow-up.
- 2026-07-30: Root-caused and fixed the `race_to_track` join bug flagged above.
  **Scope was much larger than the 3 races originally spotted**: 64 of 149
  races (every single-digit round, 1–9, across all 7 seasons — 42% of races)
  silently fell back to raw `race_id` as `circuit_key` in `fit_compound_cliff.py`,
  not just the 3 that happened to also trip `assert_cliff_predictions_valid`'s
  bound check. Root cause: DuckDB treats `_` as a digit-group separator when
  casting numeric-looking strings (`CAST('2024_7' AS INTEGER)` → `20247`,
  verified directly), so dbt-duckdb's seed auto-detection silently cast
  `race_to_track.csv`'s `"YYYY_N"` text `race_id` column to INTEGER using that
  quirk — an undocumented, accidental encoding (unpadded year+round
  concatenation) that most other models' plain `ON x.race_id = rtt.race_id`
  joins happened to reproduce via the same implicit VARCHAR→INTEGER cast
  (confirmed empirically: 148/149 already matched that way), and that
  `mart_degradation_history_envelope.sql` had already independently
  rediscovered explicitly (`CAST(REPLACE(race_id,'_','') AS INTEGER)`). Only
  `fit_compound_cliff.py`'s join was actually broken — it reconstructed the key
  via `year*100+round` arithmetic, which only matches the real (unpadded
  concat) encoding when round is two digits. Fixed by removing the implicit
  cast dependency entirely rather than patching the arithmetic: added
  `race_id: varchar` under `race_to_track` in `dbt_project.yml`'s seed
  `+column_types` (required `dbt seed --full-refresh` — a plain reseed doesn't
  ALTER an existing seed table's column types, only `CREATE`-mode does), then
  simplified `fit_compound_cliff.py`'s join to plain `l.race_id = rtt.race_id`
  (both now honestly VARCHAR `"YYYY_N"`, no casting anywhere). Verified: 148/149
  races now match by construction (the 1 remaining miss, `2018_14`, is a
  genuine pre-existing gap — absent from `race_to_track.csv` entirely,
  unrelated to this bug); `load_stint_data` output confirmed 0 races still
  falling back to raw `circuit_key` except that same `2018_14`. CI-equivalent
  `make test-all` clean (550/550 dbt, 62/62 coefficients pytest) both before
  and after the refit. Refit `compound_cliff_params` against `dev.duckdb`
  (403 groups, all severities within `[0, 1.5]`): `fit_source` mix shifted
  `cox_km_survival` 307→307 (unchanged, as expected — unaffected groups),
  `cross_season_fallback` 38→74, `compound_class_default` 58→22 — the 63
  newly-fixed races can now pool with their circuit's other seasons instead of
  having nowhere to fall back to (previously isolated under a unique raw
  `race_id`, cascading straight to generic class defaults). Promoted (prior
  seed archived). Full `dbt build --target dev` against the real warehouse:
  clean (`PASS=550 ERROR=0`), `assert_cliff_predictions_valid` explicitly
  re-checked passing. **Not folded into Phase B** (separate bug, separate fix,
  per the flagging convention above) — this is its own change, seed-refit
  cascade risk applies same as A4/B (stale `mart_degradation_predictions` /
  v4 ONNX features). Not committed — user's call, same as Phase B.
- 2026-07-30: Phase C implemented. New leaf model `int_lap_normalized_pace`
  (`normalized_pace_s`), solver switched to green-flag laps + normalized pace,
  cliff seed refit and promoted. **The acceptance test half passes** — details
  and the two plan deviations below.

  **Baselines had to be re-measured first: the plan's 0.680 Spearman was
  stale.** Re-running `validate_gate.py` against HEAD (`9d6b7d4`) before
  touching anything gave 4.3 `model_spearman` = **0.599**, not 0.680, and 4.1
  SNR 0.263 vs 0.371. The 0.680 run (`gate_metrics.json`, 10:44) predates both
  Phase B and the `race_to_track` fix/refits, and the gate was never re-run
  after them. So an **unmeasured −0.081 Spearman regression is sitting in
  already-committed work** — not caused by Phase C, but worth its own look.
  Pre-Phase-C metrics preserved as `gate_metrics_baseline_prePhaseC.json`.

  **Acceptance criterion 1 (wear-slope residual σ): PASS.** No harness existed,
  so added `scripts/measure_wear_residual_sigma.py`, which mirrors
  `estimate_wear_gradient`'s window and model choice and reports both a
  like-for-like comparison (same laps, raw vs normalized y) and an end-to-end
  one (vs a stored baseline). Median per-stint σ 0.4139 → 0.3943 (−4.7%), 61.2%
  of 6,252 stints improved; end-to-end vs the stored baseline 0.4118 → 0.3941,
  64.5% improved.

  **Acceptance criterion 2 (Spearman ≥ current): FAIL, narrowly.** 4.3
  `model_spearman` 0.599 → 0.587 (−0.012), `model_kendall` 0.456 → 0.448,
  `model_top3` 0.507 → 0.486. All three move the same way, so it reads as a
  small consistent cost rather than noise in one statistic. 4.1 SNR and 4.4
  calibration are unchanged. Note the skill-only baseline also moved
  (−0.040 → −0.070), which is expected: the refit seed cascades through
  `int_compound_cliff_predicted` into the ratings marts. That cascade is the
  same one Phase A4 had; it does **not** mean normalized pace leaked into the
  residual chain (verified separately — see below).

  **Deviation 1 from the plan's formula: no tow term.** The plan specifies
  `normalized_pace_s = lap_time_s − dirty_air_penalty(...) − tow_benefit_lap_s`.
  Subtracting the tow term makes the acceptance metric materially **worse**:
  σ 0.4139 → 0.4291, with 91% of stints degraded. `tow_benefit_lap_s` is a
  heuristic constant (−0.15s per sector classified `tow_zone`), not a fitted
  quantity, so adding it back injects a step function of noise. It is carried
  as an output column but not applied. Fitting a real tow coefficient is the
  natural follow-up and would let this term come back.

  **Deviation 2: no fixed in-traffic step, despite the raw data suggesting
  one.** Bucketing by dirty-air exposure shows median partial residual −0.09s
  at zero exposure vs +0.16s in the 0–5s bucket — i.e. an apparent ~0.3s fixed
  cost for being in traffic at all, and a pooled step+slope fit puts it at
  0.294s. **It is almost entirely selection, not physics.** Re-estimated within
  stint (stint fixed effects, holding car/driver/circuit/tyre-set constant) the
  step collapses 0.294 → 0.07: slower cars simply spend more time in traffic,
  so a cross-sectional step charges every lap for the car's own pace deficit.
  Shipping it made the metric worse (0.4180 vs 0.4139 baseline). The shipped
  penalty is plain proportional, `theta_time × time_in_dirty_air_s`, with
  theta_time = 0.004219 fitted on clean/dry/valid laps including zero-exposure
  laps (they are the reference group that identifies the intercept).
  Independent check that this is signal and not just a shrunken correction: a
  sweep of theta against the acceptance metric has an **interior** optimum near
  0.005 (σ 0.3925), rising again above 0.006 and reaching 0.4904 by 0.020. The
  fitted 0.0042 lands beside that optimum without being tuned to it; the fitted
  value ships, since picking the σ-minimizing theta would be fitting the
  acceptance test.

  **Green-flag is a much smaller change than the plan implies.** `is_valid_lap`
  contains no traffic filter, so traffic-compromised laps were never being
  discarded in the first place — Phase C's value is the normalization, not lap
  recovery. Dropping `is_valid_lap` for an explicit green-flag filter relaxes
  exactly one condition, `is_accurate`; deleted laps (track-limits: void times,
  not compromised ones) and lap 1 (standing start) are kept out deliberately.
  Net effect on the solver: 129,045 → 129,774 laps (+0.6%), 6,672 → 6,677
  stints.

  **Guardrail verified.** `int_lap_normalized_pace` is a confirmed dbt graph
  leaf: no model refs it, only `fit_compound_cliff.py`'s loader reads it. No
  ratings/residual-chain model was touched (`git diff --stat` covers only the
  solver, its tests, `schema.yml`, and the new model).

  **Verification.** Full `dbt build --target dev` clean: `PASS=557 ERROR=0
  SKIP=0 TOTAL=560` (550→557 from the new model + its 6 tests); all 43
  `assert_*.sql` pass. Coefficients pytest 66 passed (62 existing unchanged + 4
  new for the `pace_col` path, which defaults to `lap_time_s` so every existing
  fixture stays on the original code path). Seed refit: 403 rows, `fit_source`
  mix identical (307 cox_km_survival / 74 cross-season / 22 class-default), so
  group membership is unchanged and only fitted values moved — onset mean
  −0.51 laps, severity mean −0.015, gradient mean −0.0007, 0 values out of
  bounds. The 2 remaining raw-`race_id` circuit keys are both `2018_14`, the
  known pre-existing `race_to_track.csv` gap, unchanged. Prior seed archived,
  though the same-day archive filename collided again (recoverable from
  `9d6b7d4`).

  **Open decision for the user:** criterion 1 passes decisively on the metric
  Phase C directly targets; criterion 2 fails by a small margin on a more
  distal finish-order metric. Not committed — user's call, same as prior
  phases.
- 2026-07-30: Root-caused the two loose threads left open above.

  **Thread 1 — the unmeasured −0.081 Spearman regression (0.680 → 0.599)
  between Phase A and Phase B+race_to_track: explained, not a bug, no code
  change.** Isolated by holding all current SQL fixed and swapping only the
  `compound_cliff_params` seed content between the Phase A (`c7c8509`) and
  Phase B+race_to_track (`9d6b7d4`) versions, rebuilding `dim_compounds_season+`
  each time (`fct_driver_skill_features.driver_residual_mean_s` nets out
  `compound_component_s`, so any seed change propagates into both the model
  and the skill-only baseline in gate step 4.3 — this is why baseline_spearman
  moved too, from +0.031 to −0.04). Splitting the 146 races into the 63 whose
  `circuit_key` the race_to_track fix actually changed (round ≤ 9, every
  season) vs. the 83 it didn't (round ≥ 10), and taking the paired per-race
  delta between the two seed states:

  | Group | n | mean Δ Spearman | SE | t |
  | :--- | :--- | :--- | :--- | :--- |
  | round ≤ 9 (race_to_track-affected) | 63 | −0.098 | 0.014 | −6.8 |
  | round ≥ 10 (unaffected) | 83 | −0.057 | 0.015 | −3.8 |

  Both drops are real (not noise) — meaning **two independent, already-shipped
  correctness fixes** each cost real Spearman, and they stack: (1) B1–B3's
  solver changes (fresh-tyre-only baseline fit, status-aware censoring, wind
  covariate) shift the fitted curve for essentially all 403 circuit/compound/
  season groups, producing the broad −0.057 that hits even untouched races;
  (2) the race_to_track fix additionally re-pools the 63 previously-mis-keyed
  races from isolated/wrong-fallback fits into correct cross-season pooling,
  costing an incremental ~−0.04 on top of (1) for exactly that group (spot-
  checked directly: `emilia_romagna_grand_prix` MEDIUM/2024's severity moved
  1.17→1.07 between seed states with identical fit_source/n_stints, confirming
  the shift is in the fitted values, not the grouping, for high-n races; the
  38→74 cross_season_fallback shift previously documented is where grouping
  itself changed, for low-n races). Both are more statistically sound fits of
  the underlying tyre physics; the ranking metric getting worse is the same
  "correctness costs a proxy metric" pattern Phase C's own criterion 2 already
  showed, not a new problem. No code change made — reverting either fix to
  recover Spearman would be reverting real bugs. Gate files already reflect
  current reality (`gate_metrics.json` = 0.587 post-Phase-C, consistent with
  this chain); nothing was stale, the number just hadn't been explained until
  now.

  **Thread 2 — the 5 null `compound_component_s` rows: already fixed,
  verified.** Turned out to already be resolved in the committed `9d6b7d4`
  diff (not flagged as done at the time): `marts/schema.yml`'s `not_null` test
  on `compound_component_s` was scoped to `where: "compound IS NOT NULL"` with
  a description documenting the 5-lap 2018 bronze gap. Re-verified directly:
  `dbt test --select not_null_fct_lap_residuals_compound_component_s` passes,
  and all 5 affected rows (`2018_10`/VET, `2018_16`/BOT, `2018_17`/HAM,
  `2018_6`/RIC, `2018_9`/HAM, each lap 2) do have genuinely NULL `compound` —
  confirmed not a join bug, a real missing tag in bronze. No further action
  needed; those laps are already excluded from `ml_eligible` via the same
  NULL check.

  (Investigation used temporary seed swaps + partial `dbt run --select
  dim_compounds_season+` rebuilds against `data/dev.duckdb` to isolate the
  effect; state was restored to the pre-investigation seed/build afterward and
  reverified against the committed gate numbers before writing this up.)

- 2026-08-22: Checklist reconciled with git. Phase C was in fact committed as
  `bd0ce6b` on 2026-08-03 (contains `int_lap_normalized_pace.sql`, the Phase C
  solver changes, the refit `compound_cliff_params` seed and
  `gate_metrics_baseline_prePhaseC.json`); this file's mtime predates that commit,
  so its last two boxes and the "Not committed — user's call" note above were
  simply never updated. The open question recorded at the Phase C checkpoint —
  whether the −4.7% wear-slope σ gain justified the −0.012 Gate 4.3 Spearman cost —
  was resolved in favour of shipping. **`PLAN.md` is complete; Phases 0/A/B/C all
  implemented and committed.** Remaining transform-layer work has moved to
  `transform_gaps.md`, which now carries its own live checklist.
