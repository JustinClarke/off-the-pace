# UNC-01 — Uncertainty methodology for constructor pace, field base and ghost/rating intervals

**Group:** 6-launch (closest fit for work after launch; the board has no "post-launch" group) · **Depends on:** AX-20 (and AX-24, see Order) · **Model / cost:** `opus-5`; design 0.5d (this doc), implementation about 5d · **Stage:** SPEC

Design only. Nothing in `transform/`, `data/` or `app/public/data/` was touched. Runtimes below are estimates, not measurements.

## 1. The problem, with evidence

The intervals fans see on constructor pace, ghost cars and ratings are narrower than the data support, because each stage reports its own sampling noise as if the stage before it were exact and every lap were independent.

1. **Constructor pace SE assumes independent laps.** `int_constructor_structural_pace.sql:127-136` takes the per-(race, constructor) median of `lap_time_s - field_pace_smoothed_s`; `:171-185` sets the SE to `STDDEV_POP / SQRT(n_obs)` and the CI to 1.96 x that. Laps within a stint share tyre age, fuel, traffic and a driver, so n laps is not n independent draws. The effective n is closer to the number of stints (about 4 to 10 per team per race). Also: the SE is a mean-style SE (`sd/sqrt(n)`) attached to a median, `STDDEV_POP` is used where the sample SD is correct, and `COALESCE(..., 0.0)` at `:175` turns a missing SE into 0.
2. **Driver mix is not in the SE.** The pooled median mixes two drivers (`n_drivers` is carried, `:131`, but unused). A driver gap is skill, not car; the coefficient's own comment (`:140-142`) admits it "conflates driver skill with car pace".
3. **The field base has no uncertainty.** `int_field_pace_curve.sql:252-263` is a 10% trimmed mean of the cars on each lap, then a 5-lap centred smooth (header, `:3`). No SE is produced, and `pace_delta_s = lap_time_s - field_pace_smoothed_s` (`int_constructor_structural_pace.sql:114`) subtracts it as exact.
4. **The re-centring has no uncertainty.** `race_mean` (`:147-155`) is the plain `AVG` of the constructor medians; the zero-sum coefficient `c_i - mean(c)` has variance `(1-1/K)^2 s_i^2 + sum_{j!=i} s_j^2 / K^2` (independent constructors), not `s_i^2`, and two teams' re-centred values are negatively correlated.
5. **Track evolution is a point estimate.** `int_track_evolution.sql:77-97` is one OLS slope per race, clipped with `LEAST(..., 0.0)`, and a second OLS on track temperature (`:133-165`); no SE, and the clip biases it. The residual then enters lap residuals as exact (and as 0 where NULL, `int_lap_residual_decomposed.sql:254-255`, handled by TX-30 step e).
6. **Downstream stages add these as if exact.** `fct_ghost_car_pace.sql:138-146` passes `constructor_structural_pace_se_s` through as `host_constructor_pace_se_s`; `fct_ghost_race_finish.sql:195,244-246` squares and adds `host_pace_se` with the cliff and lap-spread terms (a delta-method sum with no covariance between host and ego, and no base term); ratings carry `era_adjusted_rating_ci_*` (`mart_driver_season_summary.sql:85,107`), whose rank-separation flag (`:183`) is only as honest as the SE under it. The real car estimate, `fit_constructor_car_fe.py` (driver + constructor-by-race fixed effects, `_fit_cell_fe`, `:428`), returns point estimates only; no vcov is read.

Net effect: a narrow, confident interval on a 1-to-3-stint sample, with the field-base and centring terms missing. The error is in the direction of overclaiming.

## 2. The options

### A. Analytic: stint-clustered SE plus delta-method sum
Replace the SE with a cluster-robust SE (cluster = driver-stint) and add the base and centring variances by the delta method; carry covariances so ghost host-minus-ego uses the right variance.
- **Fixes:** non-independence (partly), centring variance, base variance if given a base SE. **Does not fix:** driver mix (a stint cluster inside a driver does not measure the between-driver car/skill confound), median-versus-mean SE mismatch, the clip bias in rubber, smoothing correlation across lap cells.
- **Numbers changed:** SE and CI only; point estimates unchanged.
- **Runtime:** seconds, pure SQL.
- **Ghost gate risk:** low (point columns byte-identical). With only 4 to 10 clusters per cell the cluster SE is itself unreliable; a driver-level cluster has 2 clusters (df about 1), so that variant is unusable.

