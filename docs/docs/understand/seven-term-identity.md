---
sidebar_position: 2
title: The Seven-Term Identity
---

# The Seven-Term Identity

The additive decomposition at the core of the model, and why it is enforced as a CI test.

For column definitions and the test contract, see [`int_lap_residual_decomposed`](/reference/models/int/int_lap_residual_decomposed) and [`fct_lap_residuals`](/reference/models/fct/fct_lap_residuals).

---

Every lap has an equation. This is it:

$$\text{pace\_delta} = \text{fuel} + \text{compound} + \text{rubber} + \text{ambient} + \text{constructor} + \text{dirty\_air} + \text{driver\_skill}$$

Six measurable physics terms plus one closure term (driver skill) defined as whatever remains after everything else is subtracted. This is not an approximation. It is an exact identity enforced to within 0.1 ms floating-point tolerance on every lap in every race. If it fails, the CI build fails.

## What pace_delta is

The identity uses deviation from a field baseline, not raw lap time:

$$\text{pace\_delta} = \text{lap\_time} \text{base\_track\_pace}$$

`base_track_pace_s` is the trimmed-mean field pace smoothed over a 5-lap centred window. The fastest and slowest 10% of cars at each lap are excluded before computing the median to remove cars on extreme strategies or with mechanical issues. A driver at exactly the field median pace has `pace_delta ≈ 0`. Positive = slower than field. Negative = faster.

Normalising against the field removes the circuit characteristic (Monza is 80 s, Singapore is 100 s) so that a driver residual of −0.4 s at Monza means the same as −0.4 s at Singapore: 400 ms faster than the field median, net of all physics.

## The six physics terms

### 1. Fuel component

$$\text{fuel} = w \cdot m_{\text{fuel}}$$

$m_{\text{fuel}}$ is estimated fuel mass at lap $t$ (kg). $w$ is the weight penalty (s/kg) calibrated per circuit:

$$w \approx 0.02 + 0.0002 \times \text{corner\_count} \times \text{avg\_lateral\_g}$$

At Monaco (tight, high corner count): ~0.025 s/kg. At Monza (few corners, high speed): ~0.018 s/kg. At Suzuka (high downforce, high lateral G): ~0.035 s/kg.

The fuel term is positive and decreasing. A driver on lap 3 of a 55-lap race is ~0.8–1.0 s slower than their end-of-race pace purely from fuel mass.

### 2. Compound component (tyre degradation)

$$\text{compound}(\text{age}) = \beta_0 + \beta_1 \cdot \text{age} + \beta_2 \cdot \text{age}^2 + \beta_3 \cdot \max(0,\, \text{age} \tau) + \delta_T \cdot \text{temp\_delta}$$

The hockey-stick polynomial captures the tyre wear trajectory. $\tau$ is the cliff onset lap estimated via Kaplan-Meier survival analysis (see [Methodology](./methodology.md)). $\beta_3$ is the post-cliff degradation acceleration. $\delta_T \approx 0.005$ s/°C captures temperature sensitivity.

All coefficients and $\tau$ are stored per `(circuit, compound, season)` in `dim_compounds_season`. Pre-computed from 2018–2024; not refitted on 2025 data.

For a Soft compound at a high-wear circuit, the full trajectory from new tyres to cliff can span 1.5–2.5 s of pace loss.

### 3. Rubber component (track evolution)

$$\text{rubber}(t) = \gamma_r \cdot R(t)$$

$R(t)$ is the race-level rubber accumulation index, a smoothed measure of grip improvement as rubber builds on the racing line. Typically negative (improving pace). Grows in magnitude through the first 30–40 laps, then plateaus. Identified from the residual of the field pace curve after removing fuel and compound contributions.

### 4. Ambient component (weather)

$$\text{ambient}(t) = \gamma_a \cdot \Delta T(t)$$

$\Delta T$ is track temperature deviation from the session's thermal baseline. Higher temperatures reduce tyre grip, especially for Soft compounds near their thermal ceiling. Identified jointly with the rubber component using the fact that rubber accumulation is monotonically increasing while temperature can move either direction.

### 5. Constructor component

The constructor's structural pace relative to the field median, estimated from a panel fixed-effects regression on race-year-constructor combinations. Pre-computed from 2018–2024. This removes the car quality signal so the driver residual reflects execution, not machinery.

### 6. Dirty air component (traffic)

$$\text{dirty\_air} = \theta \cdot \text{dirty\_air\_share}(t)$$

`dirty_air_share` measures the proportion of the lap run in aerodynamic wake. $\theta$ (seconds per unit share) is calibrated from the partial residual panel after removing fuel, compound, rubber, ambient, and constructor. See [`int_dirty_air_tax_component`](/reference/models/int/int_dirty_air_tax_component).

### 7. Driver skill residual (closure)

$$\text{driver\_skill} = \text{pace\_delta} \sum_{\text{terms 1-6}}$$

Defined as the closure. Not estimated independently, but derived. This is intentional: it ensures the identity holds exactly and prevents the residual from absorbing model error. A large negative driver residual means the driver is running faster than the physics predicts. A large positive residual means the opposite.

## Why enforce it in CI

A stated invariant is documentation. An enforced invariant is a contract.

```sql
-- transform/macros/assert_additive_identity.sql
select count(*) from {{ model }}
where abs(pace_delta_s-(
  fuel_component_s + compound_component_s + rubber_component_s +
  ambient_component_s + constructor_component_s + dirty_air_component_s +
  driver_skill_residual_s
)) > 0.0001
```

If this query returns any rows, the dbt test fails and CI blocks the merge. Every model change must maintain the invariant or explicitly update the test contract. This is the most important engineering property in the project.
