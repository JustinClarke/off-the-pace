# ML Headroom — Where the Models Are Actually Leaving Value

Third audit in the `_improvements/` series, after `PLAN.md` (SC-hole, bronze pickups)
and `transform_gaps.md` (seven transform defects, all closed). Those two asked *is the
transform layer correct?* This one asks a different question:

> The transform layer is now correct. Are the **models** extracting everything the
> warehouse can give them — and if not, where is the headroom?

Measured against `data/dev.duckdb` (read-only) on **2026-08-22**, at the current
working-tree state (all five `transform_gaps.md` phases implemented, uncommitted).

**Headline: the feature set is saturated. The headroom is in targets and labels, not
columns.** Seventeen unused warehouse signals were tested and add nothing. Two of the
five production models have a defect in what they are being asked to predict.

> **Superseded in part by `ml_headroom_ii.md` (2026-08-23).** That pass closed #1, #2 and
> #5 and corrected two claims here: the balanced-class-weight change recommended in §1
> has shipped since the first ML commit (so the "+12.1% available" is already banked),
> and §2's stated app blast radius does not exist — `predicted_remaining_stint_life_laps`
> is queried but rendered nowhere. The headline above still holds, and gets sharper: #1
> turned out to be a **label-definition** defect, not class imbalance.

> **Superseded as a tracker by `ml_execution_plan.md` (2026-08-23).** That file is the
> plan; this one is frozen as the evidence base for its own measurements. Do not add
> findings here. One further reversal landed after the note above was written: §2's app
> blast radius *does* exist after all — `predicted_remaining_stint_life_laps` is rendered
> by `DegradationSimulatorChart.tsx` through the in-browser ONNX path, which
> `ml_headroom_ii.md` §6 missed. See that section's appended correction.

---

## Measurement harness (read this before trusting a number)

Every experiment below uses one harness: expanding-window season CV (train
2018…*k*−1, test season *k*, six folds), XGBoost at 300 trees / depth 6 / lr 0.08,
`random_state = S.RANDOM_STATE`, the project's own `S.FEATURE_COLUMNS`,
`S.CATEGORICAL_COLUMNS` and `S.BOOLEAN_COLUMNS` encodings, restricted to
`is_training_eligible`.

**It is untuned.** Absolute values do not match `ml/artefacts/evaluation_metrics.json`
(which is tuned, and uses pinball rather than RMSE for the quantile models). Nothing
here should be quoted as a model score. Every claim is a **relative** comparison of two
runs of the same harness differing only in the columns or labels named, and each
experiment is reported against **its own base** — the bases differ slightly between
experiments because different joins retain different rows.

---

## Findings, ranked

| # | Finding | Kind | Measured effect |
| :--- | :--- | :--- | :--- |
| 1 | Cliff classifier has two functionally dead classes | **defect** | `6_plus` F1 = **0.000**, `3_to_5` recall = **0.003** |
| 2 | Stint-life target is 41% right-censored — two questions under one label | **defect** | a leaky flag buys **+24%** RMSE; no legitimate feature buys more than +3.6% |
| 3 | 17 unused warehouse signals add nothing to the degradation model | **closes a thread** | **−0.01%** (and −0.95% on the cliff classifier) |
| 4 | Air density — the ML schema's explicit `DEFERRED` item — is not worth building | **closes a thread** | 37.6% physical spread, **−0.33% / +0.70%** marginal value |
| 5 | `tyre_allocations` seed is loaded, consumed by nothing, and contradicted by its own stub model | **orphan** | 44 rows, 2023–24, absolute C1–C5 codes |
| 6 | `int_sc_hazard_history` is a leaf (already documented as one) | **orphan** | no dbt consumer, no app consumer |

Findings 3 and 4 are negative results. They are ranked as highly as the defects because
each one closes a plausible, expensive-looking thread that would otherwise be the
obvious next thing to build.

---

## 1. The cliff classifier has two functionally dead classes

`laps_until_cliff_class` is a 4-class label. Its class support in the training set:

