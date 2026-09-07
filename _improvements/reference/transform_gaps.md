# Transform Layer — Second-Pass Gap Audit

Companion to `PLAN.md`. That document covered the SC-hole and the compounds/bronze
pickups; this one is a fresh sweep of the rest of the transform layer for the same
classes of defect it found:

- data already staged and never consumed (the `FreshTyre` pattern),
- a filter/window applied at the wrong point (the SC-hole pattern),
- a join key that silently resolves to the wrong thing (the `race_to_track` pattern),
- a model built to replace something and never wired to it.

All numbers below were measured directly against `data/dev.duckdb` (read-only) on
**2026-07-30**, at the then-current working-tree state (Phase C implemented,
uncommitted). All seven findings have since been implemented — see the
Implementation Checklist and Checkpoint. The detail sections below are the audit as
written and describe the *pre-fix* state; where implementation found the audit
understated a problem, the checklist and checkpoint record what was actually there.

---

## Findings, ranked

| # | Gap | Status | Blast radius |
| :--- | :--- | :--- | :--- |
| 1 | Qualifying chain treats cool-down laps as push laps | ✅ **fixed** (Phase 3) | `int_lap_residual_decomposed_qualifying` → `int_qualifying_decomposed` → app leaderboard |
| 2 | `is_vsc_lap` / `is_safety_car_lap` decode the wrong FastF1 codes | ✅ **fixed** (Phase 1) | `stg_laps`, `stg_laps_qualifying`, 7 downstream models |
| 3 | `race_to_track` keys on event name, not physical venue | ✅ **fixed** (Phase 2) | cliff-seed pooling, all `circuit_key`-grouped fits |
| 4 | `dim_corners` covers 17 of 36 tracks; FastF1 corner geometry staged and unused | ✅ **fixed** (Phase 5) — its windows were wrong too | whole corner-skill chain (4 models); 17 → 34 slugs |
| 5 | `int_pit_loss_circuit` built, documented, never wired to its consumer | ✅ **fixed** (Phase 4) | `int_pit_strategy_value` now reads it; verdicts unmoved |
| 6 | SC-affected stops pollute the empirical pit loss (header claims otherwise) | ✅ **fixed** (Phase 4) | `int_pit_loss_circuit` output |
| 7 | `stg_pits.pit_duration_s` is 97.6% NULL and negative where present | ✅ **fixed** (Phase 4) — grain was broken too | half of `int_pit_loss_circuit`'s stop population was phantom |

Smaller items and unused-signal inventory follow the detail sections.

---

## Implementation Checklist (live — update as you go)

Master tracker for this document, same convention as `PLAN.md`: check items off as they
land, add a dated entry to **Checkpoint** (bottom) at each phase boundary, and keep the
boxes in sync with reality — this is the resumption point if a session ends mid-phase.

Order follows **Suggested sequencing** at the bottom of this file. All five phases are
implemented in the working tree; nothing is committed — the user commits, never the agent.

### Phase 0 — bookkeeping (no code)
- [x] `PLAN.md` checklist synced — Phase C shipped in `bd0ce6b` (2026-08-03), its last
      two boxes were never ticked; Checkpoint still reads "Not committed — user's call"
- [x] Revert the stray trailing whitespace in `ingestion/src/ingest.py:39` (only dirty
      file in the tree, unrelated to any of this)
- [x] **User-gated:** delete the four docs `PLAN.md` supersedes (`compounds_logic.md`,
      `compounds_plan.md`, `downstream_audit.md`, `chat_history_compounds_architecture.md`).
      `_improvements/` is untracked in git, so deletion is unrecoverable — confirm first.
      Confirmed by user and deleted 2026-08-22.

### Phase 1 — #2 SC/VSC/red decode (self-contained; do first, everything else sits on it)
- [x] `stg_laps.sql` — `is_safety_car_lap → '.*4.*'`, `is_vsc_lap → '.*[67].*'`,
      new `is_red_flag_lap → '.*5.*'`; stale decode comment corrected
- [x] `stg_laps_qualifying.sql` — identical fix
- [x] **Consumer sweep — the part that is not cosmetic.** Every consumer pairs the flags
      as `sc OR vsc` (or `NOT sc AND NOT vsc`), which today covers codes 4/5/6/7. After
      the fix that union is 4/6/7 and silently drops 426 red-flag laps out of the
      neutralised set. Each must gain `is_red_flag_lap` to hold the row set constant:
  - [x] `int_event_corrections` — LAG/LEAD restart detection + `correction_class` +
        `correction_weight` all widened to the three-flag union
  - [x] `int_lap_anomaly_flags` — `anomaly_class` + `usable_for_modelling`
  - [x] `int_lap_air_state` — all 3 zeroing branches (share/intensity/time-in-dirty-air)
  - [x] `mart_corner_skill_driver`
  - [x] `mart_degradation_history_envelope`
  - [x] `int_stint_geometry`, `int_lap_residual_decomposed`, `fct_lap_residuals` —
        pass-through; `is_red_flag_lap` carried to the mart
  - [x] `app/src/features/lap-waterfall/queries.ts` (2 sites),
        `app/src/features/race-lost/queries.ts`, `scripts/analyze_race_case_study.py`.
        **These were the real regression risk:** all three filtered on
        `NOT is_safety_car_lap` alone, which under the broken decode silently meant
        "not SC *and* not VSC". Left untouched they would have started admitting VSC
        laps. Now filter the full three-flag set. `fct_lap_residuals` parquet is
        gitignored (`app/.gitignore`) and regenerated at deploy, so no committed data
        changes here; verified by running the app's own filter against a fresh export,
        and `tsc --noEmit` is clean. See "App data is two months stale" below.
- [x] Schema docs rewritten in `staging/schema.yml` (both models) +
      `intermediate/schema.yml`; `not_null` tests on all three flags
- [x] New `assert_track_status_flag_partition.sql` — 5 checks: each flag matches its
      digits exactly, the union equals `[4567]`, and no neutralised lap is valid.
      Categorised in `transform/tests/README.md` (required by the docs-facts gate)
- [x] **Verified, not assumed.** Ground truth re-confirmed from bronze first
      (`stg_track_status` message column: 4=SCDeployed, 5=Red, 6=VSCDeployed,
      7=VSCEnding). Post-fix on `dev.duckdb`: 8,927 SC / 2,980 VSC / 426 red —
      matching the audit exactly. Neutralised union **11,787 before → 11,787 after**;
      `is_valid_lap` unchanged at 24,449 invalid laps.
- [x] Downstream proven unchanged by snapshot-and-compare across the full 48-model
      cascade on `dev`: `correction_class` distribution, `SUM(correction_weight)`,
      restart/pre-controlled/yellow counts, `anomaly_class` distribution,
      `usable_for_modelling`, all `int_lap_air_state` sums, `driver_skill_residual_s`
      sum, and both mart row counts are **bit-identical**. The only difference anywhere
      is the intended relabelling in `int_stint_geometry` (SC 11,656→8,927,
      VSC 426→2,980).
- [x] Byte-stability oracle isolated by stash-and-rebuild (the committed baseline is
      stale — it predates Phases B/C, which list as "NEW models"). Against a true
      pre-change baseline my diff drifts exactly **7 of 62 models**, all of them ones
      that now carry the added column: `stg_laps`, `stg_laps_qualifying`,
      `int_stint_geometry`, `int_event_corrections`, `int_lap_residual_decomposed`,
      `int_lap_anomaly_flags`, `fct_lap_residuals`. `int_lap_air_state` and 5 of the 6
      other `fct_*` are byte-identical — confirming red-flag laps were already being
      zeroed under the old decode, so nothing numeric moved.
- [x] Gate: full `dbt build` on CI fixtures **PASS=565 ERROR=0 SKIP=0 TOTAL=568**;
      `dbt test` on dev **PASS=495 ERROR=0**; all 44 singular `assert_*` pass (43 + the
      new one). No seed refit needed — confirmed, the solver never reads these flags.
- [x] Docs regenerated; `docs-audit`, `docs-facts`, `docs-coverage-check` all pass.
      App `tsc --noEmit` clean.
- [x] Confirmed `make app-data-check` already fails at clean HEAD — the app-data
      drift is pre-existing, not caused by this change (see the finding below)
- [x] **Oracle baseline re-snapshotted.** `dbt build --target ci` rebuilt against the
      current working tree (PASS=565 ERROR=0 SKIP=0 TOTAL=568, matching the earlier gate
      run), then `snapshot_model_hashes.py` wrote a fresh baseline for 60 models.
      `--check` against it now passes clean: `OK: all 7 fct_* models byte-stable`.
- [x] User sign-off

### Phase 2 — #3 venue identity (cliff-seed refit; blocks #4)
- [x] Repoint `fit_compound_cliff.py:99` cross-season pooling from `race_to_track.track_id`
      to `dim_circuits.circuit_id`; sweep other `circuit_key` groupings
- [x] Cliff-seed refit + promote; expect the 4 A-side keys off `compound_class_default`
- [x] Sweep found + fixed two more instances of the same bug beyond the fitter script:
      `int_driver_circuit_affinity` (driver×circuit affinity) and
      `int_circuit_x_constructor_interaction` (constructor×circuit interaction) — both
      pooled cross-season fits on `circuit_key` (event slug) instead of `circuit_id`
      (physical venue). User confirmed extending Phase 2 to cover both.
- [x] Re-measure gates (measure fresh, do not compare to the stored number)
- [x] User sign-off

