# 08i Measurements — the `min_observations` floor, full tables

Generated from `ml/artefacts/08i_min_observations_floor_arms.json` (2026-09-18).
Delta sign convention: **positive = improvement** on every metric.

### step 1a — published v12 headline reproduction

| family | published v12 | floor-2 arm | abs diff |
| :--- | ---: | ---: | ---: |
| `degradation_regressor_p10` | 0.4764640778 | 0.4764640778 | 0.00e+00 |
| `degradation_regressor_p50` | 0.9823587336 | 0.9823587336 | 0.00e+00 |
| `degradation_regressor_p90` | 0.5128462338 | 0.5128462338 | 0.00e+00 |
| `cliff_classifier` | 0.3524660979 | 0.3524660979 | 0.00e+00 |
| `stint_life_regressor` | 1.9913358779 | 1.9913358779 | 0.00e+00 |

### coverage on the training-eligible panel

| floor | coverage | thermal-NaN rows | pp vs floor 1 | pp vs floor 2 |
| ---: | ---: | ---: | ---: | ---: |
| 1 | 98.20% | 2,156 / 119,822 | +0.00 | +2.15 |
| 2 | 96.05% | 4,727 / 119,822 | -2.15 | +0.00 |
| 3 | 90.70% | 11,141 / 119,822 | -7.50 | -5.35 |
| 5 | 80.35% | 23,549 / 119,822 | -17.85 | -15.71 |

### headline per floor (bold = best in family)

| family | metric | floor 1 | floor 2 | floor 3 | floor 5 |
| :--- | :--- | ---: | ---: | ---: | ---: |
| `p10` | pinball | **0.4753878** | 0.4764641 | 0.4873281 | 0.5008968 |
| `p50` | pinball | **0.9684060** | 0.9823587 | 0.9821650 | 0.9874394 |
| `p90` | pinball | **0.5072930** | 0.5128462 | 0.5249556 | 0.5274265 |
| `cliff F1` | macro_f1 | 0.3509052 | **0.3524661** | 0.3474381 | 0.3454120 |
| `life nll` | aft_nloglik | 1.9926008 | 1.9913359 | **1.9880619** | 1.9909305 |

### gate steps 2-4: every floor against the built substrate (floor 2)

| family | floor | delta vs floor 2 | own floor (2sqrt2 sd) | x floor | missingness-only control | E (cross-floor) | clears |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | :--- |
| `p10` | 1 | +0.0010763 | 0.0066994 | +0.16x | +0.0021707 (+0.32x) | 4.63 (up) | inside |
| `p10` | 3 | -0.0108640 | 0.0051848 | -2.10x | +0.0012840 (+0.25x) | 29.5 (DOWN) | inside |
| `p10` | 5 | -0.0244327 | 0.0106539 | -2.29x | +0.0018590 (+0.17x) | 28.5 (DOWN) | inside |
| `p50` | 1 | +0.0139527 | 0.0111509 | +1.25x | +0.0021132 (+0.19x) | 13.5 (up) | CLEARS |
| `p50` | 3 | +0.0001937 | 0.0111509 | +0.02x | -0.0016318 (-0.15x) | 0.495 (DOWN) | inside |
| `p50` | 5 | -0.0050807 | 0.0111509 | -0.46x | +0.0034435 (+0.31x) | 4.64 (DOWN) | inside |
| `p90` | 1 | +0.0055532 | 0.0146013 | +0.38x | +0.0020495 (+0.14x) | 0.413 (DOWN) | inside |
| `p90` | 3 | -0.0121094 | 0.0083954 | -1.44x | +0.0021644 (+0.26x) | 21.4 (DOWN) | inside |
| `p90` | 5 | -0.0145802 | 0.0092795 | -1.57x | -0.0008123 (-0.09x) | 30.8 (DOWN) | inside |
| `cliff F1` | 1 | -0.0015609 | 0.0043397 | -0.36x | -0.0003929 (-0.09x) | 0.527 (DOWN) | inside |
| `cliff F1` | 3 | -0.0050280 | 0.0045279 | -1.11x | -0.0005838 (-0.13x) | 3.23 (DOWN) | inside |
| `cliff F1` | 5 | -0.0070541 | 0.0070406 | -1.00x | -0.0021774 (-0.31x) | 6 (DOWN) | inside |
| `life nll` | 1 | -0.0012650 | 0.0068296 | -0.19x | +0.0011063 (+0.16x) | 0.43 (DOWN) | inside |
| `life nll` | 3 | +0.0032740 | 0.0061134 | +0.54x | +0.0023664 (+0.39x) | 1.02 (up) | inside |
| `life nll` | 5 | +0.0004054 | 0.0090994 | +0.04x | -0.0013209 (-0.15x) | 0.502 (up) | inside |

