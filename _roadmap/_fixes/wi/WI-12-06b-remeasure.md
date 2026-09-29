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

**W47 note (standing hazard):** `theta_air_label_value` is a frozen external fit, re-estimated here
on the WI-01 label and applied inside dbt thereafter. Future items that move the calibration panel
(WI-02b's seed refit, FD6 ruling, new seasons) must re-run the d1/d2 scripts and update the var if
the F2 coefficient changes. See [`THETA_AIR_LABEL_VALUE_PROCEDURE.md`](../THETA_AIR_LABEL_VALUE_PROCEDURE.md)
for the automated procedure.

## Gate results: the 06b ladder on the WI-01 label (2026-09-27, opus-5)

**Re-run on the final label (W40, 2026-09-27).** The W40 ruling moved the label's `theta_air`
from WI-01's interim pooled 0.503 to **0.331**, the final value. `data/dev.duckdb` was rebuilt
with 0.331 and `d1`/`d2` re-run on it, so every table below is from the re-measure on the final
(0.331) label. The headline numbers (theta **+0.19 to +0.35 s/lap in 2021-2024** and **+0.382 in
2025**, every interval clear of zero) are the final-label numbers. They are also identical to the
first run on the 0.503 build, and have to be. The 06b ladder does not read the label's theta: it
estimates theta per season from the calibration panel, whose outcome (lap - base - fuel - tyre
cost) sits upstream of the label's theta. The rebuilt lap panels are identical in content to the
first run's, `d2`'s printed tables are identical (only two W-section labels were renamed), and
full-precision fits differ by at most 4.6e-8 (row-order noise in pyfixest's demeaning). The label's
0.331 is itself this section's pooled F2 estimate (the W40 table below), and `d2` now stops if the
two disagree at 3 dp.

**What the gate is.** WI-12's gate is 06b's own pre-registered ladder (`work/06-publication.md`
06b: F0-F3 rungs, the lead placebo, the 2022 era contrast, the corner split), re-run on the
corrected label and panel. It is not an ML benchmark: no model is trained or scored here. The
deferred ML gate steps for the label change are W21/W24's (steps 1-4, 6, 7 and 08e, owed by
WI-15a/WI-15b once the label settles), and this item did not run them.

**Upstream state when run.** WI-15a LANDED. WI-01 MEASURED, not LANDED: its verification-pass build
is in `data/dev.duckdb` (theta_air 0.5033 at the first run and 0.331 at the W40 re-run, 5-term
identity, `event_driven` and lap-after-restart excluded, unknown-tyre laps out of the base). If
WI-01's orchestrator re-run changes the calibration panel, these numbers need re-running (the
scripts make that one command), and so does the label's declared theta (the W40 gate in `d2`).

**Evidence.** `_roadmap/_fixes/_evidence/wi-12-2026-09-27/` holds the scripts, the committed lap
panels, `d2_output.txt` (every table quoted below) and `wi12_fits.json`. Read-only against the
warehouse.

### Gate 1: reproduction (both pass)

- **The panel is the shipped one.** The rebuilt panel is `int_dirty_air_tax_component`'s
  `calibration_panel` on the WI-01 label: 138,970 laps (= the shipped `calibration_sample_n`), and
  its pooled OLS slope is 0.5033413666 against the shipped `theta_air` 0.5033413666 (|d| 3.3e-15).
  At the W40 re-run the model applies the declared 0.331 instead, so the gate checks the pooled
  slope against 0.5033413666 as a fingerprint of the panel (|d| 1.0e-15) and checks that the shipped
  `theta_air` equals the declared var (|d| 0). Both pass.
- **The estimator is 06b's.** 06b's committed panel (`implementations/06b/panel_06b_lap.parquet`)
  through this item's fit code returns 06b's published F2 table in all seven seasons, plus its era
  contrast (-0.2188), trend (-0.0667/season) and all six placebo boundaries exactly. The
  2026-09-25 pre-WI-15a/WI-01 warehouse (`dev_unfixed.duckdb`) does **not** reproduce 06b
  (2018: 16,488 laps vs 14,850; WI-02a/WI-05/WI-09/WI-13 had landed), so it is used only as an
  intermediate arm in the decomposition below, never as "before".