| Class | n | share |
| :--- | ---: | ---: |
| `none_in_stint` | 96,538 | 79.8% |
| `0_to_2` | 10,117 | 8.4% |
| *(NULL — unlabelled)* | 6,664 | 5.5% |
| `3_to_5` | 5,788 | 4.8% |
| `6_plus` | 1,827 | 1.5% |

Per-class performance on the final CV fold (harness above, macro-F1 0.2851):

```
               precision    recall  f1-score   support
       0_to_2      0.551     0.085     0.147      1342
       3_to_5      0.222     0.003     0.005       776
       6_plus      0.000     0.000     0.000       218
none_in_stint      0.885     0.997     0.937     16808
```

`6_plus` is **never predicted, once, in a whole season**. `3_to_5` is predicted at a
recall of 0.003 — three laps in a thousand. The headline macro-F1 is carried entirely by
`none_in_stint` (0.937) and a weak `0_to_2` (0.147); half the label space is decorative.
The model has learned "a cliff is coming soon or it isn't", and nothing finer.

This is not a feature problem — finding #3 shows adding 16 more signals makes it *worse*.
It is a class-imbalance and label-granularity problem. Three alternatives, same harness:

| Variant | macro-F1 | vs current | Comparable? |
| :--- | ---: | ---: | :--- |
| current 4-class | 0.2851 | — | — |
| 4-class + balanced sample weights | 0.3197 | **+12.1%** | ✅ same classes, same metric |
| 3-class (`3_to_5` ∪ `6_plus` → `3_plus`) | 0.3867 | +35.6% | ⚠️ fewer classes |
| binary (`cliff_in_stint` vs `no_cliff`) | 0.5903 | +107.0% | ⚠️ fewer classes |

**Only the first row is an apples-to-apples comparison.** Macro-F1 averages over classes,
so collapsing classes mechanically inflates it; the +35.6% and +107% are not free wins,
they are a different question being asked. Report them as what they are.

Recommended: take the balanced-weight change (+12.1%, same contract, same four classes,
no downstream schema change), and treat the collapse to 3 or 2 classes as a **product
decision** — does the app's cliff surface need "in 3–5 laps" vs "in 6+ laps" to be
distinguishable, given that today it is not distinguished at all? If the answer is no,
the 3-class label is both more honest and more accurate.

The 6,664 NULL labels (5.5%) are a separate question worth a look: they are dropped
silently from training, and nothing records why they are unlabelled.

---

## 2. The stint-life target is 41% right-censored

`remaining_stint_life_laps = stint_length_laps − lap_in_stint`. For a stint that ends at
a pit stop, this is "laps until the tyre needs changing". For a stint that ends at the
chequered flag, it is "laps until the race ends" — a different physical quantity that the
tyre had no part in setting.

| Stint kind | stints | mean length | ML training rows | share |
| :--- | ---: | ---: | ---: | ---: |
| ends at a pit stop | 5,920 | 16.8 laps | 71,336 | 59% |
| ends at the flag (**censored**) | 2,413 | 26.2 laps | 49,598 | **41%** |

Censored stints are 56% longer, because they are *selected* for being long — a tyre that
would have died before the flag caused a stop, which makes that stint uncensored. The
model is fitting a mixture of two populations under one label, with a selection effect
between them.

**How large is the damage?** Add a single forward-looking flag, `is_final_stint`:

| Variant | RMSE | vs base | final-stint rows | intra-race rows |
| :--- | ---: | ---: | ---: | ---: |
| base (42 features) | 7.524 | — | 5.93 | 8.35 |
| + `laps_remaining_in_race` | 7.478 | +0.61% | 6.00 | 8.25 |
| + `race_distance_laps` | 7.308 | +2.87% | 5.86 | 8.05 |
| + both | 7.257 | +3.55% | 5.85 | 7.98 |
| + `track_position`, `grid_position` | 7.523 | +0.02% | 5.94 | 8.34 |
| + SC hazard priors | 7.487 | +0.49% | 5.97 | 8.28 |
| + all six legitimate | 7.279 | +3.25% | 5.74 | 8.06 |
| **+ `is_final_stint`** ⚠️ **LEAKY** | **5.700** | **+24.24%** | **1.60** | 7.29 |

