# WI-02 — Compound seed: provenance first, point-in-time refit second

**Group:** 08 foundations · **Depends on:** F41 (this file) must land before the refit; benefits from
`WI-05`'s bronze QA landing first (F2's fits consume stint boundaries F24/F25 show are wrong in 3+
races) · **Blocks:** `WI-08` (shares the seed)
**Blocker:** existing human ruling needed — 00c's leakage standard vs. the spine's same-race
exemption, applied to this specific case (see below; board decision `FD3`). The magnitude is
already measured, so this is a decision, not more measurement.

**Executed as two board items**, because only half of this doc waits on that ruling:
`WI-02a` = F41, F7, F39 (provenance and the NULL-safe wear cap; no ruling needed, do F41 first) and
`WI-02b` = F2, F9 (the refit and the eligibility decoupling; needs `FD3`, `WI-02a` and `WI-05` —
the board treats `WI-05` as a hard dependency here, since refitting on stint boundaries F24/F25
show are wrong would just have to be redone).

**Findings folded in:** F2 (High), F7 (Medium), F9 (Medium→Medium, reclassified up), F39
(Low-Medium), F41 (Medium-Low), F55 (Low; added 2026-09-24, found by the WI-05 build -- code fix moved to `WI-13`; the Spain refit stays with `WI-02b`).

**Reverification:** all CONFIRMED-AS-STATED, one ARGUABLE nuance on F2's cost framing, one severity
bump on F9.

---

## F2 — the core leak, and what's actually at stake

`fit_compound_cliff.py:230` fits each (track, compound, season) cell by filtering
`race_year == season` — so **every one of the 171 (track, season) cells in the mart is fitted on
exactly the one race it's later joined back onto**, including that race's own later laps. This was
independently reconfirmed by reading the filter and the join (`fct_cliff_prediction_features.sql:
578-582`) directly, not by re-running the report's probe.

**Cost, reread carefully.** The report's own three-arm measurement (A = in-race values, B = lagged
values no refit, C = lagged values + refit) shows a **small** cost for two of the three model
families and a **materially larger** one for the third:

| Family | A → C delta | Relative size |
| :-- | :-- | :-- |
| p50 pinball | −0.0064 (0.7%) | small |
| cliff macro-F1 | +0.0015 | small |
| **stint-life AFT NLL** | **−0.0761 (≈3.8%)** | **an order of magnitude larger** |

The original report's "How I could be wrong" treats all three C-arm deltas as uniformly small /
possibly reseed noise. They aren't uniform — and stint-life is the family the 2026-09-10 gauge
decision (`_improvements` project memory) explicitly tunes against, so this asymmetry needs its own
check (a proper floor run, not a single refit) before "the honest pipeline costs little" is treated
as true for all three families.

## The ruling

Two options, both legitimate under the tree's own precedent:

1. **Point-in-time fit** (like `int_sc_hazard_history` already does): each season's cell is fitted on
   seasons strictly before it. This is what the measured "arm C" approximates.
2. **Declared same-race exemption**, matching the spine's own precedent for the label decomposition
   (`work/08-foundations-repair.md` 08…:133-160) — but *only* if training is made consistent with
   serving, i.e. the same in-race-fit-or-carried-forward distinction the 2025 fold already uses gets
   applied uniformly to training too, not just to the one held-out season.

Either is defensible; leaving it as-is (train on in-race values, serve on carried-forward ones) is
not, because it silently makes every pre-2025 published headline optimistic relative to what the
model actually does on an unrun race.

## F41 — why it has to land first

Two independent provenance defects in the fitter, found by direct code read:

- **(a) Silent class-default fallback.** `fit_compound_cliff.py:293-302` replaces any
  out-of-range/`None` parameter with `COMPOUND_DEFAULTS`, but never updates `source` or the `notes`
  string, which still says `"fitted from N stints via cox_km_survival"`. **124 of 337 "fitted" cells
  (35,377 training rows, 30.4%) hold at least one class default** — some suspiciously exactly (e.g.
  26 MEDIUM cells land at exactly the default 33.0 laps).
