# 08f-2 Measurements — Isolation of the circuit×constructor rebuild

All numbers from `scripts/measure_08f2_label_impact.py`, run 2026-09-17 against two isolated
`gate_before` warehouse builds (39-model ancestor lineage of `fct_cliff_prediction_features`,
`dbt run --select +fct_cliff_prediction_features --target gate_before`). AFTER = as-shipped
(current `int_circuit_x_constructor_interaction.sql`, commit `bbe3e48` content). BEFORE = the
same lineage with **only** that one file reverted to its pre-08f-2 content (commit `e5bcd35`,
verified as the correct immediate predecessor — see README for why `08g`'s `c7c8509` is wrong for
this isolation). Everything else — `08e`'s thermal fix, `08m`/`08l` severity-units rebuild, all
other lineage — identical on both builds. Row-matched on `lap_id` (mart / residual grain) or
`(race_year, race_id, constructor_id)` (interaction model grain) or `stint_id` (detrend grain).

## Row counts (grain unchanged)

| table | AFTER rows | BEFORE rows |
|:---|---:|---:|
| `int_circuit_x_constructor_interaction` | 1,456 | 1,456 |
| `int_lap_residual_decomposed` | 137,447 | 137,447 |
| `int_lap_residual_stint_detrend` | 7,064 | 7,064 |
| `fct_cliff_prediction_features` | 137,447 | 137,447 |

Both builds' row counts match `08g`'s previously recorded shape (137,447 / 1,456) exactly.

## Instrument check — columns outside the 08f-2 lineage

| column | lineage | max |Δ| (AFTER vs BEFORE) | max |Δ| (either scratch build vs `dev.duckdb`) |
|:---|:---|---:|---:|
| `push_residual` | family T / `int_lap_thermal_proxy` (sibling, unrelated) | 0.0 | 0.0 |
| `fuel_mass_kg` | fuel-state lineage (unrelated) | 0.0 | 0.0 |
| `expected_compound_pace_s` | compound-cliff lineage (unrelated) | 0.0 | 0.0 |

137,447/137,447 rows matched on all three, against production `data/dev.duckdb` (read-only,
never opened for write during this probe) and between the two scratch builds. Nothing outside the
intended lineage moved.

## Mechanism check — is the residual shift a per-group constant?

Grouped the per-lap `driver_skill_residual_s` diff (AFTER − BEFORE) by `(race_year, race_id,
constructor_id)` — the grain of `circuit_constructor_interaction_s` — and took the standard
deviation within each of the 1,456 groups.

| | value |
|:---|---:|
| max within-group stddev, over all 1,456 groups | 6.694609e-16 |
| mean within-group stddev | 1.646103e-16 |

Both are float-noise scale (machine epsilon for `double` is ~2.2e-16). The shift is an exact
constant per group, not approximately constant.

## 1. `circuit_constructor_interaction_s` (race × constructor grain, n=1,456)

| race_year | n | n_changed | mean |Δ| | median |Δ| | max |Δ| | mean AFTER | mean BEFORE |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 2018 | 197 | 197 | 0.101091 | 0.095616 | 0.364070 | 0.000000 | 0.002157 |
| 2019 | 207 | 207 | 0.098296 | 0.082094 | 0.514021 | 0.005740 | −0.000265 |
| 2020 | 169 | 169 | 0.088317 | 0.069679 | 0.372175 | 0.005010 | 0.000836 |
| 2021 | 209 | 209 | 0.085974 | 0.068417 | 0.310570 | 0.002694 | 0.000221 |
| 2022 | 217 | 217 | 0.092822 | 0.079145 | 0.352175 | −0.003278 | −0.000986 |
| 2023 | 219 | 219 | 0.076738 | 0.057124 | 0.353226 | −0.001360 | 0.000729 |
| 2024 | 238 | 238 | 0.063466 | 0.045068 | 0.304360 | −0.004479 | −0.000921 |
| **overall** | **1,456** | **1,456 (100%)** | **0.085995** | **0.068372** | **0.514021** | — | — |