### Phase 3 — #1 qualifying push-lap gate (largest correctness win; independent of 1-2)
- [x] 1c — **Q1/Q2/Q3 was not recoverable from bronze as staged.** The audit assumed it
      was; it is not. Bronze carried only qualifying *laps* — `session_status`,
      `track_status` and `results` were written for race sessions only, and the Q1/Q2/Q3
      columns on the race `results` are 100% NULL across all 7 seasons (they populate
      only on the qualifying session's own results). Ingestion therefore had to be
      extended before any of this was possible:
  - [x] `ingestion/src/ingest.py` — `_write_session_status`, `_write_track_status` and
        `_write_results` gain a `session_type` parameter and write under `session=Q/`,
        the same partition split `_write_weather` already used. Called from
        `ingest_qualifying`.
  - [x] Backfilled all 149 qualifying sessions, 2018–2024, from the FastF1 cache
        (`--session Q --force`). Quali lap parquet re-verified content-identical
        afterwards against the committed CI fixtures, which predate the run — the byte
        differences are parquet metadata only.
  - [x] CI fixtures regenerated for the three fixture races (new `session=Q/` files
        only; the race-session fixtures were reverted, since regenerating them pulls in
        unrelated bronze drift — a column added to laps/telemetry/weather/race_control
        since the fixtures were last cut, and a telemetry row-count change)
- [x] `stg_session_status_qualifying` + `stg_results_qualifying` staging models, with
      sources, schema docs and tests
- [x] `int_qualifying_segments` — the Q1/Q2/Q3 windows. Two sources, because neither is
      sufficient: the status timeline gives green lights but not which of them opens a
      segment (a red flag inside a segment produces more), and the official results give
      each driver's segment best but cannot say where a segment starts. Anchoring one to
      the other resolves it. Three real sessions each broke a simpler rule and are named
      in the model header
- [x] `int_qualifying_push_laps` — `is_push_lap` at lap grain (not in
      `stg_laps_qualifying`: the gate needs a join, and staging's contract is no joins).
      Within `quali_push_lap_ratio` (1.07, a new documented `dbt_project.yml` var) of the
      lap's **own segment's** best, or the driver's own best in that segment so nobody
      drops out of the decomposition
- [x] `field_pace` + the decomposition gated on it, in **both** models that computed a
      session median over the polluted set — `int_lap_residual_decomposed_qualifying` and
      `int_constructor_structural_pace_qualifying`. The latter is not named in the
      finding but carries the identical defect and feeds `constructor_component_s` into
      the identity
- [x] 1b — `quali_skill_session_avg_s` from mean-over-PB-laps to the residual of the
      driver's best push lap per segment, averaged over segments contested
- [x] `track_unexplained_s` carried into the qualifying chain from `int_track_evolution`,
      informational and outside the identity — the same treatment as the race side
- [x] `app/src/features/quali-vs-race-skill/queries.ts` re-read: every column it selects
      still exists and still means what it did, so no change needed. Same for
      `constructor-structural-pace` and `party-mode`, which read
      `int_constructor_structural_pace_qualifying` (values move, schema does not)
- [x] New `assert_quali_segment_matches_official.sql` — every official segment time was
      set inside the segment we assigned it to. 6,578 of 6,581 pass; the 3 failures are
      FastF1 copying a Q3 time into the Q2 column, which the test skips by rule rather
      than by allowlist. Registered in `transform/tests/README.md`
- [x] Gates: `dbt build` **PASS=599 ERROR=0** on both `dev` and `ci`; 45 singular tests
      pass on fixtures; coefficient pytest 66/66; `make lint` clean for the new models;
      docs regenerated with `docs-audit` / `docs-facts` / `docs-coverage-check` all
      passing; app `tsc --noEmit` clean; byte-stability oracle **OK, all 7 `fct_*`
      byte-stable** (the quali chain feeds no mart), baseline re-snapshotted for 64 models
- [x] User sign-off

### Phase 4 — the pit-loss thread (#7 → #6 → #5, in that order)
- [x] #7 — `stg_pits` rebuilt. The audit called this a broken column; the grain was
      broken too. Bronze splits a stop across two lap rows (`PitInTime` on the in-lap,
      `PitOutTime` on the out-lap) and the model emitted **both**, so "one row per pit
      stop" was never true: 10,319 rows for 5,336 stops, plus 107 pit-lane race starts.
      `pit_duration_s` now resolves the exit side by `LEAD` over the driver's own pit
      laps, guarded on the successor being the very next lap: 5,109 non-NULL (was 244),
      all positive (was all negative), median 23.93 s.
  - [x] `pit_out_lap_number`'s hardcoded `lap_number + 1` **verified**: correct on every
        one of the 5,109 stops that has an out-lap at all, NULL on the 227 that do not
        (retired in the pit lane, or the race ended under the stop). Now read rather
        than assumed.
  - [x] Third defect found in the same model, not in the audit: `compound_out` was read
        off the in-lap, so it named the tyre being **removed**, not the one fitted —
        wrong on 3,844 of 5,109 stops. Split into `compound_in` (in-lap) and a correct
        `compound_out` (out-lap). Unconsumed today, documented in `schema.yml` as if it
        worked: the same trap class as the duration column.
- [x] #6 — neutralised stops excluded in `int_pit_loss_circuit`'s `stops` CTE, on both
      the in-lap and the out-lap, using Phase 1's three corrected flags
  - [x] **The larger contaminant was the grain, not SC.** Because the model never
        filtered on `pit_in_time_s`, every out-lap row also entered as a stop keyed one
        lap late: **3,577 of the 7,308 "clean stops" (48.9%) were phantom**, median
        19.19 s against 23.64 s for the real ones. Fixing #7 removes them; #6's 674
        SC-affected stops (9.2%) were the smaller half of the problem. Net effect on the
        estimate is upward, not downward: mean 22.72 → 23.57 s.
  - [x] Finding #3's bug was in this model too. It pooled on `race_slug` (event name),
        splitting Silverstone into `british_grand_prix` (n=297, 22.76 s) and
        `70th_anniversary_grand_prix` (n=82, 19.29 s) — 3.5 s apart on one pit lane —
        and likewise Interlagos, Mexico and the Red Bull Ring. Now estimated per
        `dim_circuits.circuit_id` and emitted per event slug, the same shape Phase 2
        used for the cliff fitter, so the consumer's `race_to_track` join is unchanged.
        36 slugs over 32 physical venues.
- [x] #5 — `int_pit_loss_circuit` wired into `int_pit_strategy_value`. Full replacement
      (user-chosen): `pit_loss_s_shrunk` wins wherever it resolves, seed then 21.0 as
      fallback, and a new `pit_loss_source` column records which. 7,094 of 7,129 stints
      now empirical; the 35 that are not are one race, 2018 round 14, whose
      `race_to_track` row has a NULL `track_id` — a pre-existing seed gap, not caused
      here. `pit_lane_loss_s` range 19.30–29.61 s against the seed's flat 21.0/19–24.
- [x] Undercut-threat scan de-hardcoded (user-chosen): `min_gap_s < 22.0` becomes
      `< pit_lane_loss_s + 1.0`, which is what the model's own comment already claimed.
- [x] **The wiring moves less than the audit implies, and the measurement says why.**
      Against a pre-change snapshot of all 7,129 stints: `pit_lane_loss_s` changed on
      7,094, `undercut_threat_lap` on 37, `opportunity_cost_s` on 1, and
      `strategy_verdict` on **zero** — so `fct_stint_features.pit_decision_class` is
      bit-identical and nothing reaches the ML feature set. The reason is that the
      optimal-pit-lap search never consumed pit loss: it approximates the argmin as
      "first lap in the cliff window where expected wear exceeds 0.5 s". A longer pit
      lane therefore still does not push the modelled optimum later, which it physically
      should. Recorded as the credible next step in `strategy.mdx`, not fixed here —
      solving the real `Total_Cost(L)` minimisation is a rewrite of the model's core,
      not a wiring change.
- [x] Two singular tests, both registered in `transform/tests/README.md`:
      `assert_pit_stop_grain` (5 checks: one row per stop, out-lap is the next lap, the
      three exit-side columns resolve together, duration positive, duration equals its
      two stamps) and `assert_pit_loss_excludes_neutralised` (3 checks: independently
      rebuilt green-flag stop population matches the model's counts, slugs sharing a
      venue carry one estimate, EB value between circuit and global medians)
- [x] `pit_loss_min_s` / `pit_loss_max_s` / `pit_loss_prior_stops` promoted from inline
      `var()` defaults to documented `dbt_project.yml` vars, matching the convention
      Phase 3 set for `quali_push_lap_ratio`
- [x] Gates, all re-measured this session rather than compared to a stored number:
      `dbt build` on dev **PASS=610 ERROR=0 SKIP=0 TOTAL=613**; `make test-all` on the
      3-race CI fixtures **PASS=610 ERROR=0**, identical; both new singular tests pass on
      dev and on fixtures; coefficient pytest **66/66**; ingestion pytest 53/53; app
      `tsc --noEmit` clean; `docs-audit`, `docs-facts` and `docs-coverage-check` all
      pass after regenerating reference docs and snippets; `sqlfluff` clean on all five
      files touched.
- [x] Byte-stability oracle **OK: all 7 `fct_*` models byte-stable**, with exactly three
      non-mandatory models drifting — `stg_pits`, `int_pit_loss_circuit`,
      `int_pit_strategy_value`, i.e. precisely the three changed. This is the independent
      confirmation that `strategy_verdict` did not move: `fct_stint_features` is
      byte-identical to its pre-change hash. Baseline re-snapshotted for 64 models;
      `--check` clean afterwards.
- [x] No committed app data changes needed. `int_pit_strategy_value` and `stg_pits`
      export to `app/public/data/intermediates/`, which `app/.gitignore` excludes; the
      four tracked artifacts (`mart_corner_skill_driver`,
      `mart_degradation_history_envelope`, `ml/mart_degradation_predictions`,
      `_manifest.json`) are none of them downstream of pit loss. The app's
      `pit-strategy` feature selects `pit_lane_loss_s` by name and its schema is
      unchanged — the value moves, the contract does not.
- [x] User sign-off

### Phase 5 — #4 corner coverage (largest new-code item; depends on #3)
- [x] `dim_corners` derived from `stg_circuit_info` as a new reference model; the seed is
      deleted, not kept as an override. **Deviation from the plan, on measurement:** the
      seed was not curated geometry to fall back on. Its 193 rows were a uniform tiling of
      250–500 m blocks abutting each other, with corner counts unrelated to the real
      layout (Monza 8 blocks for 11 turns, Monaco 12 for 19, Abu Dhabi 9 for 16). At
      Bahrain its `Turn_2` block (700–1050 m) spans FastF1's turns 1, 2 and 3 — apexes at
      717, 819 and 941 m. Keeping it as an override would have preserved the wrong windows
      on exactly the 17 slugs that had any coverage. The override *mechanism* is not built
      either: no venue needs one (see the validation below), and an empty seed with a
      LEFT JOIN nothing ever exercises is the same dead-mechanism pattern this audit keeps
      finding. The model header records how to reintroduce it if a venue's geometry is ever
      found bad
- [x] Geometry keyed **per race**, not per venue, and the consumer joins on `race_id`.
      FastF1 publishes the corner table per event; Abu Dhabi (21→16), Singapore (23→19)
      and Barcelona (16→14) each change corner count mid-history, and the distance origin
      shifts between seasons at some venues (São Paulo, Baku) — the same discontinuity
      `int_track_geometry` already documents in the X/Y frame. Pooling seasons would blur
      both. This also sidesteps finding #3 entirely: nothing pools across event slugs
- [x] Window = apex ± margins, clipped at the neighbouring apexes.
      `corner_entry_margin_m` (250) and `corner_exit_margin_m` (150) are documented
      `dbt_project.yml` vars, calibrated from telemetry rather than picked: on corners with
      a clear 600 m approach the braking zone is p50 119 m / p95 181 m / p99 232 m, and of
      the cells that reach full throttle before the next apex, 96.7% do so within 150 m
      (250 m would recover 2.4 points of that at the cost of reaching further into the next
      corner)
- [x] **Geometry validated, not assumed.** Against a 10 m-binned median speed trace over
      valid laps, on the 1,586 slow corners (apex under 55% of the race's peak binned
      speed, where the minimum is unambiguous) the FastF1 apex sits a median **2 m** from
      the measured speed minimum; no venue's median offset exceeds 54 m. Spot checks land
      where they should: Monaco's slowest corner is `Turn_6` at 42 km/h (the Fairmont
      hairpin), Monza's fastest is `Turn_3` at 254 km/h (Curva Grande)
- [x] `int_corner_metrics` rewritten onto the new key, and `throttle_point_m` corrected to
      the **first** full-throttle sample at or after the apex. It was `MAX`, i.e. the last
      full-throttle sample in the block — which under abutting blocks is the lift point for
      the *next* corner, and landed within 20 m of the block boundary on 41% of cells. The
      docs already described the column as "throttle-application point … positive = gets on
      power later", so this is the documented-but-wrong class again. `race_to_track` leaves
      the path with the old key, which also recovers 2018_14 (the one race missing from
      that seed, silently dropped from the whole corner chain)
- [x] **Defect found while measuring, not in the audit: the corner mart was reading missing
      phases as the maximum penalty.** `mart_corner_skill_driver` winsorises each cell with
      `GREATEST(-1.0, LEAST(1.0, driver_mean − loro))`, and DuckDB's `LEAST`/`GREATEST`
      *ignore* NULL arguments instead of propagating them, so a corner with no braking zone
      or no exit measurement entered the season mean as **+1.0 s** rather than as no
      observation. That is why every phase's cell count was identical to `mapped_corners`,
      why no `z` was ever withheld by the 30-cell floor the model documents, and why every
      driver's `corner_skill_index` was positive: the phase means carried a +0.09 to +0.35
      bias while `mid_corner`, which has no NULLs, sat at exactly 0.000. Fixing the window
      definition raises the exit NULL rate (an exit only exists where full throttle returns
      before the next apex), so shipping the coverage change without this fix would have
      made the bias worse. Guarded explicitly; all three phase means are now 0.000 in every
      season and the phase gate fires for the first time (2019 withholds 2 of 20 drivers)
- [x] Coverage re-measured end to end: `dim_corners` **2,441 corners over 147 races and 34
      slugs** (was 193 over 17), of which 143 races carry their own geometry and 4 borrow
      the nearest season of the same slug; only 2020 Sakhir and Tuscan have no geometry
      anywhere. `int_corner_metrics` 1,129,351 → **2,593,635** cells over 34 slugs;
      `int_corner_skill_residuals` 970,874 → **2,206,939** rows with the thin-sample
      `corner_unmapped_flag` down 25.8% → 17.1%; `mart_corner_skill_driver` 92 → **141**
      driver-seasons with **all seven seasons** populated (2020 had none at all) and mean
      mapped corners 123 → 272; `fct_telemetry_deltas` 10.7M → **24.5M** rows
- [x] New singular test `assert_corner_window_geometry` — 5 checks: the window contains its
      own apex, stays inside its neighbouring apexes, respects the configured margins,
      borrowed geometry never crosses event slugs, and the corner count matches the source
      session. Registered in `transform/tests/README.md`
- [x] Gates, all re-measured this session: `dbt build` on dev **PASS=627 ERROR=0 SKIP=0
      TOTAL=630**; `make test-all` on the 3-race CI fixtures **PASS=627 ERROR=0**, identical,
      with the new test passing on fixtures too; coefficient pytest **66/66**; `sqlfluff`
      clean on both new/rewritten models and on the new test (the mart's 8 pre-existing
      `make lint` findings are in its untouched z-score block, and the 8-model failure set
      is unchanged); `docs-audit`, `docs-facts`, `docs-coverage-check` all pass after
      regenerating reference docs and snippets; app `tsc --noEmit` clean
- [x] Byte-stability oracle: exactly one `fct_*` drifted, `fct_telemetry_deltas`, which is
      the only fact downstream of the corner windows, with `int_corner_metrics` and
      `int_corner_skill_residuals` as the two non-mandatory warnings — i.e. precisely the
      changed set. `mart_corner_skill_driver` cannot drift on fixtures: 3 races put every
      driver under its 100-cell floor, so it is empty there. Baseline re-snapshotted;
      `--check` clean afterwards
- [ ] **Committed app data is now stale for one tracked artifact.**
      `app/public/data/marts/mart_corner_skill_driver/*.parquet` is downstream of this
      change and gains a 2020 partition it has never had. Not regenerated here: the export
      is all-or-nothing (`_manifest.json` carries a hash over the whole output tree), so
      running it would also swap the committed v3 degradation predictions for the local v4
      — the change the audit already says deserves its own commit. The pending app-data
      refresh picks this up; `make app-data-check` fails at clean `HEAD` either way. That
      refresh also grows the CDN payload: `fct_telemetry_deltas` exports 59 MB → 168 MB and
      `int_corner_metrics` 13 MB → 27 MB
- [ ] User sign-off

**Carried from `PLAN.md`, applies to every phase:** any change touching the cliff seed
cascades into `mart_degradation_predictions` and the v4 ONNX feature distribution, and
gate metrics must be re-measured before each phase rather than compared against a stored
number.

---

## 1. The qualifying chain treats cool-down laps as push laps

**The highest-impact finding, and the least-audited corner of the layer.** None of the
five qualifying models (`stg_laps_qualifying`, `int_lap_fuel_state_qualifying`,
`int_constructor_structural_pace_qualifying`, `int_lap_residual_decomposed_qualifying`,
`int_qualifying_decomposed`) were in Phase A's 13-consumer audit, because none of them
touch `int_stint_geometry`. They have their own version of the same bug class.

`is_valid_lap` in `stg_laps_qualifying` is `lap_time_s > 0 AND NOT is_pit_lap AND NOT
is_deleted AND is_accurate AND NOT SC/VSC AND lap_number > 1`, and `is_pit_lap` is
`pitouttime IS NOT NULL OR pitintime IS NOT NULL`. That correctly removes out-laps and
in-laps. It does **not** remove the cool-down / preparation laps *between* two push laps —
those have no pit time, so they pass every condition. A qualifying run is
out-lap → push → cool-down → push → in-lap; the middle lap survives as "valid".

Measured over all 18,944 laps the model treats as valid (`stg_laps_qualifying`, 7 seasons):

| Lap set | n | median ratio to session best | p95 ratio | n slower than 107% |
| :--- | ---: | ---: | ---: | ---: |
| `is_valid_lap`, not pit | 18,944 | 1.029 | **1.497** | **5,623 (29.7%)** |
| invalid, not pit | 1,237 | 1.045 | 1.497 | 511 (41.3%) |
| pit in/out laps | 11,418 | 1.323 | 1.581 | 11,395 (99.8%) |

Nearly **30% of the laps feeding the qualifying decomposition are >107% off the session
best** — the classic F1 cut for "this was not a serious lap". The p95 valid lap is 50%
slower than the session best.

The consequence, in `int_lap_residual_decomposed_qualifying`:

```
quali_pace_delta_s:   p05 −3.01   p50 0.00   p95 +36.56   max +69.52
                      3,902 laps (20.6%) over +10s;  1,629 (8.6%) over +30s
```

There is no `unexplained_residual_s` term in the qualifying identity — the race-side
model has one, the qualifying one does not. So the full excess lands in
`quali_driver_skill_residual_s`, whose mean absolute value is **7.04s with σ = 13.13s**,
against a real qualifying field spread of ~1–3s. `assert_qualifying_7term_identity`
passes throughout, because the identity closes regardless of what the skill term absorbs.

Two compounding sub-gaps in the same chain:

**1a. `base_track_pace_s` is a median over the polluted set.** `field_pace` in
`int_lap_residual_decomposed_qualifying` takes `PERCENTILE_CONT(0.5) FILTER (WHERE
is_valid_lap)` over the whole race. Against a median restricted to laps within 107% of
the session best, that baseline runs **+0.934s high on average** (p50 +0.234s, p90
+2.015s, max +19.193s across 149 races). This shifts every driver in a race equally, so
within-race ranking survives — but `quali_vs_race_skill_delta_s` subtracts a race-side
residual built on a properly-filtered baseline, so the delta is directly biased.

**1b. Averaging over `is_personal_best` mixes Q1 and Q3 track states.**
`int_qualifying_decomposed.quali_skill_session_avg_s` is
`AVG(quali_driver_skill_residual_s) FILTER (WHERE is_personal_best = TRUE)`. FastF1's
`IsPersonalBest` fires on *every* lap that improves the driver's session best, not once —
measured at **4.58 laps per driver-race, max 15**. Averaging them pools a Q1 first-effort
lap with a Q3 final lap across ~1s of track evolution, and the penalty scales with how
many improving laps the driver happened to set:

| PB laps in session | n driver-races | avg of PB-mean (s) | avg of PB-best (s) | penalty from averaging (s) |
| ---: | ---: | ---: | ---: | ---: |
| 1 | 133 | 0.580 | 0.580 | 0.000 |
| 2 | 333 | −0.079 | −0.703 | 0.624 |
| 4 | 578 | −0.333 | −1.359 | 1.026 |
| 6 | 375 | −0.115 | −1.685 | 1.570 |
| 8 | 114 | −0.227 | −3.803 | 3.576 |
| 10 | 30 | −0.551 | −4.678 | 4.126 |

Monotone in PB count. A driver who builds up incrementally is charged up to ~4s of
"skill deficit" that is purely an artefact of the aggregation.

**1c. Q1/Q2/Q3 are not distinguished anywhere.** `stg_laps_qualifying` hardcodes
`CAST('Q' AS VARCHAR) AS session_type`, and every baseline in the chain is per-race, not
per-segment. Since Q3 is both a faster track and a self-selected top-10 field, pooling
the three segments into one median is what makes 1a as large as it is.

**Where it surfaces:** `app/src/features/quali-vs-race-skill/queries.ts` reads
`quali_skill_session_avg_s` directly for the Quali vs Race Skill leaderboard.

**Suggested fix order:** add an explicit push-lap definition in `stg_laps_qualifying`
(e.g. `is_push_lap` = valid AND within 107% of the driver's own session best, or the
lap is a PB lap or immediately precedes one), gate `field_pace` and the decomposition on
it, then switch `quali_skill_session_avg_s` from a mean over all PB laps to the driver's
best PB lap per segment. Recovering Q1/Q2/Q3 from bronze (1c) is a prerequisite for
doing the baseline properly and should be scoped first.

---

## 2. `is_vsc_lap` and `is_safety_car_lap` decode the wrong FastF1 codes

`stg_laps.sql:121-122` (and identically `stg_laps_qualifying.sql:138-139`):

```sql
REGEXP_MATCHES(track_status, '.*[467].*') AS is_safety_car_lap,
REGEXP_MATCHES(track_status, '.*5.*')     AS is_vsc_lap,
```

FastF1's actual codes are `4 = SC`, `5 = Red flag`, `6 = VSC deployed`, `7 = VSC ending`.
So `is_safety_car_lap` is SC **∪ VSC**, and `is_vsc_lap` is **red flag** — it never
identifies a single VSC lap.

This is already known in the repo. `stg_track_status.sql:29-32` carries the correct
decode *and an explicit note*:

> `(Note: this corrects the stale comment in stg_laps, which has 5/6/7 mislabelled; the FastF1 truth is 5=Red, 6=VSC, 7=VSC-ending.)`

The **comment** in `stg_laps` was flagged as stale; the **regex** was never fixed. So the
layer now holds two contradictory decodes: `stg_track_status` (correct, feeds
`int_sc_hazard_history`) and `stg_laps` (wrong, feeds everything else).

Measured over all 162,729 race laps:

| FastF1 truth | `is_safety_car_lap` | `is_vsc_lap` | n laps |
| :--- | :--- | :--- | ---: |
| SC only | true | false | 8,398 |
| VSC only | **true** | false | 2,712 |
| SC + red | true | true | 278 |
| SC + VSC | true | false | 251 |
| red only | false | **true** | 131 |
| VSC + red | true | true | 17 |

Totals: 8,927 genuine SC laps, 2,980 genuine VSC laps, 426 red-flag laps.
`is_safety_car_lap` fires on 11,656 laps of which **2,980 (25.6%) are VSC, not SC**.
`is_vsc_lap` fires on 426 laps, **all 426 of them red flags, none of them VSC**.

**Why the damage is currently limited:** every consumer I checked uses the two flags
*together* — `int_event_corrections` assigns both `correction_class = 'neutralisation'`
and `correction_weight = 0.0`; `mart_degradation_history_envelope` and
`mart_corner_skill_driver` both filter `NOT is_safety_car_lap AND NOT is_vsc_lap`;
Phase A3 zeroes dirty air on either. The union of codes 4/5/6/7 is the correct
"neutralised lap" set, so the combined usage is right *by accident*.

**Why it still matters:**
- `fct_lap_residuals` exports both columns to the Power BI dashboard, where they are
  read as their names claim. Every VSC lap there is labelled a safety car.
- Red-flag laps have no flag of their own anywhere at lap grain. A red flag is a full
  stoppage — tyres go to ambient and can legally be changed — which is physically the
  opposite of a VSC lap, and is exactly the event `int_lap_thermal_proxy`'s EWMA should
  hard-reset on rather than decay through. (`stg_session_status.is_red_flag_stop` is
  staged for this and unused — see the inventory below.)
- Any future model that wants to treat SC and VSC differently (they have very different
  pace and thermal profiles) silently cannot.

**Fix:** `is_safety_car_lap → '.*4.*'`, `is_vsc_lap → '.*[67].*'`, add
`is_red_flag_lap → '.*5.*'`, in both `stg_laps` and `stg_laps_qualifying`. Every
consumer that currently writes `is_safety_car_lap OR is_vsc_lap` must become
`... OR is_red_flag_lap` in the same change, or 426 red-flag laps silently re-enter the
clean set. `is_valid_lap` itself is unaffected — it already tests `'.*[4567].*'`.

---

## 3. `race_to_track` keys on event name, not physical venue

The seed maps `race_id → track_id` where `track_id` is the *event* name. Four physical
circuits are therefore split across two ids:

| Physical circuit | track_id A (races) | track_id B (races) |
| :--- | :--- | :--- |
| Autódromo Hermanos Rodríguez | `mexican_grand_prix` (2) | `mexico_city_grand_prix` (4) |
| Interlagos | `brazilian_grand_prix` (2) | `são_paulo_grand_prix` (4) |
| Red Bull Ring | `austrian_grand_prix` (7) | `styrian_grand_prix` (2) |
| Silverstone | `british_grand_prix` (7) | `70th_anniversary_grand_prix` (1) |

(`sakhir_grand_prix` vs `bahrain_grand_prix` is **not** in this list — that one is a
genuinely different layout, and `dim_circuits` correctly gives it
`bahrain_international_circuit_outer`.)

**The correct mapping already exists** — `dim_circuits.circuit_id` resolves both Mexico
keys to `autodromo_hermanos_rodriguez`, both Brazil keys to
`autodromo_jose_carlos_pace`, and so on. It is simply not the key anything pools on.
`mart_degradation_history_envelope` already groups by `circuit_id`; the cliff-seed
solver and everything else group by `circuit_key` (= `race_to_track.track_id`).

The cost, visible in the current `compound_cliff_params`:

| circuit_key | rows | total stints | fit sources |
| :--- | ---: | ---: | :--- |
| `mexican_grand_prix` | 3 | 46 | cox_km_survival, **compound_class_default** |
| `mexico_city_grand_prix` | 12 | 280 | cox_km_survival, cross_season_fallback |
| `brazilian_grand_prix` | 5 | 88 | cox_km_survival, **compound_class_default** |
| `são_paulo_grand_prix` | 10 | 305 | cox_km_survival, cross_season_fallback, compound_class_default |
| `70th_anniversary_grand_prix` | 3 | 61 | cox_km_survival, **compound_class_default** |
| `styrian_grand_prix` | 6 | 114 | cox_km_survival, cross_season_fallback |

The A-side keys fall through to generic compound-class defaults because, as far as the
solver is concerned, they are one- or two-season circuits with nothing to pool against —
while the same tarmac sits under a different name with 280–305 stints of history. This
is the *same failure mode* the `race_to_track` join fix addressed (isolated keys
cascading to class defaults), just from a different cause, and it survived that fix.

**Fix:** pool on `dim_circuits.circuit_id` rather than `race_to_track.track_id` in
`fit_compound_cliff.py`'s `load_stint_data` and anywhere else grouping by `circuit_key`
for a cross-season fit. Seed-refit cascade risk applies exactly as it did for A4/B/C.

---

## 4. Corner-skill chain covers 17 of 36 tracks; FastF1 corner geometry is staged and unused

`dim_corners` is a hand-curated seed: **193 corners across 17 track_ids**. It is the sole
input gate on `int_corner_metrics` (INNER JOIN), which measures 17 tracks — and therefore
so do `int_corner_skill_residuals`, `mart_corner_skill_driver`, and
`fct_telemetry_deltas`.

Meanwhile `stg_circuit_info` stages FastF1's own corner table — `corner_number`,
`corner_letter`, `corner_x`, `corner_y`, `corner_angle_deg`, `corner_distance_m` —
covering **2,378 corners across 143 race-sessions**, with **zero downstream references**
to any of those six columns. This is the `FreshTyre` pattern exactly: already ingested,
already staged, already documented, consumed by nothing.

The 19 track_ids with no corner coverage today:

> 70th_anniversary, australian, azerbaijan, chinese, eifel, emilia_romagna, german,
> hungarian, las_vegas, mexican, miami, portuguese, qatar, russian, sakhir,
> saudi_arabian, styrian, turkish, tuscan

That includes Hungary, Australia, Azerbaijan, Saudi Arabia, Miami, Las Vegas and Imola —
a large fraction of the modern calendar, and every high-corner-count street circuit
where corner skill is most separable.

**Fix:** derive `dim_corners` from `stg_circuit_info` (window each corner as
`corner_distance_m ± brake/exit margin`) instead of maintaining it by hand, keeping the
seed only as an override for circuits where the FastF1 geometry is known bad. Note
`int_corner_metrics` joins on `track_id` while `stg_circuit_info` is keyed per
`race_id` — so finding #3 has to be settled first, or the derived dimension inherits the
same venue-splitting.

---

## 5. `int_pit_loss_circuit` was built to replace a constant, and never wired to it

The model's own header:

> Empirical circuit-specific pit-lane loss prior, **to replace the largely-imputed
> constant (`circuit_reference.pit_lane_loss_s`, default 21 s) used by
> `int_pit_strategy_value`**.

`int_pit_strategy_value` does not reference it. It still reads
`COALESCE(CAST(cr.pit_lane_loss_s AS DOUBLE), 21.0)` from `circuit_reference`
(lines 88–93, 319). Nothing in `models/`, `scripts/`, `ml/`, or `app/` refs
`int_pit_loss_circuit` — it is a materialized table with no consumers.

What that leaves unused:

| Source | n circuits | range (s) | mean (s) |
| :--- | ---: | :--- | ---: |
| `circuit_reference.pit_lane_loss_s`, measured | 36 | 19.0 – 24.0 | 20.83 |
| `circuit_reference.pit_lane_loss_s`, imputed | 8 | all exactly 21.0 | 21.00 |
| `int_pit_loss_circuit.pit_loss_s_empirical` | 36 | **15.98 – 30.37** | 22.72 |

The empirical estimate has ~3× the dynamic range of the constant in use, off a median of
203 real stops per circuit, and 8 circuits are currently pinned at a flat 21.0s.
`pit_lane_loss_s` drives `undercut_threat_lap` and the strategy cost model, so the
flattening is not cosmetic. Fix #6 before wiring it.

---

## 6. SC-affected stops pollute the empirical pit loss

`int_pit_loss_circuit`'s header states:

> Stops under SC/VSC or with anomalous laps are filtered by a sane [8, 60] s window
> before aggregation

The `[8, 60]` window is the *only* filter — `clean_stops` tests `time_lost_s` and
nothing else. There is no SC/VSC condition anywhere in the model. Under a full SC the
in-lap and out-lap are slow enough that `time_lost_s` usually exceeds 60s and gets
dropped incidentally, but a large minority survive:

| Regime | all stops | surviving [8,60] filter | median kept `time_lost_s` |
| :--- | ---: | ---: | ---: |
| SC-affected | 1,566 | **674** | **41.76 s** |
| green | 7,070 | 6,634 | 21.25 s |

674 of the 7,308 surviving stops (9.2%) are SC-affected and carry a median measured loss
of 41.8s — nearly double the green-flag 21.3s. They are pulled straight into the
per-circuit `MEDIAN(time_lost_s)`, which is why the empirical mean (22.72s) sits above
the measured constant (20.83s).

Note the regime split reads "SC" not "VSC" only because of finding #2 — with the flags
corrected, some of those 674 will reclassify as VSC. Both should be excluded.

**Fix:** add `AND NOT is_safety_car_lap AND NOT is_vsc_lap AND NOT is_red_flag_lap` on
both the in-lap and the out-lap in the `stops` CTE, so the header becomes true.

---

## 7. `stg_pits.pit_duration_s` is structurally broken

```sql
CASE WHEN pit_in_time_s IS NOT NULL AND pit_out_time_s IS NOT NULL
     THEN pit_out_time_s - pit_in_time_s END AS pit_duration_s
```

The `pit_laps` CTE selects lap rows where `pitintime OR pitouttime` is non-null. For a
normal stop those two timestamps live on **different lap rows** — `PitInTime` on the
in-lap, `PitOutTime` on the following lap — so the `AND` almost never holds:

```
10,319 rows · 10,075 NULL (97.6%)
non-null: median −116.85 s   p05 −167.27 s   p95 −90.50 s
```

Every one of the 244 rows where it does fire is **negative**, because on those rows the
`PitOutTime` belongs to the *previous* stop's exit (start of lap) and `PitInTime` to the
current entry (end of lap), so the subtraction runs backwards.

Also unverified in the same model: `pit_out_lap_number` is hardcoded as
`lap_number + 1`, never checked against the row that actually carries `PitOutTime`.

Nothing consumes the column, so nothing is currently wrong downstream — but it is
precisely the measurement #5 and #6 want, and it is documented in `schema.yml` as if it
worked. Either fix it (`LEAD(pit_out_time_s) OVER (PARTITION BY race_year, race_id,
driver_id ORDER BY lap_number)`) or drop it; leaving a 97.6%-NULL, wrong-signed column
staged and documented is the trap.

---

## App data is two months stale (found during Phase 1, unrelated to it)

`make app-data-check` — the CI drift gate — **fails at clean `HEAD`**, verified by
stashing all Phase 1 work and running it against an untouched tree. The committed
`app/public/data/**` was last exported on **2026-06-24**; the warehouse has moved
several times since.

Only four paths are tracked (`app/.gitignore` excludes `facts/`, `intermediates/`,
`dimensions/`, and loose `ml/*.parquet`), and two of them are materially wrong:

| Tracked artifact | Committed state | Warehouse state |
| :--- | :--- | :--- |
| `ml/mart_degradation_predictions/*.parquet` | model **v3**, `predicted_at` 2026-06-13 | model **v4**, `predicted_at` 2026-07-06 |
| `marts/mart_corner_skill_driver/*.parquet` | 6 columns missing | has `braking/mid/exit_skill_se_s` + `*_cells_n` |
| `marts/mart_degradation_history_envelope.parquet` | stale | rebuilt |
| `_manifest.json` | stale hash | — |

The degradation predictions are the significant one: **the shipped app has been serving
v3 predictions since the repo moved to v4 in late June**. Across 2023 the two versions
differ by a mean absolute 0.296 s and up to 5.26 s on `predicted_degradation_jump_s`,
and every probability band (`prob_0_to_2` … `prob_none_in_stint`) shifts with it.

This is the same defect class the audit hunts — an artifact built to be replaced and
never re-cut. It was deliberately **not** folded into Phase 1: re-exporting is a
one-command fix (`make app-data`) but it ships regenerated ML predictions, which is a
much larger change than a decode fix and deserves its own review. Phase 1 reverted the
tracked parquet to keep the diff focused.

**Fix:** run `make app-data`, review the prediction delta, commit separately.

---

## Smaller items

**`int_lap_residual_decomposed_qualifying.weather_proxy` — the third instance of the
`DISTINCT ON` anti-pattern.**

```sql
SELECT DISTINCT ON (race_year, race_id) ... FROM int_track_evolution
ORDER BY race_year, race_id          -- no tiebreaker
```

Same shape as the two fixed on 2026-07-30 in `int_compound_cliff_predicted` and
`int_track_evolution`, and it was missed because it dedupes on a 2-column key rather
than 3. I swept threads 1/2/3/4/6/8 and got an identical result set each time — reading
a materialized table is stable in a way the earlier ASOF-join pipeline was not — so this
is not currently flaky. It is still unpinned by contract, and it has a semantic problem
independent of determinism: `int_track_evolution` is per-lap, so this takes *some
arbitrary race lap's* rubber and ambient state as the qualifying track-state proxy.
Measured, the picked lap ranges **3 to 50 (mean 8.1)** across 147 races, against a
within-race spread of up to 1.76s rubber / 2.00s ambient. Pick a defined lap (earliest
available, which is what it happens to return today) and say so in the ORDER BY.

**`int_qualifying_decomposed` publishes a driver-race aggregate at lap grain.**
`quali_skill_session_avg_s` is constant per driver-race but emitted on every lap row.
The app then does `AVG(q.quali_skill_session_avg_s) ... GROUP BY q.driver_id`, which
weights each race by how many qualifying laps that driver ran — and the same fan-out
applies to the `fct_driver_skill_features` join beside it. That specific query is app-side,
but the grain mismatch that invites it is a transform-layer choice.

**Unused staged signals** (the `FreshTyre` sweep, re-run across all staging models;
surrogate keys and provenance columns excluded):

| Column | Note |
| :--- | :--- |
| `stg_session_status.is_red_flag_stop` | red-flag stoppages — the reset event finding #2 leaves unrepresentable |
| `stg_track_status.status_duration_s` | how long each SC/VSC/red period lasted; currently every neutralised lap is treated as equivalent |
| `stg_track_status.is_safety_car` / `is_vsc` / `is_red_flag` | the *correct* decode, sitting unused next to the wrong one in `stg_laps` |
| `stg_results.grid_position` | starting position — the direct determinant of first-stint traffic exposure, relevant to the Phase C dirty-air work |
| `stg_results.classified_position`, `time_or_gap_s` | unused |
| `stg_circuit_info.corner_*` (6 cols) | ✅ consumed since Phase 5 — `corner_number`, `corner_letter` and `corner_distance_m` build `dim_corners`; `corner_x` / `corner_y` / `corner_angle_deg` remain unread (`int_track_geometry` derives its own X/Y from raw telemetry) |
| `stg_tyre_allocations.allocated_sets_per_driver` | set availability constrains strategy; `int_pit_strategy_value` assumes unconstrained |
| `stg_pits.compound_out`, `pit_out_time_s`, `pit_duration_s` | see finding #7 |
| `stg_sector_times.sector_session_time_s` | unused |
| `stg_weather.ambient_temp_c` | unused in `models/`; read by external scripts |

**Checked and clean** (recorded so a later pass doesn't redo them): every model appears
in a `schema.yml` with documented columns; no orphan/undocumented models; divisions are
NULLIF-guarded or provably non-zero except `int_sc_hazard_history`'s `/ c.racing_laps`
(no circuit currently has zero); `int_lap_anomaly_flags` produces 0 NULL and 0
non-finite z-scores across 137,447 rows; `int_constructor_car_fe`, `int_track_geometry`,
`int_lap_normalized_pace` are deliberate graph leaves, not dead models.

---

## Suggested sequencing

Findings #2 and #3 are corrections that other work sits on top of, so they go first;
both also change values that cascade into the cliff seed, and doing them together means
one refit rather than two.

1. **#2 — SC/VSC/red decode.** Self-contained staging fix plus a mechanical sweep of the
   7 consumers that pair the two flags. Add a test asserting the three flags partition
   codes 4/5/6/7 exactly. No seed refit needed (the neutralised *union* is unchanged, so
   `correction_weight` and every `NOT sc AND NOT vsc` filter keep their current row set —
   worth verifying rather than assuming).
2. **#3 — venue identity.** Repoint cross-season pooling at `dim_circuits.circuit_id`.
   Cliff-seed refit + the usual gate re-run; expect the four A-side keys to move off
   `compound_class_default`.
3. **#1 — qualifying push-lap gate.** The largest single correctness win and independent
   of 1–2. Needs the Q1/Q2/Q3 split (1c) scoped first; that determines whether the
   baseline fix is per-segment or per-session.
4. **#7 → #6 → #5 — the pit-loss thread.** Fix the duration column, exclude neutralised
   stops, then wire `int_pit_loss_circuit` into `int_pit_strategy_value` and retire the
   flat 21.0s fallback for the 8 imputed circuits.
5. **#4 — corner coverage.** Largest new-code item; depends on #3 for the venue key.
   Roughly doubles the track coverage of the corner-skill mart.

Two notes carried over from `PLAN.md` that apply to all of the above: any change touching
the cliff seed cascades into `mart_degradation_predictions` and the v4 ONNX feature
distribution, and the gate metrics should be re-measured before each phase rather than
compared against a stored number (Phase C found a stale baseline that way).

---

## Checkpoint

- 2026-07-30: Audit written. Nothing implemented.
- 2026-08-22: Re-verified all 7 findings against the working tree — all still open.
  Added the Implementation Checklist above. Reconciled `PLAN.md` with git (Phase C had
  shipped in `bd0ce6b` on 2026-08-03; its last two boxes were never ticked) and reverted
  a stray whitespace edit in `ingestion/src/ingest.py`.
- 2026-08-22: **Phase 1 (#2, SC/VSC/red decode) implemented.** `is_safety_car_lap` now
  decodes digit 4 only, `is_vsc_lap` digits 6/7, and a new `is_red_flag_lap` carries
  digit 5 — matching `stg_track_status`, which had held the correct decode since it was
  written and whose note about the "stale comment in stg_laps" was itself the clue that
  the regex had never been fixed.

  The finding called this a mechanical staging fix. It was not quite: because every
  consumer paired the flags as `sc OR vsc`, and because the *old* pairing happened to
  span codes 4/5/6/7, correcting the decode in isolation would have silently dropped
  426 red-flag laps out of the neutralised set — turning a labelling bug into a real
  data-quality regression. Every consumer therefore had to gain `is_red_flag_lap` in the
  same change to hold the row set constant. That is what the verification above is
  checking, and the union does come out unchanged at 11,787 laps.

  Two things the audit's consumer list did not include, found by grepping outside
  `models/`: the app's `lap-waterfall` and `race-lost` queries and
  `scripts/analyze_race_case_study.py` filter on `NOT is_safety_car_lap` *alone*. Under
  the broken decode that expression meant "not SC and not VSC"; after the fix it would
  have meant "not SC" only, admitting every VSC lap into the race-pace waterfall. All
  three now filter the full three-flag set. Because `app/public/data/**` is committed
  parquet, this also required an `app-data` re-export so the shipped data carries the
  new column — verified by running the app's own filter against the regenerated
  `fct_lap_residuals` parquet.

  Red-flag laps now have a flag of their own at lap grain for the first time, which is
  the prerequisite the audit noted for representing a full stoppage (tyres to ambient,
  changes permitted) as distinct from a VSC lap. Nothing consumes that distinction yet —
  `int_lap_thermal_proxy`'s EWMA still treats a red flag exactly like any other
  neutralised lap. That is a genuine follow-up, not part of this fix.

- 2026-08-22: Re-snapshotted the byte-stability oracle baseline, folding in Phases B/C
  (committed `bd0ce6b`) and Phase 1 (this session, uncommitted) in one pass, as the
  checklist anticipated. Rebuilt `ci.duckdb` from the current working tree
  (`dbt build --target ci`, PASS=565 ERROR=0), then wrote a new baseline for 60 models.
  Pre-snapshot `--check` reported the expected shape: 6 of 7 `fct_*` models drifted
  (all but `fct_ghost_race_finish`, a CI no-op), 2 new models
  (`int_lap_normalized_pace`, `int_track_geometry`) absent from the Jul-30 baseline, and
  28 non-mandatory upstream models changed — consistent with three phases of committed
  and pending logic changes, not a surprise. Post-snapshot `--check` is clean. Phase 1's
  "User sign-off" checklist item is still open — this only clears the oracle item.

- 2026-08-22: Found while verifying Phase 1's app-side sweep: the committed app data is
  two months stale and its CI drift gate already fails at clean `HEAD` (proven by
  stashing every Phase 1 change and re-running it). The live app is serving **v3**
  tyre-degradation predictions while the repo has been on **v4** since late June.
  Written up as its own finding above rather than folded into Phase 1 — the fix is one
  command, but it ships regenerated ML predictions and should be reviewed on its own.

- 2026-08-22: **Phase 2 (#3, venue identity) implemented.** `fit_compound_cliff.py`'s
  `load_stint_data` now joins `race_to_track.track_id → dim_circuits.circuit_key` to
  resolve `dim_circuits.circuit_id` alongside the existing event-slug `circuit_key`; the
  cross-season fallback pool in `run_fit` now groups by `circuit_id` when one resolves
  (falling back to `circuit_key` only for the one known race_to_track gap). Emitted rows
  are still keyed on `circuit_key`, so `int_compound_cliff_predicted`'s join to
  `race_to_track.track_id` needed no change. Refit and promoted
  (`make coefficients-promote`): 403 rows, 16 changed, `compound_class_default` count
  22 → 19. Verified against the finding's own prediction — `mexican_grand_prix SOFT
  2019`, `brazilian_grand_prix HARD 2019`, and `70th_anniversary_grand_prix SOFT 2020`
  all moved off `compound_class_default` onto `cross_season_fallback`, now pooling with
  `mexico_city_grand_prix` / `são_paulo_grand_prix` / `british_grand_prix`'s history; the
  three `austrian_grand_prix SOFT` fallback rows kept their source but grew from a
  47-stint pool to 72 by picking up `styrian_grand_prix`.

  **Sweep turned up two more instances of the same defect** beyond the fitter script,
  which the user confirmed folding into this phase rather than deferring:
  - `int_driver_circuit_affinity` (driver × circuit affinity) pooled on `circuit_key`;
    grain changed to `(driver_id, circuit_id)`, now emitting `circuit_id` + `circuit_name`
    directly (same pattern already used by `int_driver_circuit_era_affinity`). Row count
    998 → 918 as the four venue-split pairs merged. App feature
    `driver-circuit-affinity` updated to read `circuit_id`/`circuit_name` straight off the
    model instead of joining `dim_circuits` itself; `assert_affinity_shrinkage_bounds.sql`
    updated to match.
  - `int_circuit_x_constructor_interaction` (constructor × circuit interaction) pooled its
    shrinkage on `circuit_key`; fixed to pool on `circuit_id` while leaving the model's
    output grain `(race_year, race_id, constructor_id)` and its `circuit_key` column
    unchanged, so the `constructor-circuit-interaction` app feature needed no change.
    Verified e.g. Ferrari's and Alfa Romeo Racing's `circuit_constructor_interaction_s`
    now come out identical for `mexican_grand_prix` and `mexico_city_grand_prix` rows
    (previously fit as two independent, thinner cells).

  Gates: `dbt build` clean on both `dev` (PASS=204 for the targeted rebuild, then
  PASS=566 for a full rebuild after the seed refit) and `ci` (PASS=567 ERROR=0
  TOTAL=570) targets. The repo's `scripts/snapshot_model_hashes.py` byte-stability
  oracle OOMs on this machine regardless of these changes (`fct_telemetry_deltas` alone
  is 10.6M rows and its `string_agg`-based hash needs more memory than is free here) —
  a pre-existing tooling limitation, not something this phase caused. Verified propagation
  manually instead with a memory-light `SUM(hash(t))` sweep over every model that could
  plausibly be touched: `int_driver_circuit_affinity` and everything downstream of
  `int_circuit_x_constructor_interaction` (`int_lap_residual_decomposed`,
  `fct_lap_residuals`, `fct_ghost_car_pace`, `fct_cliff_prediction_features`,
  `int_constructor_deg_sensitivity`) changed as expected; `int_driver_circuit_era_affinity`
  (already correct before this phase), `int_driver_race_skill_loro`, `int_synthetic_teammate`,
  `int_pit_strategy_value`, and `dim_compounds_season` came out byte-identical, as they
  should since none of them touch the fixed pooling keys.
  `make docs-reference` and `make docs-coverage-check` both clean after regenerating
  (`transform-inventory*.mdx` and the two models' reference pages). App `tsc --noEmit`
  clean; `driver-circuit-affinity`'s vitest suite passes (6/6). Neither changed
  intermediate model's parquet is git-tracked (`app/.gitignore` excludes
  `intermediates/`), so no app-data re-export was needed for this phase.

  Not done, and intentionally out of scope: this phase did **not** re-run the
  compound-cliff-dependent downstream chain's own consumers beyond what `dbt build`
  already covers (e.g. `mart_degradation_predictions` / the v4 ONNX feature
  distribution) — per the carried-over note at the top of this checklist, that refit
  should be measured fresh if and when that chain is touched next, not assumed stable
  from this session's numbers.

- 2026-08-22: **Phase 3 (#1, qualifying push-lap gate) implemented.** The finding's own
  first step — "recover Q1/Q2/Q3 from bronze" — turned out not to be possible: bronze
  held qualifying *laps* and nothing else. `session_status`, `track_status` and `results`
  were all written for race sessions only, and the `Q1`/`Q2`/`Q3` columns on the race
  results are NULL for all 2,979 driver-races across the seven seasons, because FastF1
  populates them only on the qualifying session's own results. So the phase started one
  layer lower than planned: `ingest.py`'s three writers gained the `session_type`
  parameter `_write_weather` already had, and all 149 qualifying sessions were backfilled
  from the FastF1 cache. Bronze is gitignored and reproducible, and the re-ingest was
  proven content-neutral for the lap files by diffing against the committed CI fixtures,
  which predate it.

  **Recovering the segments was the hard part, and each simplification failed on a real
  session.** Counting the three `Finished` events fails on the 10 sessions whose final
  segment was red-flagged to a close — the chequered flag never falls and Q3 folds into
  Q2. Counting green lights instead fails because a red flag inside a segment produces
  another one. Treating a green preceded by `Aborted` as a resumption fails on 2019 Spa,
  whose Q1 was red-flagged *to a close*, so its next green opens Q2 rather than resuming
  Q1. What works is anchoring the status timeline to the official per-driver segment
  times: match each official time back to the lap that set it, and those laps bracket
  where each segment can open. Inside that bracket the last chequered flag decides, and
  where there is none, the last green does. Two more sessions pinned down the exact
  bounds of that search — 2022 Montreal, which writes Q2's interruption as a second
  Started/Finished pair rather than an Aborted, and 2024 Interlagos, five red flags in
  changing wet conditions.

  Verified against the official results rather than against itself: of 6,581 official
  segment times that match a lap, **6,578 were set inside the segment we assigned**. The
  3 failures are FastF1 copying a driver's Q3 time into their Q2 column, confirmed by
  hand on ALB, PIA and ALO at Interlagos — the source column is wrong, not the
  assignment. That check is now `assert_quali_segment_matches_official`. Independent
  corroboration: the median recovered segment spans come out at exactly 1080s, 900s and
  720s, the regulation durations, which nothing in the derivation was told.

  What the gate then bought, measured on `dev`:

  | | before | after |
  | :--- | ---: | ---: |
  | laps feeding the decomposition | 18,943 | 14,165 |
  | of those, >107% off the segment best | 25.5% | 0.3% |
  | `quali_pace_delta_s` p95 | +36.56s | +1.66s |
  | laps over +10s / +30s | 3,902 / 1,629 | 14 / 5 |
  | `quali_driver_skill_residual_s` mean absolute | 7.04s | 0.76s |
  | its σ | 13.13s | 1.33s |

  A real qualifying field spreads over ~1–3s, so the skill term is now measuring
  something. The residual 0.3% above the cut are the driver's-own-best carve-out, which
  keeps every driver represented in a wet Q1; 43 laps of 14,165, and
  `ratio_to_segment_best` is exposed so a consumer can be stricter.

  `int_constructor_structural_pace_qualifying` was fixed in the same pass. The finding
  does not name it, but it computed its own `field_pace` with the identical
  session-median-over-polluted-laps defect and feeds `constructor_component_s` straight
  into the identity, so leaving it would have left the bug in the chain. Its deltas are
  now re-centred within each segment before pooling, because Q2 and Q3 are progressively
  self-selected fields.

  Found while validating, not fixed here, and worth its own look: **2018 qualifying laps
  are 26% `is_accurate = false`** (704 of 2,669 timed non-pit laps) against ~0.2% in every
  other season, and three 2018 sessions — Rd1, Rd7, Rd8 — have *zero* valid Q1 laps as a
  result, so their Q1 contributes nothing to the decomposition. That is a pre-existing
  staging consequence of the 2018 bronze data, unchanged by this phase (the push gate
  drops nothing further there), but it means 2018 Q1 is effectively missing from the
  qualifying chain.

  Also noted, not touched: `make lint` currently fails on 8 models in this working tree
  (`int_compound_cliff_predicted`, `int_driver_circuit_affinity`,
  `int_driver_circuit_era_affinity`, `int_stint_geometry`, `int_track_evolution`,
  `int_track_geometry`, `fct_ghost_car_pace`, `mart_corner_skill_driver`) — long lines,
  ambiguous `ORDER BY`, an unqualified reference, indentation. All are cosmetic, all come
  from the earlier uncommitted phases, and lint is clean at `HEAD`, which is how I know
  they are not from this one. Phase 3's own models pass.

- 2026-08-22: **Phase 4 (#7 → #6 → #5, the pit-loss thread) implemented.** All three
  findings were real, all three were understated, and the two extra defects found while
  measuring turned out to matter more than the ones the audit named.

  **The grain was the bug.** `stg_pits` claimed "one row per pit stop" and was one row
  per *pit lap*. Bronze splits a stop across two lap rows — `PitInTime` on the in-lap,
  `PitOutTime` on the out-lap — and the model emitted both, plus 107 pit-lane race
  starts: 10,319 rows for 5,336 stops. That is what made `pit_duration_s` 97.6% NULL and
  negative on the 244 rows where it fired, which is finding #7. But it also meant
  `int_pit_loss_circuit`, which never filtered on `pit_in_time_s`, admitted every
  out-lap row as a stop keyed one lap late. **3,577 of its 7,308 "clean stops" — 48.9% —
  were phantom**, measuring `(out_lap + the lap after it)` against a green baseline, and
  carrying a median 19.19 s against 23.64 s for the real ones. Finding #6's 674
  SC-affected stops (9.2%) were the smaller half of the contamination by a factor of
  five, and they pulled in the opposite direction: with both removed the mean per-circuit
  estimate goes *up*, 22.72 → 23.57 s, not down.

  Finding #3's venue-identity bug was in this model too, unnoticed by the audit that
  found it elsewhere. It pooled on `race_slug`, so Silverstone estimated twice —
  `british_grand_prix` at 22.76 s off 297 stops and `70th_anniversary_grand_prix` at
  19.29 s off 82 — a 3.5 s spread on one physical pit lane, with the thin half then
  shrunk hard toward the global median for a sample size that only exists because the
  event was renamed. Same for Interlagos, Mexico City and the Red Bull Ring. Now
  estimated per `dim_circuits.circuit_id` and emitted per event slug, which is the shape
  Phase 2 used for the cliff fitter, so the consumer's `race_to_track` join is unchanged.

  Third defect in `stg_pits`, not in the audit and unconsumed today: `compound_out` was
  read off the in-lap, so it named the tyre being *removed*. Wrong on 3,844 of 5,109
  stops, and documented in `schema.yml` as if it were the tyre fitted — the same
  "staged, documented, wrong" trap as the duration column. Split into `compound_in` and a
  correct `compound_out`.

  **#5's wiring moves less than the finding implies, and the measurement says why.**
  `int_pit_strategy_value` now reads `pit_loss_s_shrunk` (user-chosen full replacement,
  seed then 21.0 as fallback, `pit_loss_source` recording which), and the undercut-threat
  scan's hardcoded `min_gap_s < 22.0` became `< pit_lane_loss_s + 1.0`, which is what its
  own comment already claimed. Against a pre-change snapshot of all 7,129 stints:
  `pit_lane_loss_s` changed on 7,094, `undercut_threat_lap` on 37, `opportunity_cost_s`
  on 1, and `strategy_verdict` on **zero** — so `fct_stint_features.pit_decision_class`
  is byte-identical and nothing reaches the ML feature set. The oracle confirms this
  independently: all 7 `fct_*` byte-stable, only the three changed models drift.

  The reason is worth recording, because it is the next real finding in this family: the
  optimal-pit-lap search never consumed pit loss at all. The model header writes down a
  proper `Total_Cost(L)` minimisation, then the SQL approximates the argmin as "first lap
  in the cliff window where expected wear exceeds 0.5 s" — a threshold with no pit-loss
  term in it. A longer pit lane still does not push the modelled optimum later, which it
  physically must. Wiring the empirical value in was the right fix and makes the
  displayed number and the undercut window correct; making it *matter* means solving the
  real minimisation, which is a rewrite of the model's core rather than a join. Recorded
  in `strategy.mdx` under "Other approaches".

  Two things noted, not fixed. `2018_14` is the one race in seven seasons that falls back
  to the flat 21.0 s: its `race_to_track` row has a NULL `track_id`, a pre-existing seed
  gap Phase 2 already knew about, affecting 35 stints. And `strategy_verdict`'s
  distribution is lopsided in a way that predates all of this — 1,893 `overran`, 2,231
  `unknown`, 2,992 NULL, and 8 `optimal` across seven seasons. A verdict that fires
  "optimal" eight times in 7,129 stints is not measuring what its name says; that is its
  own finding, and the 0.5 s threshold above is the likely cause.

  Process note: my first CI run was `dbt build --target ci` without
  `--vars bronze_base=.../fixtures/bronze`, which is a full-data build into
  `ci.duckdb`, not the fixture gate — it overwrote the fixture warehouse the oracle
  baseline is cut against and made all 7 `fct_*` read as drifted with ~50× the baseline
  row counts. `make test-all` is the fixture gate and was re-run; the oracle result above
  is from the rebuilt fixture warehouse. The 8-model `make lint` failure set carried over
  from earlier phases is unchanged — the five files this phase touched are clean.

- 2026-08-22: **Phase 5 (#4, corner coverage) implemented — the last of the seven.**
  The finding was that `dim_corners` covered 17 of 36 event slugs while FastF1's own
  corner table sat staged and unread in `stg_circuit_info`. Both halves were true, and the
  half the audit did not check turned out to matter more: the seed was not thin geometry,
  it was **not geometry at all**. Its 193 rows are a uniform tiling of 250–500 m blocks
  abutting one another, with corner counts unrelated to the layouts (Monza 8 for 11 turns,
  Monaco 12 for 19, Abu Dhabi 9 for 16). At Bahrain the block it calls `Turn_2`
  (700–1050 m) contains FastF1's turns 1, 2 and 3, whose apexes are at 717, 819 and 941 m.
  So the 17 "covered" slugs were being measured against blocks with the wrong names in the
  wrong places, and keeping the seed as an override — the plan as written — would have
  preserved exactly that. It is deleted instead, with the reasoning in the model header.

  `dim_corners` is now a reference model keyed **per race**, and `int_corner_metrics`
  joins it on `race_id`. Per race rather than per venue because FastF1 publishes the table
  per event and venues re-profile mid-history — Abu Dhabi 21→16 corners, Singapore 23→19,
  Barcelona 16→14 — while the distance origin shifts between seasons at São Paulo and
  Baku, the same discontinuity `int_track_geometry` documents in the X/Y frame. Pooling
  seasons would blur both, and keying per race dissolves finding #3's venue-identity trap
  rather than inheriting it: nothing pools across slugs at all. A race with no corner table
  of its own borrows the nearest season of the same slug (4 races) and records it in
  `geometry_source`; 2020 Sakhir and Tuscan are one-offs with no sibling event and stay
  uncovered, 2 races of 149.

  The window is the apex ± documented margins, each end clipped at the neighbouring apex.
  Both margins were calibrated from telemetry, not chosen: braking zones on corners with a
  clear 600 m approach run p50 119 m / p95 181 m / p99 232 m, so entry is 250 m; of the
  cells that reach full throttle before the next apex, 96.7% do so within 150 m of it, so
  exit is 150 m. The geometry itself was validated before anything was built on it —
  against a 10 m-binned median speed trace, the FastF1 apex sits a median **2 m** from the
  measured speed minimum on the 1,586 unambiguously slow corners, and no venue's median
  offset exceeds 54 m. Monaco's slowest corner comes out as `Turn_6` at 42 km/h (the
  Fairmont hairpin) and Monza's fastest as `Turn_3` at 254 km/h (Curva Grande).

  Two corrections fell out of the window change. `throttle_point_m` was `MAX(distance at
  100% throttle)` over the block, which under abutting blocks measures the lift for the
  *next* corner and sat within 20 m of the block boundary on 41% of cells; the docs
  meanwhile describe it as the "throttle-application point … positive = gets on power
  later". It is now the first full-throttle sample at or after the apex. And dropping
  `race_to_track` from the join recovers 2018_14, the one race missing from that seed,
  which had been silently absent from the entire corner chain.

  **The defect worth recording is in the mart, and it was not in the audit.**
  `mart_corner_skill_driver` winsorises each (driver, race, corner) cell with
  `GREATEST(-1.0, LEAST(1.0, driver_mean − loro))`. DuckDB's `LEAST` and `GREATEST` ignore
  NULL arguments rather than propagating them, so `LEAST(1.0, NULL)` is `1.0`: every corner
  with no braking zone, or no point where full throttle returns, entered the season mean as
  the **maximum possible penalty** instead of as no observation. The symptoms were all
  visible in the published table and none of them had been read as symptoms — every
  phase's cell count identical to `mapped_corners`, no `z` ever withheld by the 30-cell
  floor the model documents at length, and every driver's `corner_skill_index` positive in
  every season, with phase means of +0.09 to +0.35 against `mid_corner`'s exactly 0.000
  (the one phase that has no NULLs). Fixing the windows raises the exit-phase NULL rate, so
  shipping coverage without this fix would have deepened the bias. Guarded explicitly; all
  three phase means now read 0.000 in all seven seasons, and the phase gate withholds a
  driver for the first time (2 of 20 in 2019).

  Coverage, re-measured end to end: `dim_corners` 193 corners over 17 slugs → **2,441 over
  147 races and 34 slugs**; `int_corner_metrics` 1,129,351 → **2,593,635** cells;
  `int_corner_skill_residuals` 970,874 → **2,206,939** rows, thin-sample flag 25.8% →
  17.1%; `mart_corner_skill_driver` 92 → **141** driver-seasons with all seven seasons
  populated where 2020 previously had none, mean mapped corners 123 → 272;
  `fct_telemetry_deltas` 10.7M → **24.5M** rows, the one real cost of the change — and it
  is a CDN cost as well as a build one: its parquet export goes 59 MB → 168 MB and
  `int_corner_metrics` 13 MB → 27 MB, roughly +123 MB on a publish. Both are exported by
  `scripts/export_app_data.py`; `fct_telemetry_deltas` is in its optional set, so dropping
  it from the export is available if the payload matters more than the feature does.

  Gates: `dbt build` on dev PASS=627 ERROR=0 TOTAL=630, `make test-all` on fixtures
  identical, coefficient pytest 66/66, docs gates green after regeneration, app
  `tsc --noEmit` clean, oracle drifting exactly `fct_telemetry_deltas` plus the two
  intermediates that changed, baseline re-snapshotted and `--check` clean.

  Two things noted, not fixed. `mart_corner_skill_driver`'s committed app parquet is now
  stale and gains a 2020 partition; the export is all-or-nothing, so it belongs to the
  pending app-data commit rather than here. And the same `LEAST`/`GREATEST` NULL-swallowing
  pattern appears at two other sites — `fct_cliff_prediction_features.survival_weight`
  (measured: 5 rows of 137,447 take the NULL path, and the `COALESCE(..., 1.0)` fallback
  written around it is dead code because the clamp returns 4.0 rather than NULL) and
  `int_lap_normalized_pace.dirty_air_penalty_s` (measured: no rows at the ceiling today,
  but a NULL `theta_time` would silently mean a flat 5 s penalty). Neither is material now;
  both are the same trap.

- 2026-08-22: **Data-profile baseline re-snapshotted.** `make dq-test` failed at 116 drift
  lines against the pre-Phase-1 baseline — confirmed as exactly the number this doc
  predicted, and read as a whole rather than per phase per the note above. All 116 are the
  intended movements of Phases 1–5 (`fct_lap_residuals`, `fct_stint_features`,
  `fct_telemetry_deltas`, `mart_corner_skill_driver`, `mart_degradation_history_envelope`);
  none are unexplained. Ran `make data-profile-snapshot`; `make dq-test` now passes clean
  (`No data-profile drift across 15 tables`, source freshness OK). Only
  `transform/tests/data_profile.baseline.json` changed. This clears "Resume here" item 3;
  items 1 and 2 are user-gated and untouched.

---

## Resume here (next session)

State of the working tree: all five phases implemented and uncommitted. Every finding in
this document is closed. Nothing has been committed in any phase — the user commits, never
the agent.

**Open, in order:**

1. **User sign-off on Phase 5.** Phases 1–4 are signed off. Phase 5's box is not, and
   should not be ticked by an agent.
2. ~~Phase 0's user-gated deletion~~ of the four docs `PLAN.md` supersedes. **Done
   2026-08-22** — user confirmed; `compounds_logic.md`, `compounds_plan.md`,
   `downstream_audit.md`, `chat_history_compounds_architecture.md` deleted.
3. ~~One data-profile re-snapshot before commit.~~ **Done 2026-08-22** — see Checkpoint.
   `make dq-test` now passes clean.

Only item 1 remains, and it's yours: review Phase 5, then commit whenever ready.

**Follow-ups these phases surfaced, none of them blocking:**

- `LEAST` / `GREATEST` swallow NULL arguments in DuckDB, so a clamp written around a
  nullable expression returns the bound instead of NULL. Phase 5 fixed the material case
  (`mart_corner_skill_driver`, where it made every driver's corner-skill index positive).
  Two others are latent and measured: `fct_cliff_prediction_features.survival_weight`
  (5 rows of 137,447 today, and its `COALESCE(..., 1.0)` fallback is dead code) and
  `int_lap_normalized_pace.dirty_air_penalty_s` (no rows at the ceiling today). A grep of
  the other clamp sites for nullable inner expressions is a half-hour job.

- `int_pit_strategy_value`'s optimal-pit-lap search ignores pit loss (see the Phase 4
  entry above). The single highest-value item in the strategy family now.
- `strategy_verdict` returns `optimal` on 8 of 7,129 stints. Almost certainly the same
  0.5 s threshold.
- `race_to_track` has no row for `2018_14` at all. Phase 5 removed it from the corner
  chain's path; the models that still key on that seed still lose the race —
  `int_track_geometry` covers 36 slugs but not that event, and `int_pit_strategy_value`
  falls back to the flat 21.0 s pit loss for its 35 stints.
- The app data is two months stale and `make app-data-check` fails at clean `HEAD` — the
  shipped app serves **v3** degradation predictions against the repo's **v4**. Written up
  in its own section above; the fix is `make app-data` plus a review of the prediction
  delta, and it deserves its own commit. That commit now also has to carry
  `mart_corner_skill_driver`, whose committed parquet Phase 5 made stale and which gains a
  2020 partition it has never had.
- `int_lap_thermal_proxy` still treats a red flag like any other neutralised lap, now
  that `is_red_flag_lap` exists to distinguish it (from Phase 1).
- 2018 Q1 is effectively absent from the qualifying chain — 26% `is_accurate = false`
  that season, three sessions with zero valid Q1 laps (from Phase 3).
- `make lint` fails on 8 models and `make lint-comments` fails on
  `venv/lib/python3.14/site-packages/filelock/` — the Makefile's grep does not exclude
  the vendored venv. Both pre-date this work.

**Gate commands, for reference:** `make test-all` (fixture build — needs the
`bronze_base` var, which the target supplies), `make lint-oracle-check`, `make lint`,
`make docs-reference && make docs-coverage`, then `docs-audit` / `docs-facts` /
`docs-coverage-check`, `PYTHONPATH=transform ./.venv/bin/pytest
transform/tasks/coefficients/tests/`, and `pnpm exec tsc --noEmit` in `app/`.
