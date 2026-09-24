# WI-02 — Compound seed: provenance first, point-in-time refit second

**Group:** 08 foundations · **Depends on:** F41 (this file) must land before the refit; benefits from
`WI-05`'s bronze QA landing first (F2's fits consume stint boundaries F24/F25 show are wrong in 3+
races) · **Blocks:** `WI-08` (shares the seed)
**Blocker:** existing human ruling needed — 00c's leakage standard vs. the spine's same-race
exemption, applied to this specific case (see below). The magnitude is already measured, so this is
a decision, not more measurement.

**Findings folded in:** F2 (High), F7 (Medium), F9 (Medium→Medium, reclassified up), F39
(Low-Medium), F41 (Medium-Low).

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