### Result 1: per-season theta, the headline (F2: stint FE + six tyre-age bins, race-clustered)

| Season | n | G | 06b published | **WI-01 label** | 95% CI |
| :--- | ---: | ---: | ---: | ---: | :--- |
| 2018 | 15,600 | 20 | +0.396 | **+0.511** | [+0.375, +0.647] |
| 2019 | 18,539 | 21 | +0.151 | **+0.435** | [+0.296, +0.573] |
| 2020 | 13,131 | 17 | +0.170 | **+0.297** | [+0.208, +0.386] |
| 2021 | 17,872 | 20 | +0.083 | **+0.347** | [+0.264, +0.431] |
| 2022 | 14,609 | 20 | +0.011 | **+0.275** | [+0.213, +0.337] |
| 2023 | 18,864 | 22 | +0.045 | **+0.194** | [+0.113, +0.274] |
| 2024 | 20,450 | 23 | -0.036 | **+0.271** | [+0.183, +0.359] |
| 2025 | 19,614 | 23 | (not fitted) | **+0.382** | [+0.255, +0.509] |

All four rungs, every season (every interval excludes zero on every rung):

| Rung | 2018 | 2019 | 2020 | 2021 | 2022 | 2023 | 2024 | 2025 |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| F0 pooled OLS | 0.720 | 0.644 | 0.581 | 0.373 | 0.455 | 0.346 | 0.416 | 0.603 |
| F1 driver x race | 0.600 | 0.560 | 0.428 | 0.399 | 0.304 | 0.277 | 0.283 | 0.418 |
| **F2 stint + age bin** | **0.511** | **0.435** | **0.297** | **0.347** | **0.275** | **0.194** | **0.271** | **0.382** |
| F3 F2 minus laps near SC/VSC/red/pit | 0.505 | 0.466 | 0.296 | 0.349 | 0.250 | 0.207 | 0.279 | 0.391 |

### Result 2: "no detectable directional cost 2021-2024" does not survive

**It does not survive.** On the corrected label, theta in 2021-2024 is +0.19 to +0.35 s/lap with every
interval clear of zero on every rung, and the part of it the lead placebo can certify as
directional (lag minus lead, Result 3) is detectable in 2021 (+0.108 [+0.020, +0.196]), 2022 (+0.080
[+0.004, +0.157]) and 2023 (+0.095 [+0.026, +0.164]). Only 2024's directional part is not
distinguishable from zero (+0.059 [-0.035, +0.153]). The published "nothing there" came from the
fabricated base (F1/F23a): see Result 6.

### Result 3: the lead placebo, re-ruled

