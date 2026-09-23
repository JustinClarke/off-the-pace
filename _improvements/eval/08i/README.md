# 08i Evaluation — the `min_observations` floor on `int_lap_thermal_proxy`

## Status

**GATED — 2026-09-18, on the `v12`/`08m` substrate.** Gate steps 1–7 run on four floors
(1, 2, 3, 5) across all five production families. 240 refits through `evaluate.py`'s own
`_fit`/`_score`. Nothing committed; nothing written to `ml/models/`, to the warehouse or to
`ml/artefacts/evaluation_metrics.json`.

**Ruling:** floors 3 and 5 **rejected** with the gate behind them. **Floor 1 recommended** over
the built floor 2 — but as a preference, not a majority clear. Landing it needs a warehouse
rebuild plus an artefact retrain, raised as decision **D10**.

**LANDED — `D10` resolved YES 2026-09-21; shipped inside the one `v12 → v13` bundle `D16` asked
for, with `02b`/`D12`, `08o` and `08q`. Verified independently 2026-09-22** — see *Landing
verification* at the foot of this file and in `MEASUREMENTS.md`. The floor-1 revert is in the built
warehouse bit-for-bit, all five shipped `v13` artefacts reproduce their published headline exactly
from it, and the two defects listed below are fixed.

## The question

`08e` rebuilt `stint_baseline_pace` as an expanding median over valid laps strictly before the
scored lap, with a minimum-observation floor, and priced floors 1/2/3/5 without taking any of them
through the gate. Its own note: *"Floors above 1 buy a little more degradation signal for several
points of coverage — a trade worth re-testing through the gate, not settling here."*

## Two corrections to the premise, both made before any arm ran

1. **The substrate was already floor 2.** The work doc says the rebuild "took
   `min_observations=1`". That stopped being true on **2026-09-10**, when a prior `08i` session
   set the SQL to `min_observations=2`; the change rode into git inside commit `c49473a`, whose
   message ("Add campaign-level multiple comparison audit and analysis scripts") does not mention
   it. `08m` rebuilt the warehouse on 2026-09-16, so **every v12 number in the tree sits on a
   floor-2 thermal block**. The BEFORE arm here is floor 2; floor 1 is a *revert*.
2. **The prior session's result is not carried forward.** It left **no artefact anywhere** — no
   JSON, no log, no script; this directory was empty. Its claims exist only as prose in
   `build-log.json`. Its headline claim — floors 2 and 3 give *"IDENTICAL headline results …
   across all five families"* — is **refuted**: measured here, the four floors give clearly
   different headlines in every family (stint-life: 1.9926 / 1.9913 / 1.9881 / 1.9909). Two floors
   that differ on 6,414 eligible rows cannot produce bit-identical headlines in five families.
   That arm never varied.

## The structural finding that reframes the item

`is_training_eligible` is `age_in_stint > 3 AND COALESCE(anomaly_class,'normal') NOT IN
('mistake','conditions')`. It **never references the thermal block**, so raising the floor turns
values into NaN and **never deletes a row**. Consequences:

- The leaf doc's central hazard — *"a headline that improves by deleting the hard rows is not an
  improvement"* — is **structurally absent**. Eval rows are identical at every floor
  (13,712 / 13,712 / 18,866 / 19,973), reported per family per floor to show it rather than
  assert it.
- The cross-floor contrast is **capacity-neutral by construction**: same 32 columns, same rows,
  same split. A cross-floor delta cannot be a capacity artefact. Step 4 was still run, because
  "not capacity" is not "not noise".

## Method

Only the four `thermal` columns vary — `push_residual`, `cumulative_push_load_surface`,
`cumulative_push_load_bulk`, `surface_bulk_ratio`. The contract stays 32 wide.

The four floors come from a **floor-parameterised replica** of `int_lap_thermal_proxy`'s window
logic, run read-only against the warehouse, rather than from four dbt rebuilds. That is only
legitimate because of step 1b:

| step | what | outcome |
| ---: | :--- | :--- |
| 1a | `_fit`/`_score` reproduces the published v12 headline | **exact, `0.00e+00`, all five** |
| 1b | replica at floor 2 vs the **built** warehouse | **bit-for-bit, 137,447/137,447 rows, all four columns, NULL pattern included** |
| 2 | add-ablation on `cv_final_fold` (train 2018–23, eval 2024) | per floor, per family |
| 3 | 5-reseed floor per arm, quoted against the **larger** of the two | `08g` convention |
| 4 | permutation null, four columns shuffled **jointly** in train and eval | within each floor |
| 5 | forward-window audit | **CLEAN**; leakage guard CLEAN (32 features) |
| 6 | pre-registration | written into the work doc before the arms ran |
| 7 | Construction B (paired safe-t), `n=5`, `g=1.0` | validity checked at four σ |

Floors 1/3/5 are that same replica query with one integer changed, which is what makes them
comparable to the built arm rather than to a reimplementation.

**One extra control, declared in advance.** `shuffled(F) − shuffled(2)`: both arms row-shuffled,
so the signal is destroyed in both and only NaN density differs. It separates "the floor changed
the information" from "the floor changed the missingness".

