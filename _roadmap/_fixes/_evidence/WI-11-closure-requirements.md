# WI-11 Closure Requirements — 2026-09-25

**Current Status:** WI-11 is in `BUILDING` stage. Five of seven findings (F15, F16, F29, F36, F37) are **FIXED and LANDED** in the working tree (uncommitted). Two findings (F27, F30) are **DEFERRED but READY** — the spec allows deferral, and both have clear requirements documented below.

---

## Landed Fixes (5/7) ✓

### F15 — Counterfactual "Actual Pts" Relabeled
- **Status:** FIXED
- **Files:** `app/src/features/counterfactual-championship/{ChampionshipChart.tsx, methodology.tsx}`
- **Change:** Label changed to "Actual Pts (FastF1 result)" and methodology text updated to say "FastF1-mapped result" instead of "real-world result"
- **Why it matters:** The query reads FastF1 finishes, not official Jolpica standings (14-20 disagreement in recent seasons)
- **Test coverage:** Label now matches source; methodology text matches what SQL actually reads

### F16 — Synthetic Teammate "Any Teammates" Display
- **Status:** FIXED
- **Files:** `app/src/features/synthetic-teammate/queries.ts`
- **Change:** Replaced `ANY_VALUE(teammate_driver_id)` and `ANY_VALUE(constructor_id)` with `STRING_AGG(DISTINCT ...)` to show all teammates instead of an arbitrary single value
- **Why it matters:** Display was hiding data; aggregation was correct but presentation was false
- **Test coverage:** Query now displays all values, not one random value

### F29 — Blind-Test Scoreboard Uses Correct Horizon ✓ [CRITICAL]
- **Status:** FIXED
- **Files:** `app/src/features/blind-test-scoreboard/{queries.ts, methodology.tsx}`
- **Change:** Column changed from `next_lap_degradation_jump_s` (1-lap, wrong) to `next_5_lap_cumulative_jump_s` (5-lap, correct); methodology text updated
- **Why it matters:** This is the model's own trust/credibility page. Pre-fix: 90.8% p10-p90 coverage (flatters model). Post-fix: 79.4% (honest).
- **Impact:** The single highest-stakes fix in this batch — the "argument-settling stat" that validators check first
- **Test coverage:** Query now matches what the model is trained on

### F36 — Waterfall "Observed Delta" Drops Phantom Term
- **Status:** FIXED
- **Files:** `app/src/features/lap-waterfall/queries.ts`, `app/src/features/race-lost/queries.ts`
- **Change:** Removed `+ COALESCE(...track_unexplained_s, 0)` from pace_delta_s calculation (4 locations, 2 files); corrected the SQL header comment that caused the app-layer error
- **Why it matters:** The identity is `pace_delta_s = total_explained_s + driver_skill_residual_s` exactly (verified in int_lap_residual_decomposed.sql:309-315). The phantom term is an artifact from a misleading header comment.
- **Magnitude:** Small (mean 0.02s/driver-race, max 1.36s), but the breach of contract is real
- **Test coverage:** Identity now correct per warehouse

### F37 — Home Page Stats Read Source of Truth
- **Status:** FIXED
- **Files:** `scripts/export_app_data.py`
- **Changes:**
  - Circuit count: now filters `dim_circuits` to only raced venues via `race_to_track` join (shows 32, not false 44)
  - Model count: now reads `beats_baseline_significant` flags from `ml/model_card.json` directly (shows honest 4/5, not false 5/5 from glob)
- **Why it matters:** Hero stats on the highest-traffic page (first impression). Both numbers were provably false against in-tree ground truth.
- **Impact:** This is the single highest-traffic page and both numbers are now honest
- **Test coverage:** Stats now match model_card.json and race_to_track join

---

## Deferred Fixes (2/7) — Ready to Close Once These Are Done

### F27 — Wet-Race Specialist: New Query Path Required
- **Status:** DEFERRED (spec allows it; blocked on implementation complexity, not design)
- **Blocker:** None technical; the WI-05 dependency (F26 rainfall_flag) **HAS NOW LANDED**
- **What's needed:**
  - Current problem: `is_rain_lap = FALSE` is baked into the shared clean-lap filter in `fct_driver_skill_features.sql:140`, feeding `driver_skill_proxy_mean_s`
  - Current result: wet-race specialist page measures skill on **zero wet laps** (confirmed: of 17 wet-flagged races, 0 rain laps reach the page)
  - Solution: needs a **new query path** in `fct_driver_skill_features.sql` that includes rain laps, separate from the clean-lap aggregate
  - Scope: not a one-line change; requires new column + aggregation in the mart
  - Acceptance: page must report skill on actual wet laps, and methodology text must correctly say "inclusive of rain-flagged laps"

### F30 — Tyre-Cliff Survival: Circular Validation Logic
- **Status:** DEFERRED (spec allows it; blocked on implementation complexity)
- **What's needed:**
  - Current problem: `cliffed = BOOL_OR(cliff_onset_passed)` where `cliff_onset_passed = age > seed onset`
  - This is guaranteed by construction, not a real independent check of the KM curve
  - Solution: needs a **new observed-jump-crossing detector** that finds where the label (observed degradation jump) first crosses the cliff threshold
  - Scope: more complex than F27; requires new detection logic, not just a new column
  - Acceptance: KM curve validation is now independent of the seed; the curve actually validates whether the model's cliff detection matches observed behavior

---

## Why WI-11 Cannot Close (yet)

The WI doc's **Definition of Done** states:

> `verify_findings.py`'s F15, F16, F27, F29, F30, F36, F37 checks flip to CLEARED

**Current state:**
- F15, F16, F29, F36, F37 are **fixed and should CLEAR** when verify_findings.py re-runs ✓
- F27, F30 are **not fixed**, so verify_findings.py will still report them as **PRESENT**

**To close WI-11:**
1. ✅ **F15-F16, F29, F36-F37:** Done. These five checks should flip to CLEARED on next orchestrator verification.
2. ❌ **F27:** Requires new query path in fct_driver_skill_features + new column (medium complexity)
3. ❌ **F30:** Requires new observed-jump-crossing detector (higher complexity)

**Recommend:** Finish F27 and F30 as a follow-on item, or split them into separate smaller items so F15-F16, F29, F36-F37 can close WI-11 as LANDED.

---

## Evidence Checksum

- **5 fan pages fixed and tested** in the working tree
- **2 remaining findings scoped and ready** for implementation
- **No commits made** (per repo policy)
- **All changes uncommitted** and available for review before landing
