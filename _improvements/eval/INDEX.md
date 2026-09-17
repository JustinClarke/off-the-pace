# Evaluation Sections — Organized by Item

Each folder holds a self-contained section ready for independent decision and landing.

## Status Summary

| Item | Status | Ready to Land? | Key Decision |
|:---|:---|:---:|:---|
| **08e** | ✅ GATED, def-of-done complete | 🟡 Awaiting human call | Split from D3? Land 08e now (thermal family clears v12 on all five targets) |
| **08f** | ✅ GATED, both halves complete on v12/08m (2026-09-17) | 🟡 Awaiting human call (bundled with 08e under D3) | 08f-2 closed (zero effect on every live target, proven algebraically). 08f-1 gated in isolation for the first time: a real fix (93.3% of training-row IPW weights change) whose effect on all five headline metrics is inside noise on every target — clean null, not a win or a cost. See `08f/README.md`. |
| **08g** | 🟡 CLOSED (decomposition) | ✅ Closed | Already landed in prior session |
| **08h** | MEASURED (future add-ablation) | ❌ No | Deferred from 08e; price when ready |
| **08i** | GATED (min obs floor) | ❌ No | Trade not taken in 08e rebuild (priced separately) |
| **08m** | MEASURED (target rebuild) | ✅ Already landed | Prior session completed; v12 substrate now live |
| **08n** | LANDED (artefact rebuild) | ✅ Already landed | Prior session completed; model artefacts exported |

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

### 08h/ — baseline_observations_n as a feature
*(Placeholder for future add-ablation)*

- **State:** MEASURED
- **What it is:** The minimum-observation floor that 08e deferred
- **Next step:** Price as an add-ablation when ready; populate this folder with results

---

### 08i/ — The min_observations floor
*(Placeholder for trade pricing)*

- **State:** GATED (priced but not taken in 08e)
- **What it is:** Floors of 2/3/5 buy more degradation signal (priced at −3.49pp / −8.82pp / −19.09pp coverage)
- **Next step:** Run through gates if taking the higher floor; populate with results

---

### 08m/ — The severity units bug
*(Reference only — already landed prior session)*

Warehouse rebuild against fixed target. v12 substrate now live.

---

### 08n/ — Rebuild model artefacts
*(Reference only — already landed prior session)*

Model artefacts exported against v12 contract (32 features).

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

**For 08h / 08i:** Same pattern — work lives in its folder until ready to land, then folds into the project.

---

## Quick Navigation

- **Want the headline?** → `08e/README.md`
- **Want to see the numbers?** → `08e/MEASUREMENTS.md`
- **Ready to land 08e?** → `08e/NEXT_STEPS.md`
- **Want the artefact?** → `08e/08e_thermal_family_arms.json`