Joint fit `y ~ D_lag1 + D_lead1 | stint + age bin`, race-clustered. The lag-minus-lead contrast and
its CI come from the fit's own covariance matrix. **Rule, written into `d2` before its first run
(so before any WI-01 placebo fit, though the audit's round-2 placebo numbers were already known)
and applied identically to 06b's panel:** *holds* = lag > 0, lag/lead >= 2 and the lag-minus-lead
CI excludes 0; *marginal* = lag > 0 and lag/lead >= 1.3 (06b's marginal 2019 was 1.34); *fails*
otherwise.

| Season | lag | lead | lag/lead | lag - lead [95% CI] | ruling (WI-01) | 06b's panel, same rule |
| :--- | ---: | ---: | ---: | :--- | :--- | :--- |
| 2018 | 0.432 | 0.244 | 1.77 | +0.188 [+0.093, +0.283] | marginal | holds (0.365 / 0.132) |
| 2019 | 0.379 | 0.205 | 1.85 | +0.174 [+0.063, +0.285] | marginal | marginal |
| 2020 | 0.241 | 0.188 | 1.28 | +0.053 [-0.012, +0.117] | fails | marginal (06b said holds) |
| 2021 | 0.290 | 0.182 | 1.59 | +0.108 [+0.020, +0.196] | marginal | fails |
| 2022 | 0.236 | 0.155 | 1.52 | +0.080 [+0.004, +0.157] | marginal | fails |
| 2023 | 0.172 | 0.077 | 2.24 | +0.095 [+0.026, +0.164] | holds | fails |
| 2024 | 0.223 | 0.164 | 1.36 | +0.059 [-0.035, +0.153] | marginal | fails |
| 2025 | 0.310 | 0.208 | 1.49 | +0.101 [+0.019, +0.183] | marginal | (not fitted) |

The rule reproduces 06b's rulings except 2020, where 06b read a 4.1x ratio as "holds" and the rule
also asks for the contrast's CI to clear zero (it does not: [-0.022, +0.265]).

**Re-ruling.** 06b's ruling was "holds 2018/2020, marginal 2019, fails 2021-2024 (lag ~ lead ~ 0)".
On the corrected label the picture is different in kind, not just in level:
- **The lead is material in every season** (joint lead +0.08 to +0.24). Next lap's air state is
  associated with this lap's pace everywhere, so no season's theta is a clean causal cost of
  following. Part of every number is a persistent-traffic state.
- **The lag exceeds the lead in every season** (1.3-2.2x), and the lag-minus-lead contrast excludes
  zero in six of eight seasons (all but 2020 and 2024). That contrast (+0.05 to +0.19 s/lap by
  season; pooled 2018-2025 F2 +0.107 [+0.078, +0.137] against a joint lag of 0.280) is the part of
  the cost the design can certify as directional.
- **The late era is no longer the failing era.** On the F3 sample (no laps near SC/VSC/red/pit)
  the contrast clears zero in every season except 2024, and 2019 and 2023 reach "holds".

**Publishable wording:** per-season theta is "the lap-time cost associated with having followed on
the previous lap". Between a fifth and a half of it, depending on the season, is directional by the
placebo (lag minus lead against the F2 theta: 18% in 2020 to 49% in 2023, 32% pooled), and that
part is detectable in every season except 2020 and 2024. It is not "a measured causal cost of following", and not
"no detectable directional cost".

### Result 4: the 2022 question on 06b's pre-registered window (2018-2024): survives in shape

| | 06b published | WI-01 label |
| :--- | :--- | :--- |
| theta 2018-2021 (F2 era fit) | +0.185 [+0.115, +0.255] | **+0.396 [+0.339, +0.454]** |
| theta 2022-2024 | +0.004 [-0.066, +0.075] | **+0.245 [+0.200, +0.291]** |
| Delta (pooled era x D interaction) | -0.219 [-0.331, -0.106] | **-0.241 [-0.326, -0.156]** |
| linear trend, per season | -0.0667 [-0.0963, -0.0371] | **-0.0651 [-0.0876, -0.0426]** |
| Delta, 2018 dropped | -0.163 | **-0.195 [-0.287, -0.104]** |
| Delta, 2018+2019 dropped | -0.154 | **-0.152 [-0.241, -0.063]** |

Placebo boundaries, WI-01 label: >= 2019 -0.303, >= 2020 -0.274, >= 2021 -0.218, **>= 2022
-0.241**, >= 2023 -0.223, >= 2024 -0.151. Every one excludes zero, and 2022 sits in the middle.

**What survives:** the decline is gradual, it starts before 2022, a step test fires at every
boundary, and the regulations cannot be credited on this evidence. The slope is almost
unchanged (-0.065 vs -0.067/season). **What does not survive:** "fell by roughly two thirds" (now
roughly halved, 0.40 -> 0.25 by era and 0.51 -> 0.27 from 2018 to 2024) and "gone by 2022" /
"indistinguishable from zero from 2021" (2022-2024 is +0.245 with the interval well clear of zero).

### Result 5: 2025, the out-of-sample test 06b named in advance, breaks the trend

06b's post named "the same fit on a season this analysis has never seen" as the test: "if the trend
is real and continues, theta stays at or below zero". On the corrected label the 2018-2024 trend
extrapolates to **+0.075** in 2025; the fit gives **+0.382 [+0.255, +0.509]**. That is the highest value
since 2019, and the trend's prediction sits far outside its interval. With 2025 in the window the
slope halves (-0.040 [-0.061, -0.018]/season) and the >= 2024 and >= 2025 boundaries stop firing
(-0.072 [-0.168, +0.023]; +0.038 [-0.095, +0.170]). **A steady decline is no longer what the data
shows: it is a fall from 2018 to 2023, then a rebound.** Nothing here explains the rebound. Two
caveats. 2025 is not pristine for this series, because the audit's round 2 already fitted it (0.245 on
the measured arm). Its data also moved under WI-02a (W12). But it is outside every fit 06b made,
and it sits above 2022-2024 in every arm of the decomposition below, so it is not an artefact of
one change.

### Result 6: what moved the numbers (per-season F2 theta by arm)

| Arm | 2018 | 2019 | 2020 | 2021 | 2022 | 2023 | 2024 | 2025 |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 0 06b committed panel (published) | 0.396 | 0.151 | 0.170 | 0.083 | 0.011 | 0.045 | -0.036 | |
| 1 06b SQL, 09-25 warehouse (pre-WI-15a/WI-01) | 0.321 | 0.224 | 0.166 | 0.074 | 0.022 | 0.055 | -0.027 | 0.074 |
| 2 arm 1, measured-base laps only (F1/F23a removed) | 0.416 | 0.406 | 0.300 | 0.298 | 0.226 | 0.186 | 0.189 | 0.244 |
| 3 06b SQL, WI-01 warehouse (fabricated base, fuel only) | 0.415 | 0.271 | 0.154 | 0.213 | 0.099 | 0.105 | 0.156 | 0.245 |
| 4 arm 3, measured-base laps only | 0.516 | 0.410 | 0.254 | 0.330 | 0.236 | 0.179 | 0.243 | 0.339 |
| 5 WI-01 calibration panel, y without the tyre-cost term | 0.519 | 0.410 | 0.254 | 0.330 | 0.236 | 0.180 | 0.243 | 0.339 |
| **6 WI-01 calibration panel (headline)** | **0.511** | **0.435** | **0.297** | **0.347** | **0.275** | **0.194** | **0.271** | **0.382** |

- **Removing the fabricated base (1 -> 2) is the big move**: +0.10 to +0.22 in every season, and
  three of the four largest moves are 2021, 2022 and 2024 (+0.22, +0.20, +0.22). The laps F1 fabricated had a partial residual of about -1.4 s and
  were disproportionately "following" laps. That is what produced 06b's late-era zeros. The
  intermediate arm 2 agrees with the audit's round-2 measured arm (0.437 / 0.345 / 0.307 / 0.305 /
  0.221 / 0.185 / 0.192 / 0.245) to within about 0.02 outside 2019 (different substrate). The
  -1.4 s residual and the 39% vs 22% treated share are the audit's (F23), not re-measured here.
