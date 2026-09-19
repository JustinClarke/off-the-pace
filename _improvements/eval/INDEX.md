# Evaluation Sections — Organized by Item

Each folder holds a self-contained section ready for independent decision and landing.

## Status Summary

| Item | Status | Ready to Land? | Key Decision |
|:---|:---|:---:|:---|
| **08e** | ✅ GATED, def-of-done complete | 🟡 Awaiting human call | Split from D3? Land 08e now (thermal family clears v12 on all five targets) |
| **08f** | ✅ GATED, both halves complete on v12/08m (2026-09-17) | 🟡 Awaiting human call (bundled with 08e under D3) | 08f-2 closed (zero effect on every live target, proven algebraically). 08f-1 gated in isolation for the first time: a real fix (93.3% of training-row IPW weights change) whose effect on all five headline metrics is inside noise on every target — clean null, not a win or a cost. See `08f/README.md`. |
| **08g** | 🟡 CLOSED (decomposition) | ✅ Closed | Already landed in prior session |
| **08h** | ✅ MEASURED and **REJECTED** on v12/08m (2026-09-17) | ✅ Closed — nothing to land | `baseline_observations_n` stays out of `FEATURE_COLUMNS`; contract stays 32. 0 of 5 families clear their floor (best 0.98×). Rejection pinned by a test. See `08h/README.md` |
| **08i** | GATED (min obs floor) | ❌ No | Trade not taken in 08e rebuild (priced separately) |
| **08m** | MEASURED (target rebuild) | ✅ Already landed | Prior session completed; v12 substrate now live |
| **08n** | LANDED (artefact rebuild) | ✅ Already landed | Prior session completed; model artefacts exported |
| **10c** | ✅ MEASURED on v12/08m (2026-09-18) — verdict refreshed, replaces 2026-09-10 | ✅ Closed — nothing to land (no arm) | Cause-specific metrics now reported **with a dependence band, never as a point**. The band on green-pit IPCW-Brier is **19.7× the reseed floor and wider than 24-race sampling noise**, so the level is dominated by an unidentifiable parameter while the ranking is not. Headline names its cause; product limitation stated. See `10c/README.md` |

---

## Folder Structure

### 08e/ — Thermal-proxy stint baseline reaches forward
- **State:** GATED + all gates passed + re-read on v12 complete (2026-09-17)
- **Contents:**
  - `README.md` — full status, problem, fix, all work completed
  - `MEASUREMENTS.md` — materiality tables, gate tables, re-read results
  - `NEXT_STEPS.md` — decision points and landing procedure
  - `08e_thermal_family_arms.json` — artefact with all fits and e-values
  - `08e_thermal_family_arms.log` — generation log

- **Decision required:** Land separately from D3 (thermal clears v12 on all five targets) or wait for 08f?
- **Next step:** Update build-log.json if landing: change stage to LANDED, advance pointer

---

### 08f/ — Cross-season pooled statistics in the feature lineage

- **State:** **GATED, both halves complete, 2026-09-17.** 08f-2 closed (not re-measured — its
  effect on every live target is proven exactly zero). 08f-1 gated in isolation for the first time
  ever, on the current v12/08m substrate.
- **Contents:**
  - `README.md` — both halves: 08f-2's label-impact closure, 08f-1's isolated gate, the overall
    08f verdict
  - `MEASUREMENTS.md` — full tables for both halves
  - `08f1_gate_arms.json` / `.log` — 08f-1's per-seed fits, weight-vector summaries, permutation
    null, e-values
- **08f-2 (closed, not reopened):** moves `driver_skill_residual_s` substantially (mean |Δ| 0.084s
  on 99.7% of rows) but moves every actual target — `next_5_lap_cumulative_jump_s`
  (`DEGRADATION_TARGET`), `drift_s_per_lap`, `laps_until_cliff_class` (`CLIFF_TARGET`) — by
  exactly zero (float noise, max |Δ| ~1e-14), for a proven algebraic reason: the 08f-2 shift is an
  exact constant per (race_year, race_id, constructor_id), and every target is built from
  within-stint differences, so the constant cancels. No add-ablation gate is meaningful for a
  change that provably touches zero live features and zero targets.
- **08f-1 (gated 2026-09-17):** isolated-warehouse A/B, season-lagged (AFTER, shipped) vs
  season-pooled (BEFORE, pre-fix) IPW weights, through `evaluate.py`'s own `_fit`/`_score`. The
  weight vector itself moves substantially (93.3% of training rows change, mean 1.711→1.970), but
  every one of the five headline deltas is inside its own 5-reseed floor (p10 0.49×, p50 0.15×,
  p90 −0.07×; cliff/stint-life exactly 0 by construction — `survival_weight` never reaches either).
  A real fix, a clean null on the headline.
- **Overall verdict:** 08f is `GATED` on the current substrate. Landing is still bundled with 08e
  under decision `D3` — not decided here.

---

### 08g/ — (Already closed)
Decompose the 08e/08f regression. Already landed; reference only.

---

### 08h/ — `baseline_observations_n` as a feature

- **State:** **MEASURED and REJECTED, 2026-09-17, on the v12/08m substrate.** Terminal.
- **What it is:** The add-ablation `08e` deferred — does the model want the count of valid prior
  laps behind each row's thermal baseline? (Note: this is *not* the min-observations floor; that
  is `08i`, a different item.)
