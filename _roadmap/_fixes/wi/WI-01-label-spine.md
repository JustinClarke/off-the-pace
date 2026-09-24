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
   stop drawing a spurious per-team, per-circuit shift.
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
