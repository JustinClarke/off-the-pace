# WI-01 — Label spine: one version bump, not four

**Group:** 08 foundations · **Depends on:** `WI-15a` (F48's feature-coding fix must land before θ_air
is re-estimated — step 4 below; this header used to say "nothing") · **Blocks:** any v15 retrain, WI-12
**Blocker:** a human ruling on what the field base should contain (see below, board decision `FD1`)
and a small one on F51, exclude vs. weight (`FD2`) — the measurement work is done; two design
decisions are what's outstanding.

**Findings folded in:** F1 (Critical), F22 (High), F23 (High), F38 (High), F35 (Low), F42 (Low), F5
(Medium), F48-θ-part (Low-Med), **F51** (new, Medium).

**Reverification:** all CONFIRMED-AS-STATED on independent re-derivation (two separate agents
hand-rederived F22's and F38's algebra from `int_track_evolution.sql` / `int_field_pace_curve.sql`
rather than trusting the report's own probe, and got the same identities). F35 and F42 have no
"Fix:" or "how I could be wrong" in the original reports — supplied below.

---

## The one question every one of these answers differently

`int_lap_residual_decomposed.sql` computes `driver_skill_residual_s` as *pace minus every explained
component*, where "explained" includes a **field base** (`base_track_pace_s`, from
`int_field_pace_curve.sql`) plus several **components subtracted again on top of it**
(rubber, ambient, compound, a circuit×constructor interaction). The base and the components must
share one reference frame. Right now they don't, in four different ways:

| # | What's inside the base already | What's subtracted again | Effect |
| :-- | :-- | :-- | :-- |
| F1 | Nothing — it's fabricated to 0 where the field curve has no row (14,892 / 160,207 laps, 9.3%) | (n/a — the base itself is wrong) | Label fabricated: mean error 4.2s median, 6.35s mean vs nearest real base |
| F22 | Rubber + ambient (exactly — `field_pace_smoothed_s = race_mean + rubber + ambient + unexplained` to 2.8e-14) | Rubber + ambient, again | Label moves mean 0.30s, 3.7% of cliff labels flip |
| F38 | The field's own average compound cost (mean 2.29s) — fuel is handled correctly, compound is not | The lap's own absolute compound cost | Label moves mean 1.12s (largest of the four), 10.5% of cliff labels flip; a field pit stop reads as +3.15s of driver degradation |
| F42a | — | A unitless 0.95–1.09 compound-grip ratio, added as if it were seconds | Within-stint constant; cancels from the ML label, corrupts app-surface levels |

**F35** is different in kind: a circuit×constructor interaction is added on top of a per-race
constructor structural pace that already spans the circuit for that race — but both terms are
constant within a stint, so **F35 cancels from the ML label exactly** (confirmed independently: it's
a level bug for app surfaces, not a label defect). It rides in this bump for change-management
convenience (same file, same review), not because it's correctness-blocking.

**F5** and **F48's θ part**: `theta_air` (the dirty-air tax coefficient inside the label) is one
global OLS slope over every season pooled, and it's calibrated on F1's fabricated laps (F23) *and*
miscodes the closest followers as clean (F48 — DRS-open sub-1s gaps coded `drs_train`, not
`dirty_air`). Fixing F1 alone moves θ 0.152→0.416 (2.7×); fixing F48's coding on top of that moves it
again, 0.416→0.443. **θ has to be re-estimated exactly once, after both F1 and F48's feature-coding
side land** — not once per fix.

**F51 (new):** `event_driven` laps (SC/VSC/red-flag/restart — 6.4% of the currently-eligible
population) are never excluded from `is_training_eligible`, and `correction_weight` (built for
exactly this) is computed but never applied anywhere in `ml/src/`. This sits in the same files being
touched here and should be decided in the same pass. Full write-up: `../reference/new-findings.md`.

---

## The ruling this needs before building

**What should `base_track_pace_s` represent — a race-mean reference laps are measured against, or
the field's actual pace on the track that lap?** The two readings imply opposite fixes for F22/F38:

- **Option A (recommended by the reverification — matches how fuel is already handled).** The base
  should be *fully neutral*: fuel-corrected (already true) **and** compound-corrected (F38's fix) and
  should **not** have rubber/ambient subtracted again on top (F22's fix — drop the double
  subtraction, or measure against a race-mean base and keep rubber/ambient only in the components,
  not both). This is the "measure like fuel is measured" option, and it's the one the report's own
  fix language leans toward for both findings independently, so applying the same logic to both once
  is consistent by construction.
- **Option B.** Keep the base as "the field's realized pace" (fuel- and compound- and rubber- and
  ambient-inclusive) and stop subtracting any of those components a second time. This changes the
  residual's interpretation from "pace vs. a fully neutral reference" to "pace vs. what the field
  actually did," which is a bigger conceptual shift and would need re-justifying the header identity
  and 07's closed-channel causal argument (`work/07-causal-pit-timing.md`) from scratch.

Recommend **A**. It requires no new design work beyond what F1's and F38's own fixes already do, and
it's the reading that makes F1's "drop the COALESCE" fix (below) mean the same thing everywhere.

## Method

1. **F1.** Drop the `COALESCE(base_track_pace_s, lap_time_s)` at `int_lap_residual_decomposed.sql:294`
   and `:309` so NULL propagates through `pace_delta_s` and `driver_skill_residual_s`, and NULL a
   label window (`next_5_lap_cumulative_jump_s`, `laps_until_cliff_class`) if any lap in it has no
   measured base. Then repair `int_field_pace_curve.sql`'s eligibility CTE (`:56-59`) so coverage
   doesn't collapse to zero on mixed-condition races: exclude only true in-laps (not the final
   stint's last two valid laps), and replace the race-wide "over 107% of the fastest lap" gate with
   a per-lap or rolling reference.
2. **F22 + F38, together (Option A).** Rebuild `int_field_pace_curve.sql` to correct for compound the
   same way it already corrects for fuel (subtract `expected_compound_pace_s` before trimming/
   averaging/smoothing — this is exactly F38's "arm B" counterfactual, already measured). Then in
   `int_lap_residual_decomposed.sql`, drop the second subtraction of rubber and ambient (F22's fix)
   since the base is now the sole carrier of both track-state terms.
3. **F42a.** Drop `compound_grip_peak` from the seconds-scale pace sum, or replace it with a
   properly-fitted per-compound offset in seconds with the correct sign (softer should net faster,
   not charged more).
4. **F5 + F48-θ.** After (1)–(3) land, re-estimate `theta_air` once, on the now-honest measured-lap
   panel, with the DRS-train coding from F48 already fixed on the feature side (see
   `WI-15-traffic-thermal-feature-semantics.md`). Window the estimate to a declared pre-eval season
   range (or freeze per version) rather than pooling every ingested season, so a future ingest can't
   silently relabel history again.
5. **F35.** Re-center `circuit_constructor_interaction_s` to have zero mean by construction (or only
   add it where it isn't already spanned by `constructor_structural_pace_s`), so app-surface levels
   stop drawing a spurious per-team, per-circuit shift. **[Ruled 2026-09-27, verification pass: the
   global re-centring does nothing meaningful (it moves every value by the same 0.002 s); the
   interaction is dropped from the constructor term instead, as the audit proposed. See below.]**
6. **F51.** Exclude `anomaly_class = 'event_driven'` from `is_training_eligible` (mirroring
   `'mistake'`/`'conditions'`) or apply `correction_weight` as an XGBoost sample weight — this needs
   its own small ruling (exclude vs. weight; see `../reference/new-findings.md`), but either choice touches the
   same eligibility CTE already being edited for step 1.

## Acceptance

- No labelled training row has a fabricated (COALESCE-defaulted) component anywhere in its 5-lap
  window.
- The field base is verifiably neutral to fuel *and* compound (a re-run of F38's arm-B check returns
  ~0 systematic offset).
- No component the base already contains is subtracted a second time (a re-run of F22's identity
  check, `assert_residual_components_not_in_base`, passes).
- θ_air is re-estimated exactly once across all of F1/F23/F48's fixes, on a declared season window,
  not pooled over every ingested season.
- `event_driven` laps are either excluded or weighted — not silently included at full weight.
- This is a version bump: every published v13/v14 comparison after this lands is annotated
  "not fixed-target" per F5/F2's finding, and any new headline is compared against a v14 **rebuilt**
  on the new label, not against the old published numbers (F38 alone moves 72% of labels by more
  than 250ms).

## Tests to add

T1, T2 (F1) · T9 (F5, label-stability monitor) · T16 (F22) · T17, T18 (F23) · T28 (F38, independent
re-derivation that no component the base contains is subtracted again — supersedes T16 for the
merged fix) · T32 (F42, unit check) · new: `assert_event_driven_excluded_or_weighted` (F51).

## Definition of done

`fct_cliff_prediction_features` rebuilds with the new label; `verify_findings.py`'s F1, F5, F22, F23,
F35, F38, F42 checks all flip to CLEARED; T1/T2/T16/T17/T18/T28/T32 are wired in and passing; the
model card and README are updated to state the label version and that pre-bump headline numbers are
not comparable at fixed target.

## As built (2026-09-27, fable-5.1)

Built directly in the working tree against `data/dev.duckdb` (rebuilt, not committed). Nothing
committed; nothing exported to `app/public/data`.

### Starting state: a partial prior attempt was already in the tree, unreviewed

Before this session touched anything, `int_field_pace_curve.sql` (F1's eligibility repair + F38's
compound correction), `int_compound_cliff_predicted.sql` (F42a's `compound_grip_peak` drop),
`int_circuit_x_constructor_interaction.sql` (F35's re-centring), `int_lap_residual_decomposed.sql`
(F1's base-COALESCE drop and F22's rubber/ambient de-duplication) and `fct_cliff_prediction_features.sql`
(F51's `event_driven` exclusion) were already modified, uncommitted, matching this doc's method almost
exactly. `int_circuit_x_constructor_interaction.sql` had a syntax error (missing comma before
`pre_center AS (`) that would have failed the very first build. `int_field_pace_curve.sql`'s
final-stint carve-out picked the final stint by `MAX(stint_id)`, a string (`'YYYY_race_driver_N'`) --
correct for single-digit stint counts, wrong the moment a driver reaches a double-digit stop count.
Fixed both; kept everything else as found rather than rewriting working code. F5 (theta_air windowing),
F23a/F23b (the calibration-panel/application split in `int_dirty_air_tax_component.sql`), and the
compound-component COALESCE the WI-01 board note flagged were not yet started.

### What was built this session

- **F1 (remaining piece).** Dropped `COALESCE(compound_component_s, 0.0)` from
  `total_explained_s`/`driver_skill_residual_s` (the board note's own follow-up: the WI text named
  only the base-pace COALESCE, the acceptance criterion is general). `laps_until_cliff_class`
  (`fct_cliff_prediction_features.sql`) now also returns NULL, not `'none_in_stint'`, when either
  the lap's own residual or a later lap's is unmeasured before a crossing is found or the stint ends
  -- re-derived independently in `assert_cliff_class_horizon_partition.sql`, which needed the same
  NULL-propagation added to stay a real, non-vacuous test rather than fail on every affected stint.
- **F5 + F23a + F23b (rebuilt `int_dirty_air_tax_component.sql`).** Split the single `panel` CTE into
  `panel_base` (INNER JOIN to `int_field_pace_curve`, no defensive COALESCE -- every row has a
  measured base, or no row at all) and `calibration_panel` (adds the correction_weight/rainfall
  filter AND `race_year <= var('theta_air_fit_season_max')`, new var, default 2025 = the latest
  currently-ingested season). `with_tax` now reads from `panel_base` (every base-measured lap gets a
  tax value) instead of the old, narrower `panel`. First build surfaced a real edge case the WI text
  didn't anticipate: `int_field_pace_curve` can carry a ROW for a (race, lap_number) with too few
  eligible cars to produce a value (`field_pace_trimmed_mean_s` AND the smoothed rolling average both
  NULL despite the row existing -- 19 laps, all lap 21-22 of 2022_7 around a red-flag restart); the
  INNER JOIN needed `AND fp.field_pace_smoothed_s IS NOT NULL`, not just row existence.
- **F5's verify check rewritten.** The audit's own F5 measure (count of distinct nonzero
  `dirty_air_tax_s` values) could never have detected "windowed vs. pooled": `dirty_air_share_lag1`
  is binary, so theta collapses to one nonzero value on the table either way. Replaced with a check
  that the SQL declares the season-window guard and the var has a value.
- **F23b's verify check narrowed.** After the fix, a base-missing lap still correctly has no tax row
  (F1's reason, not F23b's) -- 2,309 such rows, all lap 2 of races where the whole field's out-lap
  sits there. Both the `verify_findings.py` check and T17 now require `base_track_pace_s IS NOT NULL`
  before counting a missing tax row as the F23b defect.
- ~~**F35's verify check rewritten.** The audit's own measure (does `int_lap_residual_decomposed` still
  reference the interaction) can't distinguish the ruled fix (re-centre to zero mean, kept in the
  residual) from the defect (never re-centred): replaced with a direct check that
  `AVG(circuit_constructor_interaction_s)` is ~0 (measured: exactly `0.0`).~~ **Superseded by the
  verification pass:** re-centring reverted, interaction dropped, check rewritten to measure that it
  contributes exactly 0.
- **Two real downstream regressions found and fixed, not present in the WI doc's scope list:**
  - `fct_ghost_car_pace.sql` reconstructed `predicted_lap_time_s` by adding
    `rubber_component_s + ambient_component_s` on top of `base_track_pace_s`, which now already
    contains them (F22) -- every self-consistency check failed (up to ~all 148k rows) until both
    terms were dropped from the three recombination sums (kept as informational columns).
  - The same model's `COALESCE(driver_skill_residual_s, 0.0)` / `COALESCE(compound_component_s, 0.0)`
    turned a genuinely-unmeasured ego lap into "cost exactly 0," breaking self-consistency by up to
    ~16s on those laps. Excluded such laps from `ego_laps` instead (`driver_skill_residual_s IS NOT
    NULL`) rather than fabricating a zero.
  - `fct_lap_residuals.sql` didn't expose `base_track_pace_s`/`pace_delta_s` despite its header
    claiming to "expose the full residual decomposition" -- added both, and used them to scope the
    mart's `driver_skill_residual_s` not-null test to measured rows only.
- **Five pre-existing tests updated to the new (correct) identity/thresholds, not weakened:**
  `assert_lap_7term_identity.sql` and `assert_example_identity_closure.sql` (5-term, not 7),
  `assert_driver_skill_residual_reasonable.sql` (bound 15.0 -> 16.0s, 3 genuinely slow laps, max
  15.87s), `assert_pace_delta_flat_by_race_fifth.sql` (re-derives the NEW fuel-and-compound-corrected,
  final-stint-inclusive eligibility, not the old one), `assert_field_pace_honest_range.sql` (range
  [0.990, 1.055] -> [0.945, 1.070], then [0.920, 1.070] in the verification pass: the compound-neutral base sits further below the raw fastest lap
  on high-wear laps than a fuel-only-corrected base did).
- **New tests (all in `transform/tests/`, registered in `transform/tests/README.md`):** T1
  (`assert_pace_delta_requires_field_base.sql`), T2 (`assert_label_window_has_measured_base.sql`),
  T9 (`assert_prior_season_labels_frozen.sql`, warn, backed by the new
  `transform/seeds/label_stability_baseline.csv`), T16 (`assert_residual_components_not_in_base.sql`),
  T17 (`assert_dirty_air_tax_covers_spine.sql`), T18 (`assert_theta_panel_has_measured_base.sql`),
  T28 (`assert_field_base_component_neutral.sql`), T32 (`assert_compound_pace_units.sql`), and
  `assert_event_driven_excluded_or_weighted.sql` (F51).
- **schema.yml.** `int_lap_residual_decomposed.driver_skill_residual_s`/`total_explained_s` and
  `fct_lap_residuals.driver_skill_residual_s` not-null tests now carry
  `where: "pace_delta_s IS NOT NULL AND compound_component_s IS NOT NULL"` (or the `fct_lap_residuals`
  equivalent) instead of a blanket not-null, matching the `compound_component_s`/F39 pattern already
  in the file.
- **Docs.** `README.md` and `ml/README.md` each carry a "label spine version bump" note: `v14`'s
  artefacts were trained on the pre-bump label; no post-bump number is comparable at fixed target
  until a `v15` retrain (WI-12).

### Measured, on the rebuilt dev warehouse (2026-09-27)

- `verify_findings.py F1 F5 F22 F23a F23b F35 F38 F42a` -- **all 8 CLEARED.** Full board:
  12 present / 52 checked, all 12 pre-existing and out of this item's scope (F2/F4/F10/F11b/F12/F16/
  F18/F27/F30/F40/F42b/F44 -- blocked by FD3/FD4/FD6/WI-02b or otherwise not named in this doc).
- F1's repair: laps with no measured `base_track_pace_s` fell from 14,892/160,207 (9.3%) to
  3,981/161,040 (2.47%).
- ~~theta_air, re-estimated once on the fully-fixed panel (F1 + F22 + F23a + F23b + F38 + F5's window,
  with F48's coding already in): **0.1691 s/lap**~~ **Superseded by the verification pass: 0.5033
  s/lap.** The 0.1691 below was fitted with fuel but not tyre cost subtracted from the calibration
  residual, which is wrong once the base is compound-neutral. (n=142,377, 31.6% treated), independently
  re-derived outside the model to confirm. This is the number to carry forward, **not** the 0.443
  this doc's own text projected from testing F1+F48 in isolation -- F22/F38/F23a/F23b all touch the
  same calibration panel and the combined effect does not equal the sum of the isolated ones. Shipped
  (pre-WI-01) value was 0.1310.
- F38's neutrality check: mean `driver_skill_residual_s` on measured laps is **+0.165s** (CLEARED
  threshold is `< -1.0` i.e. not the old ~-2s compound-contaminated mean); F35's re-centring: exact
  `0.0` mean.
- `dbt test` on the full project (excluding the WI-16a `int_driver_isolation_lap_pace`+ subtree,
  which needs `make car-fe-isolation-fit` first and is unrelated to this item): the only failures are
  that pre-existing, tracked gap (W34) and one unrelated, pre-existing single-row failure in
  `assert_stint_geometry_2018_compound_code_null` (refs only `int_stint_geometry`, untouched by this
  item). Every test this item's method or tests-to-add section names passes. The one warn-severity
  failure, `assert_sector_aggregates_to_lap`, is WI-07's pre-existing, documented, out-of-scope
  finding (unaffected in count by this item -- 11,114 vs. its documented 11,892 baseline).

### Deviations from the WI doc, recorded per board.py's rule

1. ~~**theta_air lands at 0.169 s/lap, not the ~0.443 this doc projected** (see above).~~ **Superseded:
   0.5033 s/lap after the verification pass; 0.169 was a calibration bug, not a finding.** The projection
   was from testing F1+F48 alone; the fully-integrated re-estimate is materially different because
   F22/F38/F23a/F23b change the same calibration panel. Recommend the board's `note` field and any
   downstream reference to "~0.443" be corrected to 0.169 before WI-12/WI-16b read it. **[Now: 0.331
   after the W40 re-ruling (0.5033 was interim; see the end of the Verification pass); the value
   WI-12/WI-16b read is `theta_air_label_value` in `dbt_project.yml`.]**
2. **`fct_ghost_car_pace.sql` and `fct_lap_residuals.sql` needed fixes** the WI doc's method section
   doesn't name (both listed above under "real downstream regressions"). Both are direct, mechanical
   consequences of F22 and F1 respectively landing correctly upstream, not new findings against a
   different part of the pipeline.
3. **F42a: dropped, not refit.** Per the WI doc's own "either" -- `compound_grip_peak` was already
   dropped (replaced with `0.0`) by the prior partial attempt. A properly-fitted per-compound offset
   in seconds (the WI doc's other option) is not built; flagged as a possible follow-up, not done
   here.
4. **`int_pit_strategy_cost_curve.sql` still consumes `compound_grip_peak`** (a difference of two
   compounds' unitless ratios, `COALESCE(new_c0.compound_grip_peak, ...) - COALESCE(old_c0.compound_grip_peak, 0.0)`).
   Untouched: not named in this WI's method or acceptance, and out of scope for this item. Noted as
   a related, unresolved unit concern for whoever picks up F42's remainder.
5. **theta_air's frozen window (`theta_air_fit_season_max: 2025`)** is this session's read of "declared
   pre-eval season range," not a ruling: 2025 is simply every currently-ingested season (2026 is not
   ingested, W19). If FD4 (holdout policy) is later ruled in a way that excludes 2025 from any
   estimation panel, this var should move with it.
6. **Docs snippets / inventory counts (`docs/snippets/transform-inventory*.mdx`, `overview-numbers.mdx`)
   were not regenerated.** Per the board's own W8 watch item, these are deferred to a single sweep
   after landed items are committed; `make docs-coverage` will pick up the 9 new test files whenever
   that sweep runs.

### Not done / still open

- **Board/log not touched.** Per `BUILD-ORDER.md`'s own rule, updating `build-log.json` and the
  item's stage is the orchestrator's job after independently re-running this doc's definition of
  done -- not done by the agent that built it.
- **`app/public/data` not re-exported.** This item only rebuilt `data/dev.duckdb`; nothing was
  exported for the app, and nothing should be until the models are retrained on this label (matching
  W25's existing hazard note for WI-15b, which applies here too).
- **No commit.** Everything above is in the working tree only, per instruction.

## Verification pass (2026-09-27, same day, orchestrator-directed)

The first build above was checked independently before any stage move. Four defects blocked
closing it, five open questions were ruled, and several tests were found not to test what they
claimed. Everything below is in the working tree and `data/dev.duckdb` only. Nothing committed,
nothing exported to `app/public/data`.

### Critical fixes

1. **theta_air calibration subtracted fuel but not tyre cost.** With a compound-neutral base (F38),
   the calibration residual `lap - base - fuel` kept every lap's own tyre cost, and that cost is
   correlated with the dirty-air lag. `int_dirty_air_tax_component`'s partial residual now also
   subtracts `compound_component_s` (joined from `int_compound_cliff_predicted`), the same way fuel
   is handled. A lap with an unknown tyre cost gets a NULL partial residual and drops out of the fit
   only; it still gets a tax value. **theta_air 0.1691 -> 0.5057** on this fix alone, **0.5033**
   after fix 3 below (calibration n = 138,970, 2018-2025). Pooled, as ruled. *(Re-ruled after
   this pass: 0.331, W40. See "theta re-ruled after verification" below.)*
2. **FD2 was half done.** Only `event_driven` was excluded. `int_event_corrections` now emits
   `is_lap_after_restart` (two laps back SC or red flag, one lap back green; VSC excluded, as FD2's
   measurement found VSC restarts unaffected), carried through `int_lap_residual_decomposed` and
   used by `fct_cliff_prediction_features.is_training_eligible` (an internal column: the mart's
   enforced contract is unchanged). `correction_class`/`correction_weight` are untouched, so theta's
   panel does not move. **1,426 eligible rows newly excluded** (FD2 measured 1,588 on the older,
   larger eligible population). The F51 test now checks both, re-deriving the lap-after-restart
   rule from the raw SC/VSC/red flags instead of trusting the new column; it returns 1,426 rows on
   the pre-fix build.
3. **2,756 laps with unknown tyre cost entered the base** as `COALESCE(expected_compound_pace_s,
   0)`. `int_field_pace_curve` now drops them. The base loses 195 (race, lap) cells, almost all in
   four races already quarantined for tyre age (2022_11, 2022_7, 2025_6, 2018_3), whose residuals
   were already NULL; only 38 laps lose a residual (2023_8, 2020_3). Some surviving cells got
   thinner (2020_3 laps 4-5: 3 cars -> 1), which is where the largest label moves come from (watch
   list).
4. **Model card and READMEs.** `ml/src/card.py` carries a new first limitation (`LABEL_SPINE_NOTE`,
   emitted for any card version <= v14), and the same text is in `ml/model_card.yml` and
   `ml/models/model_card.json` (inserted, not regenerated; a regeneration reproduces it). The card's
   `version` stays `v14`: it describes the shipped artefacts, which were trained on the old label.
   `README.md` line 7 and the identity block say five terms; `ml/README.md` no longer calls WI-12 a
   v15 retrain (WI-12 is the 06b re-measure; a v15 retrain is unscheduled).

### Rulings on the five open questions

1. **theta window:** keep `<= 2025` (every ingested season; 2025 is complete). If FD4 rules 2025
   out of estimation, move `theta_air_fit_season_max` and relabel.
2. **F35:** the global re-centring moved every value by 0.002 s and left each per-team,
   per-circuit shift in place. Reverted (`int_circuit_x_constructor_interaction.sql` is back to
   HEAD) and the interaction dropped from `constructor_component_s`, as the audit proposed. It had to
   leave `fct_ghost_car_pace`'s three recombination sums too (kept as an informational column), or the
   ego == host identity breaks by exactly the interaction.
3. **In-lap rule:** keep the existing logic (drop the last two valid laps of a non-final stint; the
   pit in-lap itself is already not a valid lap; the final stint keeps every lap). This doc's step 1
   said "exclude only true in-laps"; that text is superseded by this ruling. The field-pace header
   now states the rule.
4. **Honest-range floor:** 0.945 -> 0.920. Observed minimum is 0.9471. Note 0.920 is *lower* than
   0.945, so the floor now flags fewer bases, not more; the tyre-cap concern it was meant to watch is
   on the watch list instead (337 laps, 0.21%, sit on the 10 s wear cap).
5. **F35 check:** rewritten to measure that the interaction contributes exactly 0: the residual SQL
   no longer references it, and `max |constructor_component_s - structural pace|` is 0. It reads
   PRESENT (0.49 s) on the pre-fix data and CLEARED after.

### Test repairs

- **T28 replaced.** The old T28 re-implemented `int_field_pace_curve`'s SQL line for line, so it
  could only detect an edit to the model (it failed on fix 3 while the base stayed neutral). The new
  T28 fits the within-race slope of per-lap mean residual on the field's mean tyre cost: +0.027
  pooled (8,956 cells), -0.10 to +0.12 by season; a fuel-only base rebuilt from the same eligible
  population (the F38 defect) gives -0.958. Bound +/-0.30, pooled and per season, plus a 1,000-cell
  vacuity guard.
- **T16 fixed.** Its race mean averaged `int_field_pace_curve` over every lap, including the
  low-sample laps `int_track_evolution` drops, so its premise held on 22.8% of rows and it silently
  skipped the rest. It now uses `AVG(track_state_index_s)`: premise holds on 100% (149,375 laps, max
  gap 2.8e-14), and a row where it breaks fails instead of being skipped.
- **T9 extended.** Also checks the fitted theta equals the declared `theta_air_label_value`
  (new var, 0.5033) within 1e-4, and is a single value. The seed `label_stability_baseline.csv` was
  re-taken after this pass (same bump, one snapshot). *(W40 changed both: the model now applies
  the var, T9 compares the applied value within 1e-9, and the seed was re-taken again. See below.)*
- **T32 note.** `int_pit_strategy_cost_curve.sql` still adds a difference of unitless
  `compound_grip_peak` ratios as seconds; out of scope, on the watch list.
- **`assert_driver_skill_residual_reasonable`** bound 16 -> 17 s: dropping the interaction moved the
  same real slow lap (2024_12 PER lap 22) from 15.871 to 16.007 s.
- **`assert_pace_delta_flat_by_race_fifth`** re-derives the base eligibility with the new
  unknown-tyre filter.
- **Comments corrected:** `int_lap_residual_decomposed`'s header said a missing dirty-air row makes
  the tax NULL; it is filled with 0 (harmless: that only happens where `pace_delta_s` is already
  NULL). The constructor term's COALESCE to 0 is now documented: 4,548 measured laps, mostly all-wet
  races with no constructor row; it cancels from both labels (a per-race constant within a stint)
  but not from residual levels.

### Measured on the rebuilt dev warehouse

- `verify_findings.py`: F1, F5, F22, F23a, F23b, F35, F38, F42a all CLEARED. 13 present / 52: the
  12 out-of-scope findings listed above plus **F45**, which flipped from a marginal CLEARED (0.0502
  vs 0.0437) to PRESENT (0.0266 vs 0.0511) because this pass moves residual levels. F45 is WI-14b's
  (blocked on FD5); on the watch list.
- Label movement against the pre-pass build: 85,545 of 106,394 labelled rows move, 49,745 by more
  than 250 ms, mean |d| 0.419 s, max 12.1 s (thin base cells, above); 8,208 `laps_until_cliff_class`
  changes; `is_training_eligible` 125,026 -> 123,715 (2,337 lost, 1,026 gained).
- Mean `driver_skill_residual_s` on measured laps +0.069 s (F38 check).
- `dbt test` (all but the WI-16a car-FE subtree): PASS 765, WARN 1, ERROR 7 of 773. The warning is
  WI-07's known `assert_sector_aggregates_to_lap` (10,848). The errors: six tests on WI-16a's
  `driver_isolation_method_scores` seed, which is not loaded in dev (W34), and the pre-existing
  single-row `assert_stint_geometry_2018_compound_code_null`. Every test named in this doc passes.
- A correction to the brief: `int_sector_residual_decomposed` (still 7-term) is not unused; the
  Sector Decomposition app page reads it through `scripts/export_app_data.py`.

### theta re-ruled after verification: 0.503 -> 0.331 (W40, 2026-09-27)

After this pass, WI-12's 06b re-measure compared estimators on this item's own calibration panel
(2018-2025, 138,970 laps). Every estimator that removes between-stint variation landed at
0.30-0.43, and the pooled 0.503 sat outside the pre-registered F2 interval (stint fixed effects
plus six tyre-age bins: 0.3313 [0.293, 0.370]). Two reasons: slower cars follow more often, and
laps late in a stint are both more often following and slower than the tyre model accounts
for. The user ruled W40: **the label carries 0.331**, not the pooled 0.503. This is the second half
of the same version bump (WI-01 + WI-12 are one bump), so 0.5033 above is an interim value and
nothing measured on it is kept. The final label carries 0.331.

**What changed.**
- `int_dirty_air_tax_component.sql` no longer fits theta. `theta_air_label` applies
  `var('theta_air_label_value')` directly. A two-way FE fit is not one SQL aggregate, so the F2 fit
  runs outside dbt (WI-12's `d2_fit_wi12.py`, section W) and is frozen as the var. The pooled
  COVAR/VAR slope and its 0.1310 COALESCE fallback are gone. `calibration_panel` is unchanged: it
  still defines the fit population, sets `calibration_sample_n` (138,970), and still carries F5's
  `theta_air_fit_season_max` filter. The panel_base comment that gave the tyre-cost mechanism
  backwards (WI-12's "Also found") is corrected: treated laps carry about 0.33 s *less* modelled
  tyre cost.
- `dbt_project.yml`: `theta_air_label_value: 0.331`, with its provenance and the bump procedure
  (rebuild, re-run WI-12 `d1`/`d2`, edit the var, re-take the seed).
- T9: the theta check compares the *applied* value with the var within 1e-9. It used to compare a
  fit within 1e-4. A mutation (var 0.5033, or 0.3310001, against the 0.331 build) warns 1 row.
  `label_stability_baseline.csv` re-taken: row counts unchanged, and five of seven season means moved
  by more than 0.001 s (2018 -0.1860 -> -0.1736, the largest).
- WI-12's `d1` gate now checks the panel against a pooled-slope fingerprint and checks shipped theta
  = the declared var. `d2` stops unless the declared var equals the F2 fit to 3 dp.
- Schema descriptions, `transform/tests/README.md`, the model card note (`card.py`,
  `model_card.yml`, `model_card.json`, byte-identical to a regeneration), `README.md` and
  `ml/README.md` say 0.331 and that WI-01 + WI-12 are one bump.

**Measured on the rebuilt dev warehouse** (`dbt build -s int_dirty_air_tax_component+`, excluding
the W34 isolation subtree: PASS 255, WARN 2, ERROR 0; the warnings were WI-07's known
`assert_sector_aggregates_to_lap` and T9 before the seed was re-taken).
- The tax reads back as exactly 0.331 on all 47,962 treated laps. It moved by -0.1723 s on those laps
  and nowhere else. No tax row was lost or gained (153,792).
- `driver_skill_residual_s`: 47,810 measured laps move, each by +0.1723 s. No NULL flips. The mean on
  measured laps goes from +0.069 to +0.123 s.
- `next_5_lap_cumulative_jump_s`: 84,486 of 106,394 labels move (31,551 by more than 250 ms, mean
  |d| 0.207 s, max 3.27 s), with no NULL flips. The residual part of a move is capped at 5 x 0.172 =
  0.862 s. The rest comes through the per-stint `drift_s_per_lap` term (-15 x drift), which is fitted
  on the residual and so moves with theta.
- `laps_until_cliff_class` changes on 4,207 rows. `is_training_eligible` goes from 123,715 to
  123,655 (1,140 flips, through residual-based `anomaly_class`).
- `dbt test` on the whole project except the W34 subtree gives PASS 765, WARN 1, ERROR 7 of 773. That
  is identical to this pass's own result above (the same warning and the same seven errors), so no
  threshold shifted.
- `verify_findings.py`: F1, F5, F22, F23a, F23b, F35, F38, F42a all CLEARED (F38's measure is now
  +0.123). The full board is unchanged at 13 present / 52.
- WI-12 re-run: `d1`'s panels are identical in content to its first run, and `d2`'s tables are
  identical. See WI-12's Gate results.
