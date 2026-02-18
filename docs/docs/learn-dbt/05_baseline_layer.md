---
sidebar_position: 6
title: "Part 5: Baseline Layer"
---

# Part 5: The baseline layer

The baseline layer applies statistical modeling to establish what "normal" performance looks like. By defining baseline profiles for track grip, tyre degradation, vehicle performance, and driver-track affinities, we build a multi-component reference model. Any deviation from these baselines represents the isolated driver skill residual.

---

## 5.1  `int_field_pace_curve`   Trimmed Mean Field Pace

To calculate driver-relative advantages, we must establish a reference pace for each lap of a race. 

We utilize a **trimmed mean** rather than a simple average or median:
1.  **Exclude anomalous laps:** The filter excludes out-laps, in-laps, safety car periods (`is_safety_car_lap = TRUE`), virtual safety cars (`is_vsc_lap = TRUE`), and rain laps.
2.  **Trim outliers:** At each lap number, we discard the fastest $10\%$ (extreme fuel-burn qualification laps) and slowest $10\%$ (spin recoveries, damage) of active drivers before averaging the remaining records.
3.  **Smooth:** Apply a $5$-lap centered rolling average to eliminate transient lap-to-lap timing noise.

This ensures our baseline represents the typical, clean competitive pace of the field on that lap.

---

## 5.2  `int_track_evolution`   Rubber and Weather Components

Track grip evolves during a race. `int_track_evolution` separates this progression into two components:
1.  **Track Rubbering-In:** Rubber deposits from tyres increase grip, monotonically reducing lap times. This is modeled using Ordinary Least Squares (OLS) with a monotone constraint: grip cannot decrease as laps accumulate.
2.  **Thermal Weather Component:** Weather variation alters grip. This is modeled by joining weather telemetry (`stg_weather`) via an `ASOF` join on `session_time_s` to correlate air and track temperatures with pace deltas.

---

## 5.3  `int_compound_cliff_predicted`   Tyre Degradation Profiles

Tyres lose grip as they age, following a non-linear "hockey-stick" degradation curve. `int_compound_cliff_predicted` imports KM survival parameters from `dim_compounds_season` to predict tyre pace decay:

$$\text{Expected Degradation}(\text{age}) = \beta_0 + \beta_1 \cdot \text{age} + \beta_2 \cdot \text{age}^2 + \beta_3 \cdot \max(0,\, \text{age} \tau) + \delta_T \cdot \Delta T_{\text{track}}$$

Where:
*   $\beta_0$: Base compound grip at zero age.
*   $\beta_1$: Linear wear coefficient (s/lap).
*   $\beta_2$: Quadratic wear coefficient (capturing exponential wear curves).
*   $\tau$: Cliff onset lap, estimated via Kaplan-Meier survival analysis.
*   $\beta_3$: Accelerated post-cliff wear gradient.
*   $\delta_T$: Track temperature sensitivity coefficient ($0.005\text{ s/°C}$).

The linear post-cliff penalty prevents quadratic terms from projecting physically impossible degradation values (e.g. hundreds of seconds) during long stints.

---

## 5.4  `int_constructor_structural_pace`   Isolated Vehicle Speed

To ensure driver skill metrics represent the driver rather than the machinery, we must isolate the car's structural performance. 

`int_constructor_structural_pace` implements a panel fixed-effects model to calculate relative constructor pace advantages, decoupled from the influence of their drivers. This is split into two independent performance components:
1.  **Power Index:** Long-straight performance (measured in S1 and S3 where engine horsepower dominates).
2.  **Aero Index:** Twisty, corner-heavy performance (measured in S2 where aerodynamic downforce dominates).

By evaluating Power and Aero independently, the model adjusts for tracks with asymmetric layouts (e.g. Monza is power-heavy, Hungary is aero-heavy).

---

## 5.5  `int_driver_circuit_affinity` & Bayesian Shrinkage

When sample sizes are small (e.g., a driver has only completed a few laps at a new track), their observed pace advantage is highly volatile. To prevent data sparsity from introducing extreme outliers, we apply **Bayesian Shrinkage** using the `bayesian_shrinkage` and `posterior_variance` macros.

### The Conjugate Normal-Normal Model
We assume a normal prior centered at $0$ (the field median). The shrunken posterior parameter is calculated as:
$$\mu_{\text{posterior}} = \frac{n \bar{x} + \tau \mu_0}{n + \tau}$$

Where:
*   $\bar{x}$: The observed pace advantage (empirical average).
*   $n$: The number of observations (laps completed).
*   $\mu_0$: The prior mean ($0$, meaning no inherent track advantage).
*   $\tau$: The prior weight, set to $15$ equivalent laps of data.

```
                  Small Sample (n = 2) ────────► Posterior pulled heavily to 0 (Prior)
                  Large Sample (n = 300) ──────► Posterior matches actual mean (x)
```

The posterior variance, which tracks rating uncertainty, is calculated using precision weights:
$$\sigma^2_{\text{posterior}} = \frac{1}{\frac{n}{\sigma^2} + \frac{1}{\sigma^2_0}}$$

### Macro Implementation
The `bayesian_shrinkage` macro applies this conjugate calculation seamlessly inside `int_driver_circuit_affinity.sql` and `int_driver_season_ratings.sql`:

```sql
SELECT
    driver_id,
    circuit_key,
    lap_count,
    observed_pace_advantage_s,
    -- Shrink towards a zero-centered prior with a weight of 15 laps
    {{ bayesian_shrinkage('lap_count', 'observed_pace_advantage_s', '0', '15') }} AS shrunken_affinity_s
FROM driver_track_records
```

This math guarantees that drivers are only credited with circuit-specific strengths after compiling a statistically significant database of clean laps.

---

## 5.6  Running the Baselines Layer

From the `/transform` root:

```bash
# Build the baseline models
dbt run --profiles-dir profiles --select tag:intermediate
```

Verify that all mathematical baseline metrics compile and run clean.

---

**Continue to [Part 6  The residual layer](./06_residual_layer.md).**