- **(b) Fuel left in the wear-gradient fit.** `survival.py:262`'s `estimate_wear_gradient` consumes
  `normalized_pace_s`, which corrects for dirty air but **not** fuel burn (confirmed:
  `int_lap_normalized_pace.sql`'s header explicitly says so). Its own docstring claims "uses
  uncensored stints only" — the code applies no censoring filter at all, a second, separate
  docstring/code mismatch from the fuel issue. Re-run fuel-corrected: median gradient rises 0.0640 →
  0.0773 (23%).

**Why this blocks the WI-02 refit specifically:** a "point-in-time" fit is only honest if a fitted
value really was measured on prior seasons. If 30% of "fitted" cells are silently class defaults,
relabeling them "lagged" doesn't make them measured — it just moves the same opacity one step
downstream. Provenance has to be recorded **per parameter** (`onset_source`, `gradient_source`,
`severity_source`) before the refit can honestly claim to be point-in-time.

## F7 — the 2025 symptom of the same root cause

1,409–1,492 of 2025's training rows (7%) have no seed cell at all (no 2024 cell to carry forward for
that venue/compound pair), and get `cliff_onset_passed = FALSE`, `laps_past_cliff = 0`,
`expected_degradation_rate = 0` — fabricated defaults that also enter the label via
`compound_component_s`. Confirmed verbatim at `int_compound_cliff_predicted.sql:146-147,152,156,
194-202`.

## F39 — a NULL becomes a 10-second wear value

DuckDB's `LEAST`/`GREATEST` **both skip NULL arguments** (confirmed live:
`SELECT LEAST(NULL,10.0), GREATEST(NULL,5.0)` → `(10.0, 5.0)`). With `age_in_stint` NULL, this chain
runs tighter than the original report states: `GREATEST(age_in_stint - onset, 0.0)` also resolves to
`0.0` (not NULL), so `laps_past_cliff` looks like "no cliff yet" rather than "unknown," and
`compound_wear_s = LEAST(NULL, 10.0)` lands exactly on the 10.0s cap. 383 spine laps (2025_6, 2025_13,
2025_1, five 2018 laps), none training-eligible, but real app damage (2025 Miami skill numbers off by
~4s). `int_lap_thermal_proxy.sql:116-117` already documents awareness of this exact DuckDB quirk for
`GREATEST` — the fix pattern already exists in-tree to copy.

## F9 — reclassified from Medium-Low to Medium

`clean_cliff` (kept in training) and `mistake` (excluded) differ **only** by `cliff_onset_passed`
(the same in-race seed as F2), and both conditions also key on `residual(t)` — a term the label
itself subtracts five times going forward. Reported label means by class: normal −0.43, mistake
(excluded) −5.03, clean_cliff (kept) −7.87. This is closer to *selecting training rows on a noisy
proxy of the label itself* than a simple confound, which is a stronger effect than "Probably wrong,
Medium-Low" implies. The original report also has no "Fix:" line for F9 — supplied below.

## F55 — `fit_weight_penalty.py` uses a fuel burn rate the model no longer reads

Full write-up: [`../reference/new-findings.md`](../reference/new-findings.md). The **code fix** (read the
burn rate from the fuel model, not the seed constant) was folded into `WI-13` on 2026-09-24. What stays
here is the **Spain refit and the fit order**: `WI-02b` refits the compound seed, the weight-penalty
fitter strips compound wear using that seed's output, and since WI-02a the compound seed's pace series
depends on `weight_penalty_factor` in turn. Pick the order (or iterate) in this item, and refit Spain
once, after the compound refit, using the corrected rate.

## Method

1. **F41 first.** Add per-parameter provenance columns to `dim_compounds_season`
   (`onset_source`, `gradient_source`, `severity_source` ∈ {fitted, cross_season_fallback,
   class_default, carried_forward}); stop the notes string from claiming "fitted" when a default
   fired. Re-run `estimate_wear_gradient` on fuel-corrected pace, and add an explicit censoring
   filter matching its own docstring.
2. **F2 refit**, per the ruling above — point-in-time or a declared, serving-consistent exemption.
   Run a proper floor (not a single reseed) on stint-life specifically before accepting "cost is
   small" for that family.
3. **F7.** Refuse to build with uncovered (venue, compound) cells for a new season (T5), or carry
   the fallback hierarchy (venue history → class default) forward explicitly and mark it as such via
   F41's new provenance column.
