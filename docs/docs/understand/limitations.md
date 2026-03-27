---
sidebar_position: 5
title: Limitations
---

# Limitations

A senior engineer documents exactly where their model breaks. These are the known limitations of the current decomposition.

---

## 1. Sequential residualisation propagates error

The identification strategy (see [Methodology](./methodology.md)) estimates terms sequentially. Each step subtracts an estimated quantity and operates on the residual. This means estimation error in an early term (say, the fuel weight penalty at a circuit with few qualifying stints) propagates into every downstream term including the driver residual.

The additive identity holds exactly by construction. But if the compound coefficient is miscalibrated for an unusual circuit, the driver residual absorbs that miscalibration. The CI test proves the math; it cannot prove the coefficients are physically correct.

## 2. Tyre compound coefficients require sufficient data

The KM survival estimates and hockey-stick polynomial coefficients are estimated per `(circuit, compound, season)`. Groups with fewer than ~8 qualifying stints produce high-variance estimates. Currently 24 circuits in `circuit_reference.csv` have a `REVIEW_REQUIRED` flag on weight penalty calibration, as these circuits have limited telemetry or unusual tyre behaviour.

The `dim_compounds_season` seed has 401 groups. Not all are equally well-calibrated. Treat driver residuals at circuits with `REVIEW_REQUIRED` flags with more caution.

## 3. 2025 data not yet ingested

The model was trained on 2018–2024. 2025 OpenF1 data is publicly available but has not yet been ingested into the Bronze layer. Until it is, the decomposition produces no 2025 laps. The out-of-sample validation against 2025 data is planned for after ML.

## 4. No 2018 Rounds 1–2 telemetry

F1 did not publish live timing telemetry until mid-season 2018. Rounds 1 and 2 of 2018 (Australia, Bahrain) have no telemetry data in the Bronze layer. This does not affect the decomposition for other races but means 2018 is slightly underrepresented in coefficient estimation.

## 5. Weather granularity is session-level

Track temperature and weather data come from `stg_weather` at session resolution. Within-race weather variation, such as afternoon temperature rises or brief cloud cover, is captured only coarsely by the ambient component. High-sensitivity compounds at circuits with strong afternoon temperature gradients (e.g., Bahrain, Abu Dhabi) may have less precise decomposition.

OpenF1 provides 1 Hz weather data. Higher-resolution ambient modelling is possible but not yet implemented.

## 6. Constructor coefficients are pre-season priors

Constructor structural pace priors are estimated from 2018–2024 data and held fixed for the 2025 validation window. A team that undergoes a major performance shift mid-season (like a large floor upgrade or a performance regression from regulation changes) will have a stale constructor coefficient. The driver residual absorbs the difference until the constructor model is refitted.

## 7. ML cliff prediction: built, but v1

The [machine layer](/machine-learning) is built: five XGBoost models turn the population-level KM survival prior into per-stint, per-lap predictions (degradation quantile trio, laps-until-cliff classifier, remaining stint life), each beating a strong per-cohort baseline. The honest remaining limitations are narrower:

- The **cliff classifier is the weakest model** (macro-F1 ≈ 0.37 on 4-class cliff timing)-it decisively beats the majority prior but absolute skill on the rare imminent-cliff windows is modest.
- There is **no live 2025 holdout** yet, so headline numbers are time-series cross-validation (final fold = 2024), not a held-out season. They flip to a true out-of-sample reveal the moment 2025 ingests.

See the [model card](/reference/ml/degradation-model-v1) for the full numbers and [Limitations & roadmap](/machine-learning/limitations-and-roadmap) for the complete accounting.

## 8. Frontend not built

The React + DuckDB-Wasm race page does not exist yet. The decomposition results exist in DuckDB at `data/dev.duckdb` and can be queried directly, but there is no interactive visualisation.

## 9. No live cloud warehouse

The production engine is DuckDB (local + CI). Microsoft Fabric Lakehouse is a planned future target but is not yet wired up. All builds and tests run against DuckDB.

---

## Data ceiling

The limitations above are *modelling* choices things we could improve with better calibration or more code. The limits below are fundamental: they follow from what the FIA and FastF1 expose, regardless of modelling effort. State them plainly; the project's credibility comes from modelling around them honestly.

| Limit | Consequence | How we cope | ML implication |
|---|---|---|---|
| **No tyre temperature or pressure** FIA does not expose sensor data | Degradation is **always inferred from lap-time decay**, never measured the defining constraint of the whole project | Model degradation as a latent decay from clean-lap pace; validate against stint shapes, not ground truth | Don't feature/predict tyre temp; treat degradation as a latent target with honest uncertainty |
| **No actual fuel load** | Fuel-correction is modelled, not observed (`int_lap_fuel_state` infers from lap count) | Keep the assumed burn-rate explicit and seeded; sensitivity-test it | Fuel effect is a prior, not a feature |
| **No setup data** wing angle, ride height, diff, camber are never published | Car setup is **confounded with constructor**; can't separate "good car" from "good setup" | Absorb into constructor + circuit-interaction terms; label as confounded | Constructor coefficients carry setup variance don't over-interpret |
| **No ERS state-of-charge or deployment map** | Energy management only **proxied** from throttle/RPM/speed patterns (CAP-5) | Use the proxy as a control, not ground truth | Deployment is a noisy proxy feature |
| **No steering angle** | Can't measure understeer/oversteer or smoothness directly | Infer cornering style from GPS line and speed/throttle traces | Driving-style features are kinematic proxies |
| **Telemetry is ~10 Hz, interpolated** not raw FIA 100+ Hz | Fine for lap/stint aggregates; **lossy** for micro-corner and exact pass-instant work | Prefer aggregate features; use lap `position` as backstop for events | Don't claim sub-metre / sub-100 ms precision |
| **`session_time_s` null for 2024** FastF1 v3.8.3 bug | Can't time-join race-control events precisely for 2024 | Join on `Lap` number instead | Per-lap granularity only for 2024 control events |
| **Track boundaries not provided** | Off-track / track-limits is a **proxy** from the empirical car-position envelope | Document the envelope assumption; cross-check against `is_track_limits_deletion` | Track-limits feature is approximate |
| **Pre-2018 coverage absent; tyre-compound labels shift by era** | Cross-era comparisons need normalisation | `int_era_normalized_driver_rating` + era-aware compound dims; always include a regulation-era control (2022 ground-effect break is the biggest discontinuity) | Era control is mandatory in any cross-season model |

None of these limitations invalidate the decomposition framework. They define where the current estimates should be treated with more caution, where data improvements would help most, and what the roadmap is addressing next.