2018's mean AFTER value is exactly 0.0 (confirms the known zero-pool defect: no prior season to
build an expanding window from). Its mean BEFORE value, 0.002157, is small but non-zero — the old
pooled estimate leaned on 2019-2024 data, most of which happened to sit close to zero for these
cells.

## 2. `driver_skill_residual_s` (lap grain, n=137,447) — barred input, propagates 1:1 from (1)

| race_year | n | n_changed | pct_changed | mean |Δ| | median |Δ| | max |Δ| |
|---:|---:|---:|---:|---:|---:|---:|
| 2018 | 17,380 | 17,324 | 99.68% | 0.104545 | 0.097381 | 0.364070 |
| 2019 | 20,723 | 20,608 | 99.45% | 0.095594 | 0.077924 | 0.514021 |
| 2020 | 15,225 | 15,225 | 100.00% | 0.088349 | 0.069679 | 0.372175 |
| 2021 | 20,560 | 20,559 | 100.00% | 0.081783 | 0.065439 | 0.310570 |
| 2022 | 19,395 | 19,318 | 99.60% | 0.090292 | 0.076759 | 0.352175 |
| 2023 | 20,908 | 20,908 | 100.00% | 0.075168 | 0.056749 | 0.353226 |
| 2024 | 23,256 | 23,236 | 99.91% | 0.061648 | 0.044133 | 0.304360 |
| **overall** | **137,447** | **137,178 (99.80%)** | — | **0.084258** | **0.067544** | **0.514021** |

2018 vs rest:

| group | n | n_changed | mean |Δ| | median |Δ| | max |Δ| |
|:---|---:|---:|---:|---:|---:|
| 2018 | 17,380 | 17,324 | 0.104545 | 0.097381 | 0.364070 |
| 2019–2024 | 120,067 | 119,854 | 0.081322 | 0.064358 | 0.514021 |

Distribution of |Δ|, overall:

| p50 | p90 | p99 | p100 (max) |
|---:|---:|---:|---:|
| 0.067544 | 0.180772 | 0.306079 | 0.514021 |

