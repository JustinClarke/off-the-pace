# WI-12 — 06b re-measure after the label bump

**Group:** 06 publication · **Depends on:** `WI-01` (θ_air must be re-estimated first) ·
**Blocker:** WI-01.

**Findings referenced:** F23, F48 (θ_air), via `WI-01`. No independent F-number of its own — this is
a publication task, not a code fix.

---

## Why this exists

06b's published claim ("dirty air's cost fell by roughly two thirds and shows no detectable
directional cost from 2021-2024") was measured on θ_air as calibrated on F1's fabricated laps
(0.152, as-built). Reconfirmed by direct re-run of 06b's own estimator on the measured-lap panel:
θ **0.416** with every 95% CI excluding zero — the decline survives at roughly −0.05/season, but
"nothing there" does not. F48's feature-coding fix (WI-15) moves it again, 0.416 → 0.443, once
DRS-open closest-followers are coded correctly.

## Method

1. Wait for `WI-01` (F1's fabrication fix + the θ re-estimation step) and `WI-15`'s F48 feature-coding
   fix to both land — θ should be estimated exactly once, on the fully-corrected panel, not twice.
2. Re-run 06b's pre-registered ladder (the same panel SQL, same fixed-effects spec, same placebo
   checks) against the corrected θ.
3. Re-rule the lead-placebo interpretation: on the measured-laps arm, lag already exceeds lead by
   ~1.6-2× in 2021-2024, where 06b's published ruling was "lag ≈ lead ≈ 0" — this needs to be
   re-stated, not just the point estimate.
4. Rewrite the published claim and the dirty-air-cost app page's methodology text
   (`dirty-air-cost/methodology.tsx:19` currently says "per-circuit OLS coefficient" when it's one
   global θ — fix that wording regardless of the re-measure's outcome).

## Acceptance

- The published 06b claim is re-measured on the corrected label and panel, not the fabricated one.
- The re-measure states plainly whether "no detectable directional cost 2021-2024" survives (current
  evidence says it does not).
- The app page's methodology text matches the actual estimator (one global θ, not per-circuit).

## Definition of done

06b's ladder is re-run once, after both upstream fixes land; the published finding and the app page
are updated together, not independently (to avoid a second round of doc drift like F20's).