### gate step 4: information the thermal block carries AT each floor

| family | floor | real | shuffled | information | x own floor | E(info) | eval rows | thermal-NaN eval |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `p10` | 1 | 0.4753878 | 0.5438663 | +0.0684786 | +10.22x | 35.5 | 13,712 | 146 (1.06%) |
| `p10` | 2 | 0.4764641 | 0.5460370 | +0.0695730 | +50.86x | 35.9 | 13,712 | 424 (3.09%) |
| `p10` | 3 | 0.4873281 | 0.5447531 | +0.0574250 | +11.08x | 35.8 | 13,712 | 1,324 (9.66%) |
| `p10` | 5 | 0.5008968 | 0.5441781 | +0.0432813 | +4.06x | 31.8 | 13,712 | 2,979 (21.73%) |
| `p50` | 1 | 0.9684060 | 1.0507024 | +0.0822964 | +10.56x | 35.6 | 13,712 | 146 (1.06%) |
| `p50` | 2 | 0.9823587 | 1.0528156 | +0.0704569 | +6.32x | 35.5 | 13,712 | 424 (3.09%) |
| `p50` | 3 | 0.9821650 | 1.0544474 | +0.0722824 | +7.72x | 35 | 13,712 | 1,324 (9.66%) |
| `p50` | 5 | 0.9874394 | 1.0493721 | +0.0619327 | +25.90x | 35.5 | 13,712 | 2,979 (21.73%) |
| `p90` | 1 | 0.5072930 | 0.5456995 | +0.0384065 | +2.63x | 29.3 | 13,712 | 146 (1.06%) |
| `p90` | 2 | 0.5128462 | 0.5477490 | +0.0349027 | +4.16x | 31.2 | 13,712 | 424 (3.09%) |
| `p90` | 3 | 0.5249556 | 0.5455846 | +0.0206290 | +2.64x | 29.1 | 13,712 | 1,324 (9.66%) |
| `p90` | 5 | 0.5274265 | 0.5485613 | +0.0211348 | +2.28x | 27.6 | 13,712 | 2,979 (21.73%) |
| `cliff F1` | 1 | 0.3509052 | 0.3372840 | +0.0136212 | +3.82x | 31.1 | 18,866 | 188 (1.00%) |
| `cliff F1` | 2 | 0.3524661 | 0.3376769 | +0.0147892 | +3.41x | 30 | 18,866 | 529 (2.80%) |
| `cliff F1` | 3 | 0.3474381 | 0.3370931 | +0.0103450 | +2.28x | 31.5 | 18,866 | 1,599 (8.48%) |
| `cliff F1` | 5 | 0.3454120 | 0.3354996 | +0.0099124 | +1.41x | 18.5 | 18,866 | 3,676 (19.48%) |
| `life nll` | 1 | 1.9926008 | 2.0146659 | +0.0220650 | +3.23x | 33.2 | 19,973 | 193 (0.97%) |
| `life nll` | 2 | 1.9913359 | 2.0157722 | +0.0244363 | +4.00x | 33.4 | 19,973 | 540 (2.70%) |
| `life nll` | 3 | 1.9880619 | 2.0134058 | +0.0253439 | +6.83x | 34.6 | 19,973 | 1,621 (8.12%) |
| `life nll` | 5 | 1.9909305 | 2.0170931 | +0.0261626 | +2.88x | 32.1 | 19,973 | 3,743 (18.74%) |

### verdict scan

p10       best=1  clears_vs_2=none  significantly_worse_than_2=['3', '5']  n_eval=13712
p50       best=1  clears_vs_2=['1']  significantly_worse_than_2=none  n_eval=13712
p90       best=1  clears_vs_2=none  significantly_worse_than_2=['3', '5']  n_eval=13712
cliff F1  best=2  clears_vs_2=none  significantly_worse_than_2=['3', '5']  n_eval=18866
life nll  best=3  clears_vs_2=none  significantly_worse_than_2=none  n_eval=19973

