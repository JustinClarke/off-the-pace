---
sidebar_position: 5
title: "Part 4: Physics Layer"
---

# Part 4: The physics layer

The intermediate physics layer calculates the deterministic, physical forces that explain lap-time variation. By subtracting calculable physics (fuel mass, aerodynamic wake, tyre wear, and thermal loads) from raw lap times, we isolate the underlying driver performance signal.

---

## 4.1  `int_stint_geometry`   Stint Tracking

A **stint** is defined as the sequence of laps completed by a driver on a single set of tyres between pit events. `int_stint_geometry` maps every lap to its corresponding stint ID (`stint_id`), tyre age (`tyre_life`), and stint counter (`lap_in_stint`).

### Stint Window Calculation
```sql
ROW_NUMBER() OVER (
    PARTITION BY driver_id, race_id, stint_number
    ORDER BY lap_number
) AS lap_in_stint
```

*   `age_in_stint` is $0$-indexed (the lap the tyre set is first mounted, including pit-out).
*   `lap_in_stint` is $1$-indexed (the first full racing lap completed on the set).

---

## 4.2  `int_lap_fuel_state` & `int_lap_fuel_state_qualifying`   Weight Corrections

F1 cars burn fuel throughout a session, getting lighter and faster. To compare paces across different phases of a session, we must compute the "empty-tank equivalent" lap time by subtracting the fuel weight penalty.

### Race Fuel Mass Correction
At race start, cars carry up to $110\text{ kg}$ of fuel. Fuel mass is calculated as:
$$\text{fuel\_mass\_kg}_t = (\text{total\_laps} t + 1) \cdot \text{fuel\_consumption\_rate}$$

### Weight Penalty Subtraction
The weight penalty is a linear function of fuel mass and the circuit-specific penalty factor $w_{\text{circuit}}$ (seconds per kg):
$$\text{weight\_penalty\_s}_t = \text{fuel\_mass\_kg}_t \cdot w_{\text{circuit}}$$
$$\text{weight\_corrected\_lap\_time\_s}_t = \text{lap\_time\_s}_t \text{weight\_penalty\_s}_t$$

### Qualifying Fuel State (`int_lap_fuel_state_qualifying`)
Qualifying runs feature light fuel loads and different burn-off kinetics. The qualifying fuel state model implements a specialized low-mass decay correction:
*   Fuel mass starts at the session load limit.
*   Burn-off is adjusted based on out-lap and hot-lap consumption parameters.

---

## 4.3  `int_lap_air_state` & `int_dirty_air_tax_component`   Aerodynamic Wake

When a car closely follows another, it enters turbulent "dirty air," losing downforce and sliding more, which overheats the tyres. Conversely, DRS (Drag Reduction System) reduces drag on straights, boosting speed.

### Air State Classifications
Using $10\text{ ms}$ high-frequency telemetry via `DistanceToDriverAhead`, laps are classified into four spatial states:

| Air State | Distance Interval | Aerodynamic Effect |
|---|---|---|
| `free_air` | $> 3.0\text{ m}$ | Normal downforce, no aerodynamic wake. |
| `tow_zone` | $1.0\text{ m} \le d \le 3.0\text{ m}$ | Aerodynamic slipstream advantage, neutral downforce. |
| `drs_zone` | $< 1.0\text{ m}$ (DRS active) | DRS wing flap open, significantly reduced drag. |
| `dirty_air` | $< 1.0\text{ m}$ (no DRS) | Severe downforce loss, tyre sliding, and thermal loading. |

### Dirty Air Tax Component
`int_dirty_air_tax_component` calculates the causal lap-time penalty (in seconds) incurred due to trailing in another car's wake. It measures `dirty_air_share` (the percentage of the lap spent in the `< 1s` gap zone) to determine the exact pace taxation.

---

## 4.4  `int_lap_thermal_proxy` & `int_tyre_surface_vs_bulk_decoupling`   Tyre Thermal State

We do not have real-time tyre temperature sensors in public FastF1 streams. Instead, we approximate thermal stress. 

Any lap run faster than a driver's stint median baseline represents "pushing," which transfers kinetic energy into the tyres. We accumulate this thermal stress over a rolling window using an **Exponentially Weighted Moving Average (EWMA)** with a decay factor $\tau = 3\text{ laps}$.

### Thermal Load Model
Let the push residual at lap $k$ be $P_k$ (pace delta vs. baseline). The accumulated thermal load at lap $t$ is:
$$\text{Thermal Load}_t = \sum_{k=0}^{t} P_k \cdot e^{-\frac{t-k}{\tau}}$$

The geometric decay ensures recent pushing efforts impact the current tyre temperature state far more than actions completed earlier in the stint. 

### Decoupling Surface vs. Bulk Temperatures (`int_tyre_surface_vs_bulk_decoupling`)
Tyres exhibit dual thermal layers:
1.  **Surface Temperature:** Highly volatile, heats rapidly during heavy traction/slides, cools quickly on straights.
2.  **Bulk Carcass Temperature:** Slow thermal inertia, builds steadily over the stint, dictates structural degradation.

The model splits the proxy thermal load into fast-decay surface states and slow-accumulation carcass states to track structural tyres degradation.

---

## 4.5  `int_corner_metrics`   Apex Geometries

This model processes high-frequency telemetry joined with the `dim_corners_reference` seed. For every corner, it isolates three physical properties:
*   `v_min`: Minimum speed through the corner apex (kph).
*   `braking_point_m`: The exact distance offset where braking was initiated.
*   `throttle_point_m`: The exact distance offset where the driver returned to full throttle.

These metrics allow for corner-by-corner analysis of driver technique and vehicle traction.

---

## 4.6  Running the Intermediate Physics Layer

To compile the intermediate models, run the following command from the `/transform` root:

```bash
# Build intermediate physics views
dbt run --profiles-dir profiles --select tag:intermediate

# Run intermediate unit validation tests to ensure that stint bounds and mathematical transformations do not leak variables across session splits:
dbt test --profiles-dir profiles --select tag:intermediate
```

---

**Continue to [Part 5  The baseline layer](./05_baseline_layer.md).**