## Result

Full tables in [`MEASUREMENTS.md`](MEASUREMENTS.md) and in the work doc's
`08i — RESULT 2026-09-18` section. The short form:

**The trade does not exist.** `08e` priced higher floors as buying signal for coverage. They cost
**both**. Floors 3 and 5 clear their own floor *in the wrong direction* on p10, p90 and cliff,
and every missingness-only control is small (|0.09×|–|0.39×|) — so that is destroyed information,
not NaN density.

| floor | coverage (eligible panel) | verdict |
| ---: | ---: | :--- |
| 1 | 98.20% | **recommended** — best on all three degradation heads; clears on p50 at +1.25× (`E`=13.5) |
| 2 (built) | 96.05% | the status quo; beaten by floor 1 on the degradation trio, better on cliff by 0.36× (inside floor) |
| 3 | 90.70% | **rejected** — clears against on p10 (−2.10×), p90 (−1.44×), cliff (−1.11×) |
| 5 | 80.35% | **rejected** — clears against on p10 (−2.29×), p90 (−1.57×), cliff (−1.00×) |

The thermal block carries real information at **every** floor (+1.41× to +50.86× its own floor,
`E` 18.5–35.9), consistent with `08e`'s family-T finding. What the floor changes is how much —
and more floor means less, with `stint_life_regressor` the single exception.

## The honesty note

The pre-registered decision rule asked floor 1 to clear on a **majority** of the five families.
It clears on **one** (p50). The rule's two branches — "clears on a majority" and "clears nowhere"
— did not anticipate this case. That gap is recorded rather than resolved by re-reading the rule
after seeing the data. Floor 1 is recommended on the *weight* of the evidence (best on 3 of 5
point estimates, never worse than its own floor anywhere, most information in total, +2.15pp
coverage, and it halves the over-representation of blind rows in the hardest cliff class) — not
on a gate pass it did not achieve.

## Where the coverage goes — the leaf doc's hazard, confirmed

The `0_to_2` cliff class is 10.05% of eligible rows. Its blind rate rises monotonically with the
floor: **10.48% → 12.13% → 17.44% → 26.13%**. At floor 5 a quarter of the hardest class has no
thermal reading at all. That is the mechanism behind cliff's −1.11× and −1.00×.

## Two live defects this item found — both fixed 2026-09-21

- `transform/tests/assert_no_future_leakage.sql` hard-codes `>= 2` — a second copy of the
  parameter that must move with any floor change or it fires spuriously. **Fixed**; it held *two*
  copies (`>= 2` in the baseline CASE and `expected_n_prior < 2` in the floor check) and both now
  read 1. The test passes on the built warehouse.
- `transform/models/intermediate/schema.yml` still documents **floor 1** for
  `stint_baseline_pace` ("NULL until *one* valid prior lap exists … Costs 1.41pp") while the SQL
  runs floor 2 at a measured 3.95pp. **Fixed**; the description now states the floor explicitly,
  carries this item's provenance and both the v12 and the realised v13 coverage figures.

## Landing verification — 2026-09-22, read-only

Run because the build log could not answer it: the 2026-09-22 handoff entry recorded 08i as an
*unlanded* member of the v13 bundle and flagged in its own `assumed` field that it had not checked
`ml/models/` or `S.MODEL_VERSION_DEFAULT`. Checked directly, it had landed.

1. **The revert is in the warehouse.** This item's floor-parameterised replica, re-pointed at
   floor 1, reproduces the **built** thermal block bit-for-bit: 137,447/137,447 rows on all four
   columns, NULL counts **7,094 / 7,094 / 7,094 / 20,263** — against floor 2's
   14,017 / 14,017 / 14,017 / 27,287 at the time of the gate run.
2. **The floor is 1 by direct invariant.** 0 violating rows of 162,729 on
   `stint_baseline_pace IS NULL ⟺ baseline_observations_n < 1`, and the minimum
   `baseline_observations_n` on a non-NULL baseline is exactly 1.
3. **The shipped artefacts are fitted on it.** All five published `v13` headlines reproduce to
   `0.00e+00` from the current warehouse through `evaluate.py`'s own `_fit`/`_score`
   (table in `MEASUREMENTS.md`).
4. **Lineage green.** `dbt test --select int_lap_thermal_proxy+` PASS=35 ERROR=0;
   `assert_no_future_leakage` PASS; `python3 -m ml.src.features --check` CLEAN.

**Still owed by the bundle, not by this item:** `transform/tests/data_profile.baseline.json` is
un-re-snapshotted (95 drift entries, most of them other items'), and `app/public/models/` still
holds the v12 ONNX set — the only two failures in `make ml-test` (226 passed, 2 failed), remedied
by `make app-models`, which touches the deploy surface `D2` governs.

## Artefacts

- `ml/artefacts/08i_min_observations_floor_arms.json` — every arm, every seed, every `E`
- `ml/artefacts/08i_min_observations_floor_arms.log` — the run log
- `scripts/arms_08i_min_observations_floor.py` — the arms, including the replica SQL
