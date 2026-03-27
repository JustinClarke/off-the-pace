---
sidebar_position: 7
title: "Part 6: Residual Layer"
---

# Part 6: The residual layer

The residual layer isolates driver skill. By subtracting all calculated physical and baseline components from raw lap times, the remaining variance represents the causal contribution of the driver.

---

## 6.1  The Seven-Term Decomposition Identity

`int_lap_residual_decomposed` calculates the full additive decomposition. For every valid lap, the sum of all physical components plus the driver skill residual must equal the raw field-relative pace delta:

$$\text{pace\_delta\_s} = \text{fuel\_component\_s} + \text{compound\_component\_s} + \text{rubber\_component\_s} + \text{ambient\_component\_s} + \text{constructor\_component\_s} + \text{dirty\_air\_tax\_s} + \text{driver\_skill\_residual\_s}$$

Where:
*   $\text{pace\_delta\_s}$: Driver's lap deviation from trimmed field average ($\text{lap\_time}-\text{base\_track\_pace}$).
*   $\text{fuel\_component\_s}$: Lap-time penalty incurred due to remaining fuel weight.
*   $\text{compound\_component\_s}$: Tyre wear penalty based on compound age and track temperature.
*   $\text{rubber\_component\_s}$: Track rubber-in grip advantage (monotonically increasing).
*   $\text{ambient\_component\_s}$: Thermal weather fluctuations.
*   $\text{constructor\_component\_s}$: Isolated team car performance index (Aero/Power).
*   $\text{dirty\_air\_tax\_s}$: Aerodynamic wake penalty.
*   $\text{driver\_skill\_residual\_s}$: The closure term, representing driver execution.

### Identity Integrity
The identity must close exactly on every single row to floating-point tolerance ($< 1e-4\text{ s}$). If any component is updated without matching adjustments in the residual, singular closure tests fail, halting the integration.

### Qualifying Session Residuals
Qualifying sessions are processed in parallel via `int_lap_residual_decomposed_qualifying.sql` and `int_qualifying_decomposed.sql`. These use qualifying-specific fuel, tire, and team baselines to isolate single-lap qualifying driver speed.

---

## 6.2  Multi-Grain Residuals: Sector & Corner Level

To isolate exactly *where* on the circuit a driver is gaining or losing time, the pipeline decomposes lap-level metrics down to sector and corner granularities:
*   `int_sector_residual_decomposed`: Computes the seven-term identity separately for Sectors 1, 2, and 3.
*   `int_corner_skill_residuals`: Normalizes minimum speeds (`v_min`), braking, and throttle points per corner against circuit-level medians.
*   `int_tyre_surface_vs_bulk_decoupling`: Separates tyre thermal load into surface (fast-responding, τ≈3 laps) and bulk (slow-responding, τ≈5 laps) components-isolating whether pace loss is driven by immediate overheating or cumulative thermal degradation.

This enables detailed sub-lap skill profiling, isolating whether a driver excels in high-downforce twisty zones (S2) or high-speed straight-line traps (S1/S3).

---

## 6.3  Race Events: `int_race_control_events`, `int_overtakes`, `int_penalties`

Three models enrich the residual layer with structured race-event data:
*   `int_race_control_events`: Forward-fills SC/VSC/red-flag neutralisation windows from the race-control message log. Grain: race × lap (field-wide, not per driver). Replaces the coarse TrackStatus digit in stg_laps with a precisely bounded flag.
*   `int_overtakes`: Identifies on-track position changes from telemetry (driver-ahead transitions), distinguishing pit-cycle gains from genuine racecraft.
*   `int_penalties`: Extracts penalty and investigation events from the race-control log. One row per message-a single incident may produce multiple rows (investigation → decision).

---

## 6.4  `int_event_corrections`   Anomaly Weighting

Laps impacted by incidents, safety cars, or yellow flags do not represent competitive driver skill. `int_event_corrections` assigns a manual weight ($w \in [0.0,\, 1.0]$) to every lap based on incident metrics:

| Weight | Classification | Criteria |
|---|---|---|
| **$0.0$** | `deleted` | Lap time deleted by stewards (track limits, etc.). |
| **$0.0$** | `major_outlier` | Lap residual exceeds $5 \times$ Median Absolute Deviation. |
| **$0.3$** | `safety_car` | Full Safety Car period (regulated, slow pace). |
| **$0.5$** | `virtual_sc` | Virtual Safety Car period (regulated pacing). |
| **$0.7$** | `restart` | Out-lap immediately following a restart or SC period. |
| **$0.7$** | `pit_lap` | In-lap and out-lap containing active tyre swaps. |
| **$0.8$** | `local_yellow` | Yellow flag flags active in one or more sectors. |
| **$1.0$** | `clean` | Free, unconstrained racing lap. |

---

## 6.5  `int_lap_anomaly_flags`   Trailing MAD Anomaly Detection

Laps with highly irregular residuals are statistically classified to determine their underlying causes. We implement a **Trailing Median Absolute Deviation (MAD)** window rather than standard standard-deviation metrics to protect the calculations from outlier distortion:

$$\text{MAD} = \text{median}\left(|x_i \text{median}(X)|\right)$$

### The Trailing Window Constraint
The rolling window utilizes a trailing $7$-lap sequence (excluding the current lap $t$). **Centred windows are strictly prohibited.** A centered window would leak future lap information (such as post-cliff degradation times) into the current classification, causing data leakage that would mask tyre-cliff onsets in training datasets.

### Modified Z-Score Threshold
A lap's modified Z-score is calculated as:
$$M_i = \frac{0.6745 \cdot (r_i \text{median}(R))}{\text{MAD}}$$

Laps with $M_i > 3.5$ are flagged as anomalous and categorized:
*   `clean_cliff`: Anomaly matches expected tyre-wear cliff indicators.
*   `mistake`: Sudden drop in pace matching slide or locking telemetry.
*   `conditions`: Anomaly correlates with sharp ambient temperature shifts.
*   `event_driven`: Coincides with VSC, SC, or yellow flags.

---

## 6.6  Compiling and Running the Residual Layer

From the `/transform` directory:

```bash
# Build the residual models
dbt run --profiles-dir profiles --select int_lap_residual_decomposed
```

Confirm that the seven-term identity closure passes validation tests:
```bash
dbt test --profiles-dir profiles --select assert_residual_decomposition_identity
```

---

**Continue to [Part 7  The mart layer and ML handoff](./07_mart_layer.md).**
