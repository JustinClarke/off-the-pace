# Research round R1 — state-of-the-art scan

**Opened and drafted 2026-09-07.** A one-off R&D round asking a question the programme's
notebooks have not asked: *what does the current literature offer that this data could carry?*
Across ML, statistics, causal inference, the transform layer, and the published F1 field.

**This is not a tracker.** Stage lives in [`../status/build-log.json`](../status/build-log.json)
and only there. Progress through this round is tracked in
[`../research-log.json`](../research-log.json). Findings that survive triage get promoted into the
build log as items with a stage; until they are, nothing here is a commitment.

**Nothing was shipped, committed, or modified.** All measurement was `read_only=True` against
`data/dev.duckdb` plus one read of `data/marts/mart_degradation_predictions.parquet`. No model
artefact, no warehouse table, no `ml/models/*.json` and no git state was touched.

---

## The documents

| Doc | Covers | Prices |
| :--- | :--- | :--- |
| [R1 — Instruments](R1-instruments.md) | the noise floor, the multiplicity audit, the headline score | `01a` `01b` `04a-c` `05a` |
| [R2 — Model family](R2-model-family.md) | hierarchical, distributional, shape-constrained, foundation models | `05a` |
| [R3 — Competing risks](R3-competing-risks.md) | stint life is not a single-event survival problem | `02d` `05a` |
| [R4 — Conditional coverage](R4-conditional-coverage.md) | the band is marginally right and conditionally wrong | `06` · the app |
| [R5 — Representation & transform](R5-representation-and-transform.md) | path signatures, FPCA, and the leakage-guard gap | `02a` `02c` `02d` · transform |
| [R6 — Causal, decision & the field](R6-causal-decision-and-the-field.md) | AKM, DML/IV, the unassembled DP, and where this project stands | `03c` `07a-b` `06` · the app |

---

## Ranked findings

Ranked by **value per day**, not by intellectual interest. The top five are the round's answer.