`is_final_stint` cannot be a feature — at lap *L* you do not know whether the driver will
stop again; that is the future. But the fact that one leaky bit is worth 24% while every
legitimate feature combined is worth 3.6% **is the measurement**: the censoring is where
the error lives, and no amount of feature engineering will reach it.

Note `fuel_mass_kg` already carries race progress — it correlates with
`laps_remaining_in_race` at **r = 0.975**, because initial fuel is
`race_lap_count × rate`. That is why `laps_remaining_in_race` adds only +0.61%: the model
already has it. This closes the "the model is blind to race distance" hypothesis.

**What actually fixes it.** Two legitimate routes were tested; a third was attempted and
did not converge:

| Variant | RMSE | vs base | final | intra-race |
| :--- | ---: | ---: | ---: | ---: |
| base (+ laps_remaining + race_distance) | 7.261 | — | 5.89 | 7.98 |
| + clamp `min(pred, laps_remaining)` at inference | 7.239 | +0.31% | 5.86 | 7.96 |
| train on uncensored stints only, then clamp | 8.127 | −11.92% | 9.47 | **6.99** |
| right-censored AFT (`survival:aft`) + clamp | — | — | — | — |

The clamp is free and correct (laps-remaining is known at inference), but nearly
worthless — the model rarely over-predicts past the flag.

The third row is the informative one. Training only on uncensored stints improves the
intra-race population from 7.98 → **6.99 RMSE (+12.4%)** — a genuine gain at the question
"when does this tyre die" — while wrecking final stints (5.89 → 9.47). That is not a
failure of the idea, it is the selection effect made visible: uncensored stints are the
short-life ones, so a model trained only on them systematically under-predicts on the
long-life stints, and a `min()` clamp cannot correct an under-prediction.

The principled fix is therefore **right-censored survival modelling** — XGBoost's
`survival:aft` with `label_upper_bound = +∞` on final stints, so a censored stint
contributes "life ≥ observed" rather than "life = observed". This is the standard
treatment and the project already has the vocabulary for it (`survival_weight`, the IPW
machinery in `fct_cliff_prediction_features`). **I attempted it in this pass and it
returned NaN**; the cause was not chased down (likely the loss scale or the infinite
upper bound). It is not concluded — it is the recommended next experiment, not a
recommended change.

**Why this reaches the app.** `predicted_remaining_stint_life_laps` surfaces in the
`blind-test-scoreboard` feature. On 41% of its rows the model is being publicly scored on
whether it predicted *the chequered flag*, not whether it predicted tyre death.

---

## 3. Seventeen unused warehouse signals add nothing (negative result)

`transform_gaps.md` closed with an "unused staged signals" inventory. The obvious next
move is to promote them into the feature set. **Measured, that move is worthless.**

All seventeen were joined onto `fct_cliff_prediction_features` and tested as a block:

| Signal | source | coverage |
| :--- | :--- | ---: |
| `track_position` | `stg_laps.position` | 100.0% |
| `min_gap_s`, `tow_benefit_lap_s`, `time_in_dirty_air_s` | `int_lap_air_state` | 93–100% |
| `track_temp_c`, `humidity_pct`, `wind_speed_ms`, track−ambient delta | `stg_weather` | 100.0% |
| `grid_position` | `stg_results` | 100.0% |
| `speed_i1/i2/fl/st_kph` | `stg_laps` | 83–100% |
| `laps_remaining_in_race`, `race_distance_laps` | derived | 100.0% |
| `sc_hazard_per_lap_shrunk`, `any_hazard_per_lap_shrunk` | `int_sc_hazard_history` | 100.0% |
| `allocated_sets_per_driver` | `stg_tyre_allocations` | **0.0%** — see #5 |