- **F48's coding plus WI-01's base redefinition (2 -> 4)**: -0.05 to +0.10, largest in 2018 and 2025.
- **WI-01's own calibration filters (4 -> 5)**: nil (<= 0.003).
- **Subtracting the lap's tyre cost (5 -> 6)**: -0.01 to +0.04. Within a stint with age bins the tyre
  term barely matters. It is the pooled estimator that it moves by 0.33 (W40 below).
- 06b's substrate to the 09-25 warehouse (0 -> 1): other landed items moved 2018 (-0.075) and 2019
  (+0.073) only.

### Result 7: the corner split (2018-2024, driver x race x corner FE + age bins, WI-01 treatment)

Apex-speed deficit (`mid_corner_residual_s`, 06b's Deviation-2 headline; x 0.2778 = fraction of apex
speed):

| Class | n (pre / 2022+) | pre | 2022+ | % apex speed | Delta [95% CI] | 06b published Delta |
| :--- | ---: | ---: | ---: | :--- | :--- | :--- |
| slow < 125 km/h | 236,279 / 198,677 | +0.0450 | +0.0556 | 1.25% -> 1.54% | +0.0067 [-0.0033, +0.0166] | -0.0001 |
| medium 125-199 | 161,415 / 110,903 | +0.0518 | +0.0484 | 1.44% -> 1.35% | -0.0071 [-0.0179, +0.0037] | -0.0023 |
| fast >= 200 | 29,646 / 28,512 | +0.0401 | +0.0294 | 1.11% -> 0.82% | -0.0119 [-0.0316, +0.0077] | -0.0114 |

