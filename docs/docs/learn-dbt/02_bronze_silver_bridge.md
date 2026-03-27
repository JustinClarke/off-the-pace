---
sidebar_position: 3
title: "Part 2: Staging & Sources"
---

# Part 2: The Bronze→Silver bridge: sources and staging

The staging layer is where raw, untyped Hive-partitioned Bronze data is structured into clean, typed, and schema-enforced relational views. Staging models are virtualized as views (`materialized = 'view'`), adding zero storage overhead while ensuring upstream sensor changes are cleanly normalized before intermediate calculations.

---

## 2.1  Model Overview

The staging layer comprises **9 active staging models** normalizing inputs across weather telemetry, pit events, laps, and race control variables:

| Staging Model | Source Table | Key Transformations |
|---|---|---|
| `stg_laps` | `raw_laps` | Casts types, scales time, parses safety car flags (Race session). |
| `stg_laps_qualifying` | `raw_laps_qualifying` | Casts and isolates qualifying telemetry (Qualifying session). |
| `stg_weather` | `raw_weather` | Casts ambient metrics, track temp, wind dynamics. |
| `stg_telemetry` | `raw_telemetry` | Standardizes distance offsets, speed, and throttle variables. |
| `stg_sector_times` | `stg_laps` | Unpivots sector columns into a sector-grain table. |
| `stg_pits` | `raw_pit_data` | Normalizes tyre swaps and pit duration intervals. |
| `stg_events` | `raw_dim_events` (seed) | Cleans incident descriptors and flag boundaries. |
| `stg_tyre_allocations` | `tyre_allocations` (seed)| Placeholder stub for future pre-race allocations. |

---

## 2.2  `stg_laps` & `stg_laps_qualifying`   The Core Data Feeds

These models normalize lap metadata. The raw FastF1 data stores timing in nanoseconds and columns in PascalCase (e.g. `LapTime`, `DriverNumber`). Staging renames columns to `snake_case`, scales nanoseconds to seconds, and defines clear booleans.

### Staging Timing Transformations
```sql
-- Nanoseconds to seconds cast
CASE 
    WHEN LapTime IS NOT NULL THEN CAST(LapTime AS DOUBLE) / 1e9 
    ELSE NULL 
END AS lap_time_s
```

### Regular Expression Track Status Parsing
In the raw Bronze schema, `TrackStatus` is a concatenated string of digits representing track status codes that occurred during the lap (e.g., `"14"` represents Clear and Safety Car; `"125"` represents Clear, Yellow, and VSC). 

To ensure safety car and VSC laps are captured without losing laps with compound statuses, staging implements regex checks using the DuckDB `REGEXP_MATCHES` engine rather than slow substring scanning:

```sql
-- Identify safety car flags (4 = Safety Car, 6 = SC Ending, 7 = Red Flag)
REGEXP_MATCHES(track_status, '.*[467].*') AS is_safety_car_lap,

-- Identify virtual safety car flags (5 = VSC)
REGEXP_MATCHES(track_status, '.*5.*')     AS is_vsc_lap
```

---

## 2.3  `stg_weather`   ASOF Join Preparation

Weather metrics (ambient temperature, track temperature, humidity) are sampled asynchronously at approximately $1\text{ Hz}$ in `raw_weather`. Staging renames and cleans these parameters. 

Importantly, weather variables are **not joined to laps in the staging layer**. Because laps take between $80\text{ s}$ and $120\text{ s}$ while weather is sampled at $1\text{ Hz}$, traditional joins would miss rows. Instead, these are joined downstream in the intermediate layers using an **ASOF join** on `session_time_s`, selecting the closest preceding weather timestamp for each lap.

---

## 2.4  `stg_telemetry`   High-Density 10ms Telemetry

Telemetry is sampled at high frequencies (~10ms grain). Key fields include speed, pedal inputs (throttle, brake), and `DistanceToDriverAhead` (distance to the leading car in meters, updated in real time).

Downstream intermediates consume this high-density stream:
*   `int_lap_air_state` checks distance intervals throughout the lap to measure dirty-air taxation.
*   `fct_telemetry_deltas` provides sub-lap sector analytics.

---

## 2.5  `stg_sector_times`   Unpivoting Sector Metrics

Raw lap data contains three separate columns: `Sector1Time`, `Sector2Time`, `Sector3Time`. To facilitate clean sector-grain aggregations without nested SQL logic, staging unpivots these columns into a long format (one row per sector number per lap) using a union pattern:

```sql
SELECT lap_id, 1 AS sector_number, sector1_time_s AS sector_time_s FROM {{ ref('stg_laps') }}
UNION ALL
SELECT lap_id, 2 AS sector_number, sector2_time_s FROM {{ ref('stg_laps') }}
UNION ALL
SELECT lap_id, 3 AS sector_number, sector3_time_s FROM {{ ref('stg_laps') }}
```

---

## 2.6  Executing and Verifying the Staging Layer

To execute and validate staging transformations, run the following commands from the `transform/` root directory:

```bash
# Compile and build the staging models
dbt run --profiles-dir profiles --select staging.*

# Run schema validation and constraint tests
dbt test --profiles-dir profiles --select staging.*
```

Verify that all staging views compiled correctly and all schema assertions (`not_null`, `unique`, and `accepted_values`) pass. 

### Database Validation Query
You can run a validation query against your local warehouse to confirm the count of distinct races staging has structured:

```sql
-- Run inside Harlequin (make query)
SELECT COUNT(DISTINCT race_id) FROM stg_laps;
```
Expected output: **168** distinct race IDs, covering all ingested 2018–2024 sessions.

---

**Continue to [Part 3  Reference data](./03_reference_data.md).**