- **Contents:**
  - `README.md` — the question, the two spec corrections, the method, why the first pass misread
    the pair arm
  - `MEASUREMENTS.md` — per-family tables, the pair-arm decomposition, the declarability ruling
  - `../../../ml/artefacts/08h_baseline_observations_n_arms.json` / `.log`
- **Result:** 0 of 5 families clear their own 5-reseed floor (best: p50 at 0.98×). 0 of 5 clear on
  information. `stint_life_regressor`'s information delta is negative. No synergy with
  `push_residual` on any family — the pair arm's size is `push_residual`'s own signal. The column
  is ρ = 0.97 with `lap_in_stint`, already in the contract.
- **Ruling:** stays out of `FEATURE_COLUMNS`; stays in the mart as the companion column consumers
  need to condition on the thermal NULLs. The declarability hazard is **declined**, not deferred.
- **Next step:** none. Pinned by
  `ml/tests/test_features.py::test_baseline_observations_n_is_never_a_feature`.

---

### 08i/ — The min_observations floor

- **State:** GATED 2026-09-18 — gate steps 1–7 run on floors 1/2/3/5, all five families, on the
  v12/`08m` substrate. Step 1a reproduces the published v12 headline to `0.00e+00`; step 1b's
  floor-parameterised replica reproduces the **built** thermal block bit-for-bit (137,447 rows).
- **Premise correction:** the substrate was **already floor 2**, not floor 1 — set 2026-09-10 and
  carried into git inside commit `c49473a`, whose message does not mention it. The BEFORE arm is
  floor 2 and floor 1 is a revert. The 2026-09-10 session left no artefact, and its "floors 2 and
  3 give identical headlines in all five families" claim is refuted.
- **Result:** **the trade does not exist.** Higher floors cost coverage *and* signal. Floors 3
  and 5 clear their own floor **in the wrong direction** on p10, p90 and cliff (−2.10× / −1.44× /
  −1.11× and −2.29× / −1.57× / −1.00×), with every missingness-only control small — destroyed
  information, not NaN density. Coverage: 98.20 / 96.05 / 90.70 / 80.35%.
- **Ruling:** floors 3 and 5 **rejected**. **Floor 1 recommended** over the built floor 2 — best
  on all three degradation heads, clears on p50 at +1.25× (`E`=13.5), never worse than its own
  floor anywhere, +2.15pp coverage. Recorded honestly as a *preference*, not a majority clear:
  the pre-registered rule asked for a majority and floor 1 clears on one of five.
- **Next step:** decision **D10** — landing floor 1 costs a warehouse rebuild plus a retrain and
  re-export of all five artefacts. Also two live defects: `assert_no_future_leakage.sql`
  hard-codes the floor at 2, and `schema.yml` still documents floor 1.

---

### 08m/ — The severity units bug
*(Reference only — already landed prior session)*

Warehouse rebuild against fixed target. v12 substrate now live.

---

### 08n/ — Rebuild model artefacts
*(Reference only — already landed prior session)*

Model artefacts exported against v12 contract (32 features).

---

### 10c/ — Competing-risks evaluation, with the dependent-censoring caveat quantified

- **State:** **MEASURED, 2026-09-18, on v12/08m.** Replaces the 2026-09-10 verdict, which `10b`
  §10 had already ruled doubly superseded (in-sample, *and* measured under the rejected `10b`
  label). Gates 1, 2 (substituted), 3 and 5 run; 4 and 7 inapplicable and stated.
- **Contents:**
  - `README.md` — the three framings, the band, the three widths, D-calibration, what landed
  - `eval_10c_cause_specific_framework.json` / `.log` — every framing, every τ, floors, bootstrap
- **Headline:** on the tyre-limit set, the *realised* green-pit ending is predicted with IPCW-Brier
  **0.1904** / AUC **0.6896** [0.639, 0.734]; the same model read as the *latent* tyre limit scores
  **0.1452**, bracketed **[0.1367, 0.1729]** across Kendall's τ ∈ [−0.5, +0.5].
- **Why it matters beyond the item:** the framing choice is worth 0.045 Brier and the dependence
  band a further 0.036 — both larger than `10e`'s S1x, the biggest model improvement this campaign
  has measured (0.023). `10d` and `10e`'s *comparisons* stand (the band is common-mode within a
  fixed framing and cancels); their *levels* should not be quoted without the framing named.
- **Decision required:** none. No arm, nothing to land. The open work is an instrument for SC
  arrival (`02d` / `07a`), a τ-aware D-calibration, and `R3`'s option 1 — a model that actually
  targets the cause-specific hazard.

---

## How to Use This Structure

**When you decide to land 08e:**
1. Review `08e/README.md` and `08e/MEASUREMENTS.md` one more time
2. Follow the procedure in `08e/NEXT_STEPS.md`
3. Once landed, 08e folder becomes part of the project history; archived or moved to docs

**When you decide on 08f:**
1. Review `08f/README.md` and `08f/MEASUREMENTS.md` (the 2026-09-17 label-impact probe)
2. Decide the remaining 08f-1 scope (see options above)
3. Same handoff procedure

**For 08i:** Same pattern — work lives in its folder until ready to land, then folds into the
project. (**08h is done** — measured, rejected, and terminal; nothing to land.)

---

## Quick Navigation

- **Want the headline?** → `08e/README.md`
- **Want to see the numbers?** → `08e/MEASUREMENTS.md`
- **Ready to land 08e?** → `08e/NEXT_STEPS.md`
- **Want the artefact?** → `08e/08e_thermal_family_arms.json`