- Still ordered as the aero mechanism predicts (fast falls most, slow does not fall), and none of the
  three is distinguishable from zero. The fast-corner interval now runs from removing 79% of the
  pre-2022 deficit to making it 19% worse; half-width 1.65x the estimate, about 2.7x the fast-corner
  sample needed to resolve it (06b: 1.78x, 3.2x). Fast corners are 7.6% of corner-rows (06b's own
  panel: 7.6%); 06b's post and work doc say 15%, which is the share of corner *cells* from its
  pre-registration probe, not of rows. Corrected in the rewritten post.
- **The "precise half" changed.** Slow-corner deficit by season: 0.038 / 0.045 / 0.048 / 0.050 /
  0.054 / 0.053 / 0.059 (1.0% -> 1.6% of apex speed, 2018 -> 2024), and every interval excludes zero.
  06b's "about 0.9%, exactly as in 2018" becomes "about 1.0% in 2018 and about 1.6% in 2024". The
  cornering deficit did not shrink. If anything it grew, while the lap-level cost halved.
- **The pre-registered total (`corner_residual_total_s`) now has a fast-corner Delta that clears
  zero:** -0.0525 [-0.1019, -0.0030] (slow -0.0133, medium -0.0216, both spanning zero). 06b's
  Deviation 2 stands: the total sums `braking_loss_s`, whose sign runs the other way, so this cannot
  be read as "less time lost in fast corners". It is reported, not interpreted, and one of three
  tests at p ~ 0.04.
- Why the corner levels moved when the corner outcome did not: the treatment did. F48 now codes the
  closest (sub-1 s, DRS-open) followers as treated, and the panel lost the fabricated-base laps.

### W40: which estimator should price the label (pooled over the label's 2018-2025 window)

**Ruled 2026-09-27: F2, 0.331.** The label now carries 0.331 (`theta_air_label_value`). W40 is
RESOLVED. The table is as measured. At the time, F0 was what the label carried.