The rows that show *zero* diff are exactly the (race_year, race_id, constructor_id) cells that
were already 0.0 on both sides (mostly 2018's own first-visit cells) — not a separate population.

## 3. `drift_s_per_lap` (stint grain, n=7,064) — feeds the detrended targets

| n | n_changed | mean |Δ| | median |Δ| | max |Δ| |
|---:|---:|---:|---:|---:|
| 7,064 | **0** | 3.112912e-17 | 6.938894e-18 | 1.776357e-15 |

Float noise only. 0 stints move beyond it.

## 4. `next_5_lap_cumulative_jump_s` == `DEGRADATION_TARGET` (lap grain)

| population | n | n_changed | mean |Δ| | median |Δ| | max |Δ| | mean AFTER | mean BEFORE |
|:---|---:|---:|---:|---:|---:|---:|---:|
| both non-null | 95,346 | 0 | 1.260468e-15 | 8.881784e-16 | 2.486900e-14 | −0.394565 | −0.394565 |
| training-eligible both sides | 81,619 | 0 | 1.273132e-15 | 8.881784e-16 | 2.486900e-14 | −0.460681 | −0.460681 |

By season, training-eligible both sides:

| race_year | n | n_changed | mean |Δ| | median |Δ| | max |Δ| |
|---:|---:|---:|---:|---:|---:|---:|
| 2018 | 10,769 | 0 | 1.618e-15 | 8.882e-16 | 1.510e-14 |
| 2019 | 12,491 | 0 | 1.171e-15 | 8.882e-16 | 2.487e-14 |
| 2020 | 9,108 | 0 | 1.129e-15 | 8.882e-16 | 1.121e-14 |
| 2021 | 13,149 | 0 | 1.298e-15 | 8.882e-16 | 1.554e-14 |
| 2022 | 10,194 | 0 | 1.194e-15 | 8.882e-16 | 1.510e-14 |
| 2023 | 12,196 | 0 | 1.306e-15 | 8.882e-16 | 1.787e-14 |
| 2024 | 13,712 | 0 | 1.197e-15 | 8.882e-16 | 1.155e-14 |

81,619 training-eligible rows matches the currently-published v12/08m substrate figure exactly
(`_improvements/work/08-foundations-repair.md`'s 08m note: "is_training_eligible ... 82,470 →
81,619"), confirming this probe ran on the current, correct substrate.

`next_3_lap_cumulative_jump_s` (n=110,944, both non-null): 0 changed, max |Δ| = 1.776357e-14.

Legacy single-lap targets (`next_lap_degradation_jump_s`, `next_lap_degradation_jump_detrended_s`,
n=130,353 both non-null): 0 changed on either, max |Δ| = 3.552714e-15.

## 5. `laps_until_cliff_class` == `CLIFF_TARGET` (categorical, lap grain)

Confusion matrix (AFTER class vs BEFORE class), all rows land on the diagonal:

| after_class | before_class | n |
|:---|:---|---:|
| none_in_stint | none_in_stint | 82,965 |
| 6_plus | 6_plus | 20,145 |
| 0_to_2 | 0_to_2 | 15,198 |
| 3_to_5 | 3_to_5 | 12,045 |
| NULL | NULL | 7,094 |

Total rows: 137,447. Class changed: **0 (0.00%)**. Restricted to training-eligible both sides
(119,822 rows): class changed **0 (0.00%)**.

## 6. `is_training_eligible` / `anomaly_class` population check

Secondary check — NOT a re-test of whether `cliff_candidate_flag` carries information (settled
dead, `08g`/`08j`; stays closed).

| after eligible n | before eligible n | eligibility flipped n | anomaly_class changed n |
|---:|---:|---:|---:|
| 119,822 | 119,822 | 0 | 0 |

Mechanistically consistent with §2's finding: `int_lap_anomaly_flags.sql`'s trailing-MAD window
(`trailing_window`, `trailing_mad` CTEs) is partitioned by `(race_year, race_id, driver_id)`,
which nests inside the same constant-shift group as `circuit_constructor_interaction_s`
`(race_year, race_id, constructor_id)` — a driver belongs to exactly one constructor per race — so
the constant cancels there too, exactly.

## 7. `remaining_stint_life_laps`

Not rebuilt or measured numerically — traced by SQL and confirmed out of scope. Its source model
`int_stint_end_regime.sql` refs only `{{ ref('int_stint_geometry') }}` and
`{{ ref('stg_results') }}`; `int_stint_geometry.sql` refs only `{{ ref('stg_laps') }}`. No `ref()`
to `int_circuit_x_constructor_interaction` or `int_lap_residual_decomposed` exists anywhere in
that chain, so no rebuild could show a difference — this is a structural conclusion, not a
measured zero.

## Reproduction

The full manual build procedure (profile edit, seed, two `dbt run`s, the file revert and its
exact commit, cleanup) is documented in `scripts/measure_08f2_label_impact.py`'s module
docstring. The script itself is the read-only analysis half; it takes two directories of parquet
snapshots (see `export()` in the script) rather than rebuilding on invocation, since the scratch
warehouse and profile block are deliberately not left on disk between runs.

---

# 08f-1 Measurements — Isolation of the survival-weight season-lag

All numbers from `scripts/gate_08f1_survival_weight.py`, run 2026-09-17 against two isolated
`gate_before` warehouse builds (`dbt run --select +fct_cliff_prediction_features +fct_stint_features
--target gate_before`, 40+26 models). AFTER = as-shipped (season-lagged, commit `bbe3e48` content).
BEFORE = the same lineage with **only** `total_per_compound`/`stints_reaching`/`stint_survival`
hand-reverted to season-pooled form (commit `c7de693`, verified as the correct immediate
predecessor). Everything else — `08e`'s thermal fix, `08f-2`'s point-in-time interaction, `08m`/`08l`'s
severity-unit rebuild, `baseline_observations_n`, corner-inputs (02c), qualifying (02b) — identical
on both builds. `evaluate.py::_fit`/`_score`/`attribution.refit_noise_floor` used throughout; no
reimplementation of fit, score, split or CV logic.

## Instrument check — row-level diff outside `survival_weight`

All 32 `FEATURE_COLUMNS` and the censoring flag, train and eval, for all five targets:

| target | train X cols differing | eval X cols differing | y_tr max |Δ| | y_ev max |Δ| |
|:---|---:|---:|---:|---:|
| `degradation_regressor_p10` | 0 | 0 | 8.62e-14 | 6.75e-14 |
| `degradation_regressor_p50` | 0 | 0 | 8.62e-14 | 6.75e-14 |
| `degradation_regressor_p90` | 0 | 0 | 8.62e-14 | 6.75e-14 |
| `cliff_classifier` | 0 | 0 | 0.0 | 0.0 |
| `stint_life_regressor` | 0 | 0 | 0.0 | 0.0 |

Zero feature columns differ on either side, for every target — confirms `survival_weight`'s CTEs
share no computation with anything that feeds `X`. The quantile trio's target
(`next_5_lap_cumulative_jump_s`) carries float noise at the same order of magnitude as the known
non-associative-float-under-threading artifact `08e`/`08g` already documented (8.17e-14) — not a
leak in this isolation. `cliff_classifier`'s (`laps_until_cliff_class`) and `stint_life_regressor`'s
(`remaining_stint_life_laps`) targets differ by exactly 0.0, not float noise, because both are built
from integer/categorical arithmetic the threading reorder does not touch.

Row counts (both builds, all targets): `degradation_regressor_*` n_train=67,907 n_eval=13,712;
`cliff_classifier` n_train=94,360 n_eval=18,866; `stint_life_regressor` n_train=99,849 n_eval=19,973.
`mode=cv_final_fold`, `eval_season=2024` throughout (2025 not yet ingested).

## Instrument check — published v12 reproduction (AFTER arm)

| target | AFTER headline | published v12 | match to 10dp |
|:---|---:|---:|:---:|
| `degradation_regressor_p10` | 0.4764640778 | 0.4764640778 | exact |
| `degradation_regressor_p50` | 0.9823587336 | 0.9823587336 | exact |
| `degradation_regressor_p90` | 0.5128462338 | 0.5128462338 | exact |
| `cliff_classifier` | 0.3524660979 | 0.3524660979 | exact |
| `stint_life_regressor` | 1.9913358779 | 1.9913358779 | exact |

All five also match `08e_thermal_family_arms.json`'s independently-computed `A+T` (full 32-column)
cell to the digits shown — a second, independent refit (different session, different isolated
warehouse copy) reproduces the same numbers.

## The weight vector, AFTER vs BEFORE

| | AFTER (season-lagged) | BEFORE (season-pooled) |
|:---|---:|---:|
| mean | 1.970446 | 1.710771 |
| sd | 1.140947 | 0.868060 |
| min | 1.000000 | 1.026596 |
| max | 4.000000 | 4.000000 |

Max per-row |Δ| = 2.973404. Rows with a changed weight: **63,344 / 67,907 (93.3%)**. The clip range
is [0.25, 4.0] (`GREATEST(0.25, LEAST(4.0, ...))`); neither side's minimum reaches the 0.25 floor,
both reach the 4.0 ceiling.

## The gate question: AFTER vs BEFORE, quantile trio

`evaluate.py::_fit` at the canonical seed (`S.RANDOM_STATE`), `evaluate.py::_score` (unweighted at
eval time). Positive delta = AFTER improves on BEFORE. Floor = `2·√2·sd` over 5 reseeds
(`S.RANDOM_STATE + 0..4`), quoted from the larger of the AFTER-arm floor and the BEFORE-arm floor.

| target | AFTER | BEFORE | delta | floor | quoted from | ratio | clears? |
|:---|---:|---:|---:|---:|:---:|---:|:---:|
| p10 | 0.4764640778 | 0.4802231706 | +0.00375909 | 0.00763075 | before (sd 0.0026979 vs after sd 0.0004837) | 0.49× | inside |
| p50 | 0.9823587336 | 0.9840438286 | +0.00168510 | 0.01115092 | after (sd 0.0039424 vs before sd 0.0033120) | 0.15× | inside |
| p90 | 0.5128462338 | 0.5122840197 | −0.00056221 | 0.00839541 | after (sd 0.0029682 vs before sd 0.0022145) | −0.07× | inside |

No target clears, in either direction. `cliff_classifier`/`stint_life_regressor`: delta = 0.0 by
construction (see instrument check above — no code path, no data path).

## Uniform-weight comparison (secondary; not 08f-1's own gate question)

`A` = uniform weights (w=1 for every training row), the zero point the two IPW arms are read
against — not what production ships.

| target | uniform A | AFTER vs A | BEFORE vs A |
|:---|---:|---:|---:|
| p10 | 0.4711254463 | −0.00533863 | −0.00909772 |
| p50 | 0.9817102187 | −0.00064851 | −0.00233361 |
| p90 | 0.5093926910 | −0.00345354 | −0.00289133 |

Both IPW schemes underperform no-reweighting on all three heads at `eval_season` 2024; AFTER is
closer to uniform (smaller loss) than BEFORE on p10/p50, marginally further on p90. Not gated here
— recorded because it fell out of the same arms.

## Permutation null (translated: shuffle the weight VECTOR across training rows)

Capacity = shuffled − uniform A. Information = real − shuffled. Both oriented positive=improvement.

| target | arm | shuffled headline | capacity | capacity ×floor | information | information ×floor |
|:---|:---|---:|---:|---:|---:|---:|
| p10 | AFTER | 0.4665590145 | +0.00456643 | 0.60× | −0.00990506 | **−1.30×** |
| p10 | BEFORE | 0.4721344809 | −0.00100903 | −0.13× | −0.00808869 | **−1.06×** |
| p50 | AFTER | 0.9780458299 | +0.00366439 | 0.33× | −0.00431290 | −0.39× |
| p50 | BEFORE | 0.9871601145 | −0.00544990 | −0.49× | +0.00311629 | 0.28× |
| p90 | AFTER | 0.5184358514 | −0.00904316 | −1.08× | +0.00558962 | 0.67× |
| p90 | BEFORE | 0.5175787628 | −0.00818607 | −0.98× | +0.00529474 | 0.63× |

Only p10's information terms clear (both arms, both negative — the specific row-to-weight alignment
costs pinball relative to the same weight values randomly reassigned, for both weighting schemes
alike). p10 and p90's capacity terms also approach or exceed 1× in places (p10 AFTER capacity 0.60×,
p90 both arms ≈ −1.0×) — reweighting by itself, independent of alignment, measurably moves p10 and
p90.