| Target | 42 features | + candidates | change |
| :--- | ---: | ---: | ---: |
| degradation p50 (RMSE, lower better) | 0.8271 | 0.8272 | **−0.01%** |
| cliff classifier (macro-F1, higher better) | 0.2850 | 0.2823 | **−0.95%** |

Nothing. The one place they *did* move a number is stint life (+3.25%, table in #2), and
that is race-distance information the model already had through fuel mass.

This is consistent with the project's own ablation artefacts, which already show
`weather_air` and `track` as net-negative groups for the cliff classifier
(`ml/artefacts/ablation_cliff_classifier.parquet`: removing `track` *improves* macro-F1 by
0.0047). The feature set is not starved; if anything it is slightly over-fed.

**Recommendation: close this thread.** Record the negative result so a future pass does
not re-derive it, and stop treating the unused-signal inventory as a backlog.

---

## 4. Air density is not worth building (negative result)

`ml/src/schema.py` carries an explicit deferral:

> The air-density weather features (`air_density_kgm3` / `density_ratio_to_ref`) remain
> DEFERRED pending air-density enrichment

The blocker is real and small: **`pressure_hpa` is present in bronze
(`data/bronze/weather/`), 100% non-null across all seven seasons, and staged nowhere** —
`stg_weather` projects 12 columns and drops it. One column in one staging model unblocks
it.

The physics look compelling. Pressure ranges 778–1023 hPa (Mexico City's altitude against
sea level), and computing density properly — dry-air + vapour partial pressures via
Tetens — gives **0.902 to 1.241 kg/m³, a 37.6% spread**. Downforce, drag and thermal load
all scale with it.

Measured marginal value, both features added to the 42:

| Target | base | + air density | change |
| :--- | ---: | ---: | ---: |
| degradation p50 (RMSE) | 0.8299 | 0.8326 | **−0.33%** |
| cliff classifier (macro-F1) | 0.2834 | 0.2854 | **+0.70%** |

Both inside the noise of the harness. The reason is that air density is very nearly a
per-circuit constant, and circuit identity is already in the feature set three times over
(`track_energy_index`, `circuit_abrasiveness_index`, and the per-circuit-per-season
compound cliff parameters). The model already knows Mexico is Mexico.

**Recommendation: close the `DEFERRED` note in `ml/src/schema.py` with this measurement**
rather than leaving it as an open TODO that reads like unrealised value. Staging
`pressure_hpa` is still cheap and defensible for completeness — but it should not be sold
as an ML win, and it should not be sequenced ahead of #1 or #2.

---

## 5. `tyre_allocations` — a seed loaded into the warehouse and consumed by nothing

`transform/seeds/tyre_allocations.csv` is a 44-row seed covering 2023 (21 races) and 2024
(23 races), with columns `season, circuit_key, hard_code, medium_code, soft_code` — the
Pirelli mapping from the *relative* label to the *absolute* compound (C1–C5).

It is materialised in `dev.duckdb` as `tyre_allocations`. **Nothing reads it** — not a
`ref()`, not a macro, not the export script, not the app.

Meanwhile `stg_tyre_allocations`, the model whose whole job is that mapping, is a
deliberate stub returning zero rows, and its header says:

```sql
-- SOURCE NOT YET INGESTED  requires scraping or manual seed from
-- Pirelli allocation sheets.
```

The manual seed it asks for exists, in the seeds directory, for two of the seven seasons.
This is exactly the `FreshTyre` / `int_pit_loss_circuit` pattern `transform_gaps.md` was
built to catch: staged data on one side, a stub declaring it absent on the other, and no
`ref()` between them.

**Why it might matter, stated as a hypothesis and not a result.** `compound` is currently
a *relative* label: a `HARD` at Bahrain (C2) and a `HARD` at Suzuka (C3) are different
rubber, and the model sees the same token. Absolute codes would let the compound
parameters pool across races by physical compound rather than by weekend nomenclature —
the same class of correction as `transform_gaps.md` finding #3 (event slug vs physical
venue). **This was not tested**, because 44 races of 149 is too thin a slice to CV
honestly against the harness above. It is a hypothesis with a real mechanism, gated on
backfilling 2018–2022.