| Estimator | n | theta | 95% CI |
| :--- | ---: | ---: | :--- |
| F0 pooled OLS (WI-01's interim label value) | 138,970 | 0.503 | [0.446, 0.561] |
| F0, constructor term also subtracted | 138,970 | 0.363 | [0.312, 0.413] |
| constructor x race FE | 138,966 | 0.435 | [0.379, 0.491] |
| F1 driver x race FE | 138,935 | 0.397 | [0.354, 0.440] |
| F1 + tyre-age bins | 138,935 | 0.297 | [0.256, 0.338] |
| stint FE only | 138,679 | 0.433 | [0.386, 0.480] |
| **F2 stint FE + tyre-age bins (06b's pre-registered headline; the label's value since W40)** | 138,679 | **0.331** | **[0.293, 0.370]** |
| F2, y without the tyre-cost term | 138,679 | 0.312 | [0.274, 0.350] |
| F3 | 120,467 | 0.337 | [0.298, 0.376] |

Mean by treatment arm (D_lag1 = 0 / 1): modelled tyre cost **1.413 / 1.082 s** (treated laps carry
0.33 s *less*); constructor term -0.070 / +0.071 (treated laps are in slower cars, +0.14). Within
stint + age bin the tyre term does not differ by treatment (-0.019 [-0.042, +0.003]).

**Pooled is not confirmed.** Every estimator that removes between-stint variation lands at 0.30-0.43.
Pooled 0.503 sits above all of them and outside the F2 interval. Two between-stint confounds push
it up: slower cars follow more (the constructor term alone is worth 0.14), and, within a stint,
later laps are both more often following and slower than the tyre model accounts for (age bins take
stint-FE 0.433 to 0.331). The label only ever sees theta through within-stint differences
(`next_5_lap_cumulative_jump_s` is a lead-difference of the residual inside a stint), so a
between-stint confound in theta has no business there. The age-bin part matters most: without the
bins, theta absorbs real residual degradation, and the label is built to predict exactly that. The
F2 estimate is also insensitive to the tyre model (0.312 without the tyre term vs 0.331 with it),
where pooled swings 0.169 -> 0.503.

**Recommendation (a ruling, not taken here):** move `theta_air_label_value` to the pre-registered F2
estimate, **0.331**, as a second label bump. Keeping pooled would need a written reason that survives
the table above. This item did not change the label. That is a label version bump (rebuild dev, T9's
declared value, `label_stability_baseline.csv` re-taken, the verify checks), and W40 names it as the
ruled outcome of this item. One implementation note: the model's SQL fits COVAR/VAR, and a two-way FE
fit does not fit in one SQL aggregate. Either fit F2 outside dbt and freeze the value as the declared
var (T9 already compares fitted to declared, so T9 would need to compare against that fit), or
approximate it in SQL with within-stint demeaning plus age-bin dummies (FWL).

**Ruled and implemented (W40, 2026-09-27): 0.331, by the first route.** F2 is fitted outside dbt
(`d2`, section W) and frozen as `theta_air_label_value: 0.331`. `int_dirty_air_tax_component`
applies the var directly, T9 compares the applied value with it (1e-9), and `d2` stops unless the
var equals this F2 fit to 3 dp. Everything the bump needs was done: dev rebuilt, the seed re-taken,
`dbt test` and the verify checks re-run. The results are in WI-01's "theta re-ruled after
verification" section. The frozen value can go stale if the panel moves without a re-fit
(watch W47).

**Also found:** the comment in `int_dirty_air_tax_component.sql` (panel_base, ~lines 196-200) gives
the tyre-cost mechanism backwards. It says "a car deep in a stint on worn tyres is more often the one
following", but treated laps carry 0.33 s *less* modelled tyre cost, which is why a fuel-only
partial residual biased pooled theta *down* (0.169). The fix is right; the stated reason is not.
~~Not edited: it is WI-01's file, under the orchestrator's verification.~~ Corrected in the W40
edit.

### Step 4: what was rewritten

- **App page (`dirty-air-cost`)**: `methodology.tsx`, `page.tsx`'s "How It's Calculated" badge and
  `docs/app/dirty-air-cost.mdx` no longer say "per-circuit OLS coefficient". They now say "one
  coefficient shared by every circuit and every season" and give the actual treatment (the previous
  lap's middle-third median gap under 1.5 s, one bit, flat per-lap charge). They drop "DRS opens carry
  no tax" (false since WI-15a) and "leader laps are excluded" (281 of 8,084 laps after a P1 lap are
  taxed; the car ahead can be a backmarker). They add that one pooled coefficient is applied to every
  season. No theta value is quoted: the app's exported data still carries 0.152 (pre-WI-15a, W28),
  and the model's has since moved to 0.331 (W40). Every exclusion stated was checked on both the current table and the
  app export (0 pit laps, 0 neutralised laps, 0 first-lap-of-stint charges, 0 charges on the lap
  after a neutralised lap). eslint clean, the feature's 4 tests pass, `app_docs_audit.py` OK.
- **The post** (`implementations/06b/06b_dirty_air_per_season.md`) is rewritten on these numbers.
  Status unchanged: written, not published.
- **`work/06-publication.md` 06b** keeps its original record, with superseding notes on the measured
  claim, the placebo ruling and the 08q app-suppression item.

### Open, for the orchestrator

1. ~~**W40 ruling** (above): F2 0.331 or pooled 0.503 for the label.~~ **Ruled 0.331 and
   implemented, 2026-09-27** (see the W40 section).
2. **08q's pending app ruling is now baseless.** The improvements board records "disable the
   dirty-air-cost leaderboard for 2021 and 2024, where theta's CI crosses zero" as pending
   implementation, and as the one thing standing between 06b's post and publication. On the
   corrected label no season's interval crosses zero on any rung. Recommend retiring that ruling, not
   implementing it.
3. **WI-01 is MEASURED, not LANDED.** If its orchestrator re-run changes the calibration panel,
   re-run `d1` and `d2` (Gate 1 will say so).
4. The placebo result means even F2 prices some persistent-traffic association as dirty air. The
   directional part pooled is about 0.11 s/lap. Recorded, not acted on: the pre-registered design
   has no better instrument, and 06b's "what would change this" list (per-corner exposure, a
   dose-response in the gap) is still the way to get one.