### B. Block bootstrap through the whole pipeline (recommended)
Per race, resample whole stints (the unit that is exchangeable), within driver (drivers held fixed, since driver skill is what the car estimate must separate, not a random draw), and for each replicate recompute: field base (trimmed mean, 5-lap smooth, the W43/W44 boundary rules), track-evolution lines, every constructor median, the race-mean centring, and, in the same replicate, the car fixed effects on the race-level panel. Store a per-cell SE and 2.5/97.5 quantiles (and, for the ghost and rating marts, 200 thinned draws per cell so ghost and rating sums use the joint distribution, which carries the negative covariance and the shared base error for free).
- **Fixes:** all six points in section 1 except the driver-mix bias (below); correlation from smoothing, trimming, the median and the clip are propagated, not approximated.
- **Numbers changed:** none in point estimates (the replicas must reproduce them, see Acceptance); SE and CI columns get new bootstrap values, which will be wider.
- **Runtime:** estimate 150 to 190 races x 500 replicates x a few thousand laps in vectorised pandas or numpy: minutes to tens of minutes on one thread, plus a one-off Python port of the SQL base and pace logic that must match the SQL exactly. The car-FE bootstrap (pyfixest per replicate on race-level aggregates, per era) is the slow part; estimate under an hour, to be measured. Output is a fit file (parquet) read by dbt as a source, like the other fits, so dbt build time is unchanged.
- **Ghost gate risk:** low for point values (added columns; existing point columns stay byte-identical, existing SE columns kept beside the new `_boot_*` ones until the owner has reviewed). The model-hash baseline (`transform/tests/model_hashes.baseline.json`) changes for any mart that gains columns; that is one declared diff. The risk is the Python replica drifting from the SQL, which is why the replica has a bit-level parity gate.

### C. Hierarchical model: constructor-by-race random effect shrunk to the team-season mean
Fit `y ~ driver + (constructor x race)` with the constructor-by-race effect drawn from `N(team-season mean, tau^2)`; the posterior gives shrunk point estimates and intervals.
- **Fixes:** small-sample cells (the 1,122 no-pace and thin cells get a principled value and an honest wide interval, which also answers HD20); pools information across races.
- **Numbers changed:** point estimates move (shrinkage), every ghost and rating number moves; breaks the byte-identical ghost gate and invalidates the TX-15 diff baseline.
- **Runtime:** a mixed model on about 1.4M laps or on race-level aggregates: tens of minutes per fit, with convergence work.
- **Ghost gate risk:** high. This is a change of estimator, not of uncertainty; it needs its own ruling and its own review, and it should follow B, not replace it.

## 3. Recommendation

**Option B.** Reason: it is the only option that propagates the field base, the median, the smoothing and the zero-sum centring into one interval, with the correct dependence, and it leaves every reviewed point estimate (and so the TX-15 diff and the ghost point columns) untouched; A needs more clusters than a team-race has, and C changes the numbers the owner has already reviewed. C stays a later, separately ruled option; A is the fallback if the replica port proves too costly (in that case ship delta-method with a base SE from the bootstrap on a 20-race sample).

Known limit, which stays in the page wording: the bootstrap holds drivers fixed, so it covers sampling noise, not the confound between a team's car and its drivers' skill. The interval is the interval of the estimate given the model, and the method note must say so. The car-FE SE is the honest answer to the driver-mix question for the ghost leaderboard; the SQL median path remains a descriptive pace figure.

Cells with a flagged prior (HD20) get an SE equal to the cross-team spread of constructor pace in that race (never 0, never the prior's own spread); cells HD20 rules missing get NULL.

## 4. Acceptance test

1. **Replica parity (gate 0):** the Python replica reproduces the SQL point estimates (field base, rubber slope, constructor median, centring) to 1e-9 on the scratch build for every race; the car-FE replica reproduces `car_fe_raw_s` to the fit's solver tolerance (1e-12 per `fit_constructor_car_fe.py:440-442`).
2. **Simulation with known effects (the coverage gate):** take the real lap structure (drivers, stints, lap numbers, compounds) of at least 100 races from 2018-2024; inject known constructor-by-race effects, driver effects, stint-level shocks and a known track trend; regenerate lap times; run the full pipeline and the bootstrap. Pass: the 95% interval covers the true constructor effect in 93 to 97% of cells, overall and in each stratum (n_obs bands, number of stints, K constructors), and the current `sd/sqrt(n)` interval is reported beside it to show how far it undercovers. Same test for the ghost host-minus-ego difference and for a rating.
3. **Real data:** no coverage claim from 2025 until ML-01 has scored it once. The TX-29 doc records that 2025 was already used as a selection fold (`ml/src/card.py` HOLDOUT_NOTE), so it is not a clean holdout for tuning; after ML-01, report the finish-position and ghost-lap interval coverage on 2025 once, on a fold not used for selection, and do not tune on it. 2026 is not used (HD21).
4. **Diff review:** point columns byte-identical to the TX-30 baseline; every changed SE/CI column listed with before and after; one owner review.

## 5. Order

- After AX-20 (launch): this is post-launch work, per the owner's ordering (transform close, then AI work, then dirty air, ML retrain and UNC-01).
- After TX-30: the sweep fixes the zero-fills and sets the baseline the byte-identical gate compares against; UNC-01 must not mix into that diff.
- After HD20 is ruled and TX-18 lands: it fixes which cells are priors (SE rule above) and which are NULL.
- After AX-24 (car-ahead rebuild or removal): the field base filters on `int_lap_air_state` (`free_air`, `tow_zone`), which reads the held car-ahead field, so the base, and so the bootstrap, moves when that moves. UNC-01 therefore also waits on AX-24 (already after AX-20).
- After TX-29 (holdout 2025) so no fit or bootstrap reads 2025 or 2026; and use the same fit-window guard.
- Independent of ML-01 except for step 3 of the acceptance test (the one-time 2025 coverage); ML-01 may run first or in parallel.