n_eval identical across floors by construction (floor changes NaN, not rows).

---

## Landing verification — 2026-09-22, on the built `v13` substrate

Read-only. Nothing written to `ml/models/`, `ml/artefacts/`, the warehouse or git. The floors
2/3/5 rows below are counterfactuals computed with this item's own floor-parameterised replica
against the current warehouse; floor 1 is what is actually built.

### step 1b, re-pointed at floor 1 — replica vs the BUILT warehouse

| column | exact | mismatch | NULLs built | NULLs replica |
| :--- | ---: | ---: | ---: | ---: |
| `push_residual` | 137,447 / 137,447 | 0 | 7,094 | 7,094 |
| `cumulative_push_load_surface` | 137,447 / 137,447 | 0 | 7,094 | 7,094 |
| `cumulative_push_load_bulk` | 137,447 / 137,447 | 0 | 7,094 | 7,094 |
| `surface_bulk_ratio` | 137,447 / 137,447 | 0 | 20,263 | 20,263 |

BIT-FOR-BIT at floor 1: **True**. (At the gate run, the built substrate was floor 2 and carried
14,017 / 14,017 / 14,017 / 27,287.)

### step 1a — the published `v13` headline, refit from the current warehouse

Canonical seed, through `evaluate.py`'s own `_fit`/`_score`. The floor-1 replica is identical to
the live split's thermal block on all four columns, train and eval, in every family.

| family | published v13 | refit here | abs diff | width | thermal-NaN, eval |
| :--- | ---: | ---: | ---: | ---: | ---: |
| `degradation_regressor_p10` | 0.4557991687 | 0.4557991687 | 0.00e+00 | 32 | 146 |
| `degradation_regressor_p50` | 0.9309607723 | 0.9309607723 | 0.00e+00 | 32 | 146 |
| `degradation_regressor_p90` | 0.5070426104 | 0.5070426104 | 0.00e+00 | 32 | 146 |
| `cliff_classifier` | 0.3847835663 | 0.3847835663 | 0.00e+00 | **39** | 188 |
| `stint_life_regressor` | 2.1566148091 | 2.1566148091 | 0.00e+00 | 32 | 193 |

The classifier is 39 wide because `02b`'s seven qualifying columns rode the same bump (`D12`).

### coverage and the hardest cliff class, realised against predicted

The panel moved with the bundle — `08q` re-estimated `theta_air`, which moves `dirty_air_tax_s`
into `driver_skill_residual_s` and so into both the degradation target and
`laps_until_cliff_class`. Reported side by side, not diffed.

| quantity | predicted (v12 panel, 2026-09-18) | realised (v13 panel, 2026-09-22) |
| :--- | ---: | ---: |
| eligible rows | 119,822 | 119,775 |
| coverage, floor 1 (built) | 98.20% (2,156 NaN) | **98.20%** (2,152 NaN) |
| coverage, floor 2 | 96.05% (4,727) | 96.07% (4,708) |
| coverage, floor 3 | 90.70% (11,141) | 90.68% (11,163) |
| coverage, floor 5 | 80.35% (23,549) | 80.31% (23,582) |
| coverage bought vs floor 2 | +2.15pp | **+2.13pp** |
| `0_to_2` share of eligible | 10.05% | 9.52% |
| blind rate within `0_to_2`, floor 1 | 10.48% | 11.13% |
| blind rate within `0_to_2`, floor 2 | 12.13% | 12.61% |
| blind rate within `0_to_2`, floor 3 | 17.44% | 17.47% |
| blind rate within `0_to_2`, floor 5 | 26.13% | 25.65% |

The coverage gain reproduces to 0.02pp, and floors 3 and 5 cost the same coverage they were
rejected for (their *signal* cost was not re-measured here — the gate table above is arm-vs-arm on
a fixed target and is not re-run by a landing check). The `0_to_2` blind-rate levels moved about
half a point with the class definition; the gain the ruling rested on (−1.65pp predicted) is
**−1.48pp** realised.

### invariant on the intermediate model

`stint_baseline_pace IS NULL` matches `baseline_observations_n < 1` on **0** violating rows across
all 162,729 `int_lap_thermal_proxy` rows, and the minimum `baseline_observations_n` on a non-NULL
baseline is exactly **1** — it would be 2 under the old floor.