4. **F39.** `CASE WHEN age_in_stint IS NULL THEN NULL ELSE LEAST(...) END` in the wear-cap macro. Add
   a lint rule flagging any `LEAST`/`GREATEST` over a nullable expression anywhere in `transform/
   models/` (T29's second half).
5. **F9.** Decouple `is_training_eligible`'s `clean_cliff` branch from `cliff_onset_passed` — e.g.
   define "cliff" via a change-point in the observed residual series rather than the same-race-fitted
   seed, or convert the exclusion into a sample weight so it doesn't hard-select the training
   population on a label-adjacent quantity.

## Acceptance

- Every seed cell's provenance is recorded per parameter, and no cell's `notes` claims "fitted" when
  a class default fired.
- The compound seed feeding training is fitted (or explicitly declared exempt) using only
  information available before the season it's served for; training and serving use the same kind of
  value.
- A floor run (not a single refit) confirms the honest pipeline's cost for stint-life specifically,
  not just p50/cliff.
- No 2025 (or future-season) row silently fabricates cliff features from a missing cell.
- `age_in_stint IS NULL` never produces a valid-looking wear value.
- Training eligibility no longer hard-selects on the same in-race seed that also drives F2's leakage.

## Tests to add

T3 (seed point-in-time), T5 (refuse-to-build on coverage gaps), T29 (NULL-safe LEAST/GREATEST + lint),
T31 (per-parameter provenance + censoring-filter check).

## Definition of done

`dim_compounds_season` carries per-parameter provenance; `fit_compound_cliff.py` and `survival.py`
match their own docstrings; the refit ruling is recorded in `build-log.json`'s decisions with the
measured cost (including the stint-life-specific floor); `verify_findings.py`'s F2, F7, F39, F41
checks flip to CLEARED; F9's eligibility change is measured with the seed-decoupled arm the original
report proposed but didn't run.

## As built -- WI-02a (2026-09-24): F41, F7, F39

State is in `../status/build-log.json`; this section only corrects or refines the spec where the
build did. WI-02b (F2 refit, F9) is untouched: **the seed was not refit**, and no parameter value of
an existing seed row changed.

- **F41a -- how the existing seed got per-parameter provenance without a refit.** `fit_group` now
  records `onset_source` / `gradient_source` / `severity_source` at fit time (plus `fit_source`, now
  exposed on `dim_compounds_season`), and writes "N stints via <tier>; no usable estimate for
  <params>: class default used" instead of "fitted from ..." when a default fires. The 510 existing
  rows predate that, so their sources were **labelled from their values**: on a
  cox_km/cross-season cell a parameter exactly equal to its `COMPOUND_DEFAULTS` value is
  `class_default`. The rule is one-directional -- a fired default always lands exactly on the default,
  so no default can be labelled measured; the only possible error is a genuine estimate that happens
  to equal one. Measured with recorded provenance on a scratch refit (below): 3-4 of ~1,200
  parameters per refit, so the inferred labels may over-report about 0.3% of parameters as defaults.
  Result: cox_km cells onset 70 / gradient 77 / severity 19 (the audit's numbers exactly); the audit
  did not count cross-season cells, which hold 4 / 12 / 0 more; notes rewritten on 140 cells (124
  cox_km, 16 cross-season).
- **`carried_forward` keeps a default a default.** The 71 hand-carried 2025 rows copy 2024 cells,
  12 / 15 / 6 of whose parameters are class defaults; those stay `class_default`, the rest are
  `carried_forward` -- the doc's own argument that relabelling a default "lagged" moves the opacity
  downstream. The 2025 australian_grand_prix INTERMEDIATE row (hand-made: an n_stints-weighted mean of
  other circuits' INTERMEDIATE cells, labelled `compound_class_default`) is not `COMPOUND_DEFAULTS`; its
  values were left unchanged and labelled `class_default`, as its notes explain.
- **T31 -- one clause of the audit's spec is not asserted.** "No fitted parameter equals the class
  default unless its source says default" is false by design once provenance is recorded (the 3-4
  coincidences above; a KM median is an integer lap count). The defect is guarded where it lives,
  in `fit_group` (unit tests forcing each fallback path); the seed-level tests check vocabulary, tier
  consistency, "class_default means the default value", honest notes, and carried rows.
- **F41b -- the whole series is fuel-corrected, not only the gradient's.** The fitter fits onset,
  severity and gradient on one series by design, and the cliff macro de-double-counts severity
  against `span * wear_gradient`, which only cancels when both carry the fuel burn or neither does.
  So `load_stint_data` emits `fuel_corrected_pace_s` (normalized pace minus
  `int_lap_fuel_state.weight_penalty_s`; the 0.8% of green-flag laps that model does not price --
  inaccurate timing, nearly all 2018 -- use the same race's constants and formula, which reproduce
  `weight_penalty_s` exactly on every priced lap) and `fit_group` prefers it. `normalized_pace_s` stays
  in the frame for `scripts/measure_wear_residual_sigma.py`.
- **F41b -- the censoring filter, and what it costs.** `estimate_wear_gradient` now keeps uncensored
  stints only, as its docstring said: a cliff detected on the fitted series, or a stint ended by a
  retirement (`dnf_status`, which the loader attaches to the final stint only; `forced_stop_flag` is
  on every lap of a retiring driver's race, so it would admit voluntary pits). Its docstring's window
  (`min(onset-2, max_age-2)`) was also wrong and now matches the code; `estimate_cliff_severity`'s
  docstring now says what the code does (detected cliffs only, windows on each stint's own cliff; the
  onset argument is unused). Scratch refit of 2018-2024 on today's warehouse, not promoted, against
  the pre-change estimator on the same warehouse (median measured gradient, cells measured in both):
  fuel correction alone 0.0710 -> 0.0935 (x1.38; gradient class defaults 107 -> 75 of 428 cells, onset
  88 -> 66, severity 40 -> 30); the filter alone x1.02 but 107 -> 136 gradient defaults; both
  0.0714 -> 0.1034 (x1.47, 93 defaults). The audit's x1.23 held the seed's onsets fixed on the
  pre-WI-05 warehouse (per-slug fuel rate); holding them fixed on today's warehouse gives x1.34 on the
  cells usable both ways, and refitting the onsets on the corrected series too gives x1.38 -- so most of
  the move from x1.23 is WI-05's fuel model, not this change. **For WI-02b:** the filter selects
  toward stints that reached a cliff and turns 18 more cells' gradients into class defaults; it is the
  doc's instruction, not a measured improvement.
- **WI-05 interaction found: the fitter could not run.** WI-05's quarantine NULLs tyre age on whole
  stints while the fitter took the compound from `stg_laps`, so 208 stints (2018-2024) entered with
  every age NULL and `build_survival_dataset` raised on `int(NaN)`. `load_stint_data` now drops laps
  with no tyre age (4,265 rows). WI-02b's refit needs this.
- **F7 -- the doc's "either/or" is both.** Refusing to build alone could not clear F7's check without
  seed rows. So: `fit_compound_cliff.py --fill-gaps` (fits nothing) writes a pending seed with a row
  for every needed (venue, season, compound) the seed lacks -- the latest *earlier* season's cell for
  the same `circuit_key` and compound, else `COMPOUND_DEFAULTS` -- and `assert_compound_params_cover_mart`
  (T5, error severity) refuses the build on any valid lap with a known compound and no cell. Run for
  2025, it added 5 rows (1,624 valid laps): são_paulo_grand_prix HARD (from 2022), MEDIUM and SOFT
  (from 2023), bahrain_grand_prix MEDIUM (from 2023), belgian_grand_prix INTERMEDIATE (class default).
  Promoted through `seed_writer` (the old seed is archived as `_archive/compound_cliff_params_2026-09-24.csv`).
  `int_compound_cliff_predicted` also stopped COALESCEing its pass-through `compound_cliff_onset_laps` /
  `compound_cliff_severity` / `compound_wear_gradient` to 999 / 0 / 0; after T5 the only cell-less laps
  are the quarantined ones with no compound, and they now read NULL. The curve's internal COALESCEs
  (in the shared macros) are unchanged and unreachable for a lap with a known compound.
- **F39 -- where the guard went, and three tests that had encoded the defect.** The guard is in
  `compound_cliff_wear_s` (and `cliff_ramp_frac`, which read an unknown depth as a full cliff);
  `int_compound_cliff_predicted` now calls that macro instead of the inline copy it carried at two
  sites, and `laps_past_cliff` and `expected_degradation_rate_s_per_lap` are NULL on an unknown age.
  The `not_null` tests on `compound_wear_s` / `expected_compound_pace_s` and on
  `fct_lap_residuals.compound_component_s` are now scoped to known-age laps: the last one had been
  passing on the fabricated value for 19 laps with a compound but no age (2025_1 BEA, 2025_13 SAI).
- **F39 -- what the fix does not do.** `int_lap_residual_decomposed` COALESCEs a NULL compound term to
  0, so the 4,107 laps' residuals move from about -10 s to about 0 s while the rest of the field sits
  near -2.5 s (F38's field compound cost): e.g. 2025_6's 19 quarantined driver-races average -0.03 s in
  `fct_driver_skill_features`, down from -10.11. The fabricated 10 s is gone, but those driver-races are
  still not comparable to their field until WI-01 removes the COALESCE (its acceptance already names
  it). None of these laps is training-eligible.
- **T29 lint -- scope and location.** `transform/tasks/coefficients/tests/test_sql_least_greatest_nullable.py`
  (the only transform pytest suite CI runs, rather than the audit's `ml/tests/` path), over
  `transform/models` and `transform/macros`. A call passes if its operands are NULL-proof by syntax, or
  sit inside CASE blocks that NULL-test every column they read; otherwise it needs a reviewed entry in
  `transform/tests/least_greatest_nullable.allowlist.json`. The 40 existing sites were reviewed with
  warehouse counts: 26 `not_null`, 4 `intended`, 10 `open` (a NULL would become the bound; not fixed here,
  out of WI-02a's findings). Two `open` sites fire today: `fct_cliff_prediction_features.survival_weight`
  is 4.0 instead of the COALESCE's 1.0 on the 4,088 unknown-compound rows (none eligible; the weight is
  off the training path). **Corrected by WI-13 (2026-09-25): the real size is 24,800 rows, 18,878 of them
  training-eligible** -- all of 2018 and later-season tail cells too; see WI-13's As built, and `int_constructor_deg_sensitivity.cliff_onset_shift_laps` is -3.0 (the
  harshest bound) instead of 0 on 1 of 233 cells whose `ref_depth` is NULL (feeds the ghost-car pages).
  The label clips -- the audit's latent sibling -- use a new `clamp_or_null` macro; no label value moved
  (0 NULL residuals today; the only differences outside stints whose residual changed are 1e-16 float
  noise, the same as two builds of unchanged code).
- **`verify_findings.py` F2 re-pointed.** Its query counted `notes like 'fitted from % via
  cox_km_survival'`, which F41 rewrote on 124 cells, so it would have fallen 337 -> 213 for a reason that
  is not F2. It now counts cells with any parameter `fitted` on its own season: 330 (the other 7
  cox_km cells are defaults on all three). Still PRESENT, as it should be until WI-02b. F41b's check is a
  text check and clears because the fitter now names `weight_corrected_lap_time`'s correction; the
  substantive evidence is T31's loader test and the dev check that `fuel_corrected_pace_s` equals
  normalized pace minus `weight_penalty_s` on every priced lap (max difference 0.0).
- **It moves 2025 features and labels.** F7's fix is by design a change to the ML contract's values
  for the cells it fills. On `fct_cliff_prediction_features`, 1,476 training-eligible 2025 rows (7.5%
  of 19,756) change features (the `compound_*` block, `expected_compound_pace_s`,
  `expected_degradation_rate_s_per_lap`, and `laps_past_cliff` / `cliff_onset_passed` on 530), 1,379
  change a label (933 on `next_5_lap_cumulative_jump_s`, mean |change| 1.50 s, max 12.1 s), and
  eligibility flips on 112 rows (89 in, 23 out) through `anomaly_class` -- F9's coupling of
  `clean_cliff` to `cliff_onset_passed`, which WI-02b owns. No 2018-2024 training-eligible row changes.
  No model was retrained.