| # | Finding | Cost | Kind | Doc |
| ---: | :--- | :--- | :--- | :--- |
| 1 | **The stint-life target is a competing-risks problem.** 1,543 of 5,360 uncensored stints (**28.8%**) end under SC, VSC or red flag, and they run **11.1 laps against green's 19.4**. The AFT model is told each is a completed tyre life. Present in all seven seasons. | days | measured defect | [R3](R3-competing-risks.md) |
| 2 | **`audit_forward_window` is blind to aggregation-scope leakage**, and **both** of the programme's known live leakage suspects sit precisely in the gap — neither has a `LEAD`, a `FOLLOWING` frame or a self-join inequality. Extending the walker to `GROUP BY` scope converts a class of silent bug into a build failure. | days | prevention | [R5](R5-representation-and-transform.md) |
| 3 | **The prediction band is conditionally miscalibrated on circuit** — 72.4% at Mexico to 85.6% at Mugello, **13.2 points across 36 circuits, in-sample** — while being near-perfect marginally (80.38%) and on tyre age (1.3 points). Mondrian/CQR recalibration fixes it without touching the model. | 1–2d | measured defect | [R4](R4-conditional-coverage.md) |
| 4 | **The stochastic DP over pit timing is ~80% built and never assembled.** `int_pit_strategy_cost_curve`, `int_pit_loss_circuit`, `int_sc_hazard_history` (which `schema.py` records as *"unconsumed today"*) and the five models are the transition costs, event process and dynamics of a published DP formulation. It yields a headroom metric **in seconds of race time**. | days | assembly | [R6](R6-causal-decision-and-the-field.md) |
| 5 | **`01b` should be rebuilt as difference-based variance estimation**, a forty-year-old solved problem the programme reinvented. **Three of the five defects `work/01` lists dissolve**; the m-bias is the family's defining closed-form correction, and there is no `d → 0` step to extrapolate. Separately: a kNN floor over 33 scaled columns is **outside the regime where kNN Bayes-error estimation has been shown to work**. | rescope | method | [R1](R1-instruments.md) |
| 6 | **e-values / e-BH replace the retrospective BH plan** and **dissolve `04b`** — an e-value is built directly from the reseed distribution, so no floor-ratio-to-p-value conversion is needed. Stopped e-BH is FDR-valid at any data-dependent stopping time, which is the actual shape of a 22-checkpoint campaign. | 0.5d + a gate change | method | [R1](R1-instruments.md) |
| 7 | **Monotone constraints are free and answer half of `work/05`'s structural case.** XGBoost supports them natively; `behaviour_audit`'s monotonicity probe becomes a test of a guarantee. Should not be blocked behind `01`. | hours | cheap win | [R2](R2-model-family.md) |
| 8 | **Hand-crafted telemetry aggregation is measured to add nothing.** Phase 9 dropped every one of the eleven `int_lap_telemetry_aggregates` columns; the only group that ever cleared came from a different sensor. **Path signatures** (deterministic, reparameterisation-invariant, ~100 columns, no training loop) and **FPCA** on the 100-fraction `relative_distance` grid `int_lap_proximity` already builds are the untried representations. | days–weeks | representation | [R5](R5-representation-and-transform.md) |
| 9 | **The published state-space tyre-degradation model exists at one-race scale.** Latent degradation, lap times as observation, fuel in the observation equation, pit stops as state resets, skewed-t errors. Its stated limitation is that it needs generalising to multi-race and multi-driver. This is the only public dataset that can. | days | publication + feature | [R6](R6-causal-decision-and-the-field.md) |
| 10 | **GPBoost is a third bracket leg for `01`, not just a candidate for `05a`.** Tree boosting *plus* grouped random effects returns fitted variance components — a model-based irreducible-noise estimate that fails in different directions from a neighbourhood one. A measurement-only probe ships nothing. | 1–2d | instrument | [R2](R2-model-family.md) |
| 11 | **CRPS should sit beside the pinball trio.** Averaged quantile loss converges to it; it scores the distribution as one object, makes distributional models comparable to the incumbent, and its calibration/resolution/**uncertainty** decomposition gives an independent read on the same quantity `01b` is chasing. | hours | instrument | [R1](R1-instruments.md) |

## Negative results and non-recommendations — recorded so they are not re-derived

- **Do not "fix" marginal calibration.** Pooled coverage is 80.38% against a nominal 80, with
  symmetric tails, on a target with skew −0.83. The problem is conditional, not marginal.
- **Quantile crossing is not available as an argument.** `predict.py:53` row-sorts the trio with
  `np.sort` before writing, so the parquet's zero crossings say nothing about the models. The raw
  rate is unmeasured; only a >1% breach is logged.
- **The compound-conditional coverage spread is a small-n artefact** — HYPERSOFT n=295, WET n=60.
  The four compounds carrying 96% of rows sit at 80.0–81.5%.
- **Do not migrate off dbt/DuckDB.** SQLMesh's time-range semantics would prevent some leakage
  structurally, but finding #2 buys that property directly for a fraction of the cost of
  re-earning 70 models, a lint config, a test suite and a working SQL-AST auditor.
- **Modern staggered-adoption DiD does not apply to `07`.** A safety car is not an absorbing
  treatment. It is worth knowing for `03c`'s two-way FE; it is not an estimator for the SC
  experiment.
- **Tabular foundation models are an instrument, not a shipping candidate.** Their reported win
  rates are over i.i.d. benchmark suites, not panels with season-grouped CV and an overlapping
  5-lap target, and they have no ONNX path.
- **This project's evaluation protocol is ahead of the published field.** The nearest peer-reviewed
  competitor wins on a bidirectional architecture over a forecasting problem, with SMOTE applied
  across a temporal split, and leads with ROC-AUC on a 3.5%-positive target. See
  [R6](R6-causal-decision-and-the-field.md) Part 1.

---

## Epistemic register for this round

Following [`../foundations/epistemics.md`](../foundations/epistemics.md).

**Verified** — traced to a query or a code path, all read-only:

- The end-regime decomposition of 8,333 stints and its per-season stability ([R3](R3-competing-risks.md)).
- The target's shape: n=82,315, skewness −0.829, excess kurtosis 5.218 ([R2](R2-model-family.md)).
- Band coverage, marginal and by four conditioning variables ([R4](R4-conditional-coverage.md)).
- That production v11 trains on `race_year < holdout_season`, holdout = `MAX(race_year)+1` = 2025
  and unpopulated — so **every coverage number in this round is in-sample** (`features.py:115-121`,
  `features.py:195-213`).
- That `predict.py:53` row-sorts the quantile trio before writing.
- That `int_corner_skill_residuals` buckets by `FLOOR(lap_number/5.0)*5.0` + `GROUP BY`, and
  `int_sc_hazard_history` aggregates to one row per circuit across all seasons — **neither
  containing any construct `audit_forward_window` inspects.**

**Assumed** — inference, flagged as such:

- That the loss currently attributable to non-green stint endings is material in AFT NLL terms.
  The share and the length gap are measured; the loss attribution is `02d`'s arithmetic.
- That circuit-level heteroscedasticity the 33-column contract cannot express is the mechanism
  behind the coverage spread. Plausible; the traffic/deployment-regime alternative is not excluded.
- That a signature or FPCA representation would clear `gates.md` where the scalar aggregates did
  not. The aggregates' failure is measured; the replacement's success is a hypothesis.

**Gates run:** None. This round measured and read; it fitted nothing and shipped nothing.

**A flag, not a ruling, on the pointer item `02a`.** Its acceptance criterion is binary — centred
(leaks) or backward-looking (safe). The SQL is **neither**: a fixed `FLOOR(lap/5)*5` block, so the
forward reach is position-dependent within the block and averages about two laps. Running `02a` is
the next session's job; this is only notice that the item admits a third answer and that the fix
is likely "recompute as a trailing window" either way. See
[R5](R5-representation-and-transform.md) Part 2.