Minimum honest action, regardless: either wire the seed and narrow the stub's comment to
"2018–2022 not yet seeded", or delete the seed. Loading a seed nothing reads while a stub
declares it missing is the trap this series keeps finding.

---

## 6. `int_sc_hazard_history` is a leaf (already known)

Recorded for completeness, not as a discovery — `docs/transform/families/strategy.mdx`
already states it plainly:

> `int_sc_hazard_history` remains a genuine leaf: built, tested by its own singular test,
> read by nothing else in dbt and exported to no app feature.

Confirmed by a full-repo grep: the only references outside the model, its schema entry and
its singular test are documentation. Finding #3 tested its two shrunk hazard columns as
features and they were worth +0.49% on stint life and nothing elsewhere, so promoting them
into the feature set is not the answer.

The docs already name the right consumer: a lap-by-lap race simulation that *draws* a
Safety Car needs exactly a per-lap hazard. That is the `int_pit_strategy_value` rewrite
below, not a feature addition.

---

## Carried forward from `transform_gaps.md`

Unchanged and still the highest-value item in the strategy family — restated here because
this audit's findings reinforce it:

> `int_pit_strategy_value`'s optimal-pit-lap search approximates the argmin as "first lap
> in the cliff window where expected wear exceeds 0.5 s" — a threshold with no pit-loss
> term in it. A longer pit lane does not push the modelled optimum later, which it
> physically should. `strategy_verdict` returns `optimal` on 8 of 7,129 stints.

Solving the real `Total_Cost(L)` minimisation is where `int_pit_loss_circuit` (now
correct, Phase 4) and `int_sc_hazard_history` (finding #6) both finally get consumed, and
it is the one item on this page that creates new app capability rather than repairing
existing numbers.

---

## Suggested sequencing

1. **#1 — cliff classifier class weights.** Smallest change on the page, +12.1%
   apples-to-apples, no schema change, no app change. Do it first. Then put the
   4-vs-3-class question to a product decision with the per-class table above in hand.
2. **#2 — stint-life censoring.** Get `survival:aft` converging (it did not, here), then
   compare it honestly against the current framing on both sub-populations separately, not
   on a pooled RMSE. Whatever the outcome, `blind-test-scoreboard` should report the two
   populations separately — a single number over a 41/59 mixture is not interpretable.
3. **#5 — `tyre_allocations`.** Half-hour decision: wire it or delete it. Do not leave it
   as-is.
4. **Pit-strategy `Total_Cost(L)` rewrite.** The real work, and the only item that adds an
   app capability. Everything else on this page is repair.
5. **#3 / #4 — record and close.** Add the negative results to the docs so they are not
   re-derived. Optionally stage `pressure_hpa` for completeness, sold as completeness.

**Not recommended:** promoting the unused-signal inventory into the feature set, and
building air-density enrichment as an ML feature. Both were measured; both are worth
approximately zero.

---

## Checkpoint

- 2026-08-22: Audit written. Nothing implemented, nothing committed. All six findings
  measured against `data/dev.duckdb` read-only with the harness described at the top.
  Findings #3 and #4 are negative results and are complete as written — they need no
  implementation, only recording. Findings #1, #2 and #5 are open.
- Open question for the user, blocking #1: does the app need `3_to_5` and `6_plus` to be
  distinguishable, given they are not distinguished today?
- 2026-08-23: **Answered, and the question dissolves.** `6_plus` was not indistinguishable
  for want of features or class weight — the label never tested horizon 4 and never tested
  past 6, so `6_plus` meant "exactly 6" and every cliff 7+ laps out sat in `none_in_stint`.
  Repaired, `6_plus` reaches F1 0.321 and the four classes are worth keeping. See
  `ml_headroom_ii.md` §1. Findings #1 (fixed in the working tree), #2 (measured, not
  implemented) and #5 (closed as a negative result) are all resolved there; #3, #4 and #6
  stand as written.