## e-values (step 7) — information contrast, Construction B, n=5, g=1.0

| target | d_bar | t | E | direction = improvement | max attainable E |
|:---|---:|---:|---:|:---:|---:|
| p10 | −0.004445 | −2.342 | 2.114 | No | 36.0 |
| p50 | −0.003614 | −2.279 | 2.004 | No | 36.0 |
| p90 | +0.002644 | +2.140 | 1.778 | Yes | 36.0 |

MC validity check (100,000 draws per sigma, n=5, g=1.0): mean E = 1.0016 / 0.9992 / 1.0108 / 1.0014
at sigma = 0.001 / 0.01 / 0.1 / 1.0 (±0.010-0.011) — construction valid at this n, identical check
to `08e`'s.

Negative controls (shuffle vs shuffle, H0 true by construction):

| target | d_bar | E |
|:---|---:|---:|
| p10 | −0.000652 | 0.472 |
| p50 | +0.005596 | **8.761** |
| p90 | +0.004995 | 0.928 |

p50's control (8.761) is the largest E anywhere in this gate — recorded, not rounded away, per
`08e`'s own precedent with its 3.282 control on p10. It is a negative control (both arms are
shuffles of the same vector; H0 is true by construction here), so it does not indict any headline
finding, but it is the single largest number in the table.

## Reproduction

Manual dbt steps, the exact hand-revert patch, and the full pre-registered design are documented in
`scripts/gate_08f1_survival_weight.py`'s module docstring. The script has three `--stage`s
(`export-after`, `export-before` — both need the isolated warehouse in the matching state —
`analyze`, pure pandas/numpy from the two snapshots). Snapshots are pickled `EvalSplit` contents,
not committed.
