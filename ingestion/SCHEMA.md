# Bronze Layer Schema Reference

Complete schema documentation for ingestion output files. **All column names and types are verified
against actual Parquet `DESCRIBE` output**-do not rely on FastF1 documentation or prior versions
of this file, which contained inaccuracies (missing columns, phantom columns, wrong case).

Always re-verify with:
```bash
python3 -c "import duckdb,glob; f=glob.glob('data/bronze/<dataset>/season=*/race=*/*.parquet')[0]; print(duckdb.sql(f\"DESCRIBE SELECT * FROM '{f}'\").df().to_string())"
```

## Directory Structure

Output Parquet files are Hive-partitioned by season and race. All files are compressed with Snappy.

```
data/bronze/
├── laps/
│   └── season=YYYY/
│       └── race=<slug>/
│           ├── YYYY_<slug>_laps.parquet              # Race laps
│           └── session=Q/
│               └── YYYY_<slug>_quali_laps.parquet    # Qualifying laps (if --sessions both)
├── weather/
│   └── season=YYYY/
│       └── race=<slug>/
│           └── weather.parquet
├── race_control/
│   └── season=YYYY/
│       └── race=<slug>/
│           └── race_control.parquet
├── telemetry/
│   └── season=YYYY/
│       └── race=<slug>/
│           └── telemetry.parquet
└── manifests/
    └── manifests.parquet
```

## Column Definitions by Dataset

### Laps

**File:** `bronze/laps/season=YYYY/race=<slug>/YYYY_<slug>_laps.parquet`

**Type:** Fact table. One row per driver per lap. ~20–30k rows per race (20 drivers × 50–70 laps).

**Grain:** `(race_id, season, Driver, LapNumber)`

| Column | Parquet Type | Nullable | Notes |
|--------|-------------|----------|-------|
| Time | BIGINT | Yes | Session elapsed time at lap end (nanoseconds) |
| Driver | VARCHAR | Yes | Three-letter driver code (VER, HAM, …) |
| DriverNumber | VARCHAR | Yes | FIA driver number as string (e.g. "1", "44") |
| LapTime | BIGINT | Yes | Lap duration (nanoseconds). Null for in-progress or invalid laps. Divide by 1e9 for seconds. |
| LapNumber | DOUBLE | Yes | 1-indexed. Includes outlap (lap 0) if present. |
| Stint | DOUBLE | Yes | Stint number (1-indexed) |
| PitOutTime | BIGINT | Yes | Session time at pit lane exit (nanoseconds); null if no pit-out this lap |
| PitInTime | BIGINT | Yes | Session time at pit lane entry (nanoseconds); null if no pit-in this lap |
| Sector1Time | BIGINT | Yes | Sector 1 duration (nanoseconds) |
| Sector2Time | BIGINT | Yes | Sector 2 duration (nanoseconds) |
| Sector3Time | BIGINT | Yes | Sector 3 duration (nanoseconds) |
| Sector1SessionTime | BIGINT | Yes | Session elapsed time at S1 exit (nanoseconds) |
| Sector2SessionTime | BIGINT | Yes | Session elapsed time at S2 exit (nanoseconds) |
| Sector3SessionTime | BIGINT | Yes | Session elapsed time at S3 exit (nanoseconds) |
| SpeedI1 | DOUBLE | Yes | Speed at intermediate 1 trap (kph) |
| SpeedI2 | DOUBLE | Yes | Speed at intermediate 2 trap (kph) |
| SpeedFL | DOUBLE | Yes | Speed at finish line trap (kph) |
| SpeedST | DOUBLE | Yes | Speed at speed trap on main straight (kph) |
| IsPersonalBest | BOOLEAN | Yes | True if this is the driver's personal best for the session |
| Compound | VARCHAR | Yes | SOFT / MEDIUM / HARD / INTERMEDIATE / WET. Null if unknown. |
| TyreLife | DOUBLE | Yes | Consecutive laps completed on current tyre set |
| FreshTyre | BOOLEAN | Yes | True if tyre was new when fitted |
| Team | VARCHAR | Yes | Constructor name |
| LapStartTime | BIGINT | Yes | Session elapsed time at lap start (nanoseconds) |
| LapStartDate | TIMESTAMP_NS | Yes | Wall-clock datetime at lap start |
| TrackStatus | VARCHAR | Yes | Single-digit string: 1=green, 2=yellow, 4=SC, 5=VSC, 6=SC ending, 7=red flag |
| Position | DOUBLE | Yes | Race position at end of lap |
| Deleted | BOOLEAN | Yes | True if the lap time was deleted (track limits, etc.) |
| DeletedReason | VARCHAR | Yes | Reason for deletion (e.g. "Track Limits at Turn X"); null if not deleted |
| FastF1Generated | BOOLEAN | Yes | Internal FastF1 flag for estimated/interpolated laps |
| IsAccurate | BOOLEAN | Yes | True if telemetry coverage is complete for this lap |
| race_id | VARCHAR | Yes | Hive partition-race name slug (e.g. british_grand_prix) |
| season | BIGINT | Yes | Hive partition-calendar year |
| race | VARCHAR | Yes | Race name (redundant with race_id; kept for readability) |

**Notes:**
- `LapNumber` is stored as DOUBLE (not int)-cast as needed.
- `DriverNumber` is VARCHAR, not integer-some drivers have non-numeric numbers historically.
- `LapTime` and all time columns are nanoseconds; divide by `1e9` for seconds.
- `TrackStatus` is a string of digits, not an integer. May contain multi-digit codes (e.g. "245").
- `DeletedReason` is non-null only when `Deleted = true`. Use it to distinguish track-limits
  deletions (skill/discipline signal) from data-quality deletions.

---

### Telemetry

**File:** `bronze/telemetry/season=YYYY/race=<slug>/telemetry.parquet`

**Type:** Event log. One row per ~10 Hz sample per driver per lap. ~2–5 million rows per race;
~90M rows per season. **Always filter by `season` and `race_id`** to avoid full scans.

**Grain:** `(race_id, season, driver_id, lap_number, distance_m)`

| Column | Parquet Type | Nullable | Notes |
|--------|-------------|----------|-------|
| index | BIGINT | Yes | Row index (FastF1 internal; not a stable key) |
| Date | TIMESTAMP_NS | Yes | Wall-clock datetime of the sample |
| SessionTime | BIGINT | Yes | Session elapsed time (nanoseconds) |
| DriverAhead | VARCHAR | Yes | Three-letter code of the car immediately ahead. Null when leading. |
| DistanceToDriverAhead | DOUBLE | Yes | Gap to the car ahead in metres (~95–100% filled) |
| Time | BIGINT | Yes | Lap-relative time (nanoseconds) |
| RPM | DOUBLE | Yes | Engine revolutions per minute |
| speed_kph | DOUBLE | Yes | Speed in km/h |
| nGear | BIGINT | Yes | Current gear (0=neutral, 1–8) |
| throttle_pct | DOUBLE | Yes | Throttle pedal position (0–100%) |
| brake | BOOLEAN | Yes | True if brake pedal is applied |
| DRS | BIGINT | Yes | DRS status enum. **10, 12, 14 = DRS active (flap open)**; other values = inactive. Decode once in staging-do not copy the magic numbers into downstream models. |
| Source | VARCHAR | Yes | FastF1 internal data source tag |
| distance_m | DOUBLE | Yes | Distance from lap start in metres. Resets to 0 each lap. Spa lap distances reach ~7077 m. |
| RelativeDistance | DOUBLE | Yes | Fractional distance around lap (0.0–1.0) |
| Status | VARCHAR | Yes | FastF1 internal status |
| X | DOUBLE | Yes | GPS X coordinate (metres, ~1–2 m precision) |
| Y | DOUBLE | Yes | GPS Y coordinate (metres, ~1–2 m precision) |
| Z | DOUBLE | Yes | GPS Z coordinate. **Unreliable-do not use for elevation work.** |
| driver_id | VARCHAR | Yes | Three-letter driver code (matches `Driver` in laps) |
| lap_number | DOUBLE | Yes | Links to `laps.LapNumber` |
| race_id | VARCHAR | Yes | Hive partition-race name slug |
| season | BIGINT | Yes | Hive partition-calendar year |
| race | VARCHAR | Yes | Race name (redundant with race_id) |

**Columns that do NOT exist (phantom from earlier docs-do not reference):**
- `brake_pct`-no brake pressure channel in FastF1 data
- `drs` (boolean)-the actual column is `DRS` (BIGINT enum; see above)
- `session`-not present in telemetry Parquet; filtering is by `race_id`/`season`

**Notes:**
- Telemetry is sparse: gaps occur during pit stops, SC periods, and for DNF cars.
- The distance upper bound `< 6500` in earlier staging was a bug-Spa reaches **7077 m**.
  The correct cap is `< 8000` or no upper bound (filter `IS NOT NULL` only).
- `int_lap_air_state` must read from `stg_telemetry` only, not directly from this source.

---

### Weather

**File:** `bronze/weather/season=YYYY/race=<slug>/weather.parquet`

**Type:** Dimension. One row per sample (approximately 1 per minute during the session).
~150–300 rows per race day.

**Grain:** `(race_id, season, session_time_s)`

| Column | Parquet Type | Nullable | Notes |
|--------|-------------|----------|-------|
| index | BIGINT | Yes | Row index |
| Time | BIGINT | Yes | Session elapsed time (nanoseconds) |
| ambient_temp_c | DOUBLE | Yes | Ambient air temperature (°C) |
| humidity_pct | DOUBLE | Yes | Relative humidity (0–100%) |
| pressure_hpa | DOUBLE | Yes | Atmospheric pressure (hectopascals). ~875 hPa at Mexico City (2240 m altitude) vs ~1013 hPa at sea level. Air density ∝ pressure-relevant cross-venue covariate for aero and PU performance. |
| rainfall_flag | BOOLEAN | Yes | True if precipitation detected. **There is no cumulative rainfall_mm column**-rain is a flag only. |
| track_temp_c | DOUBLE | Yes | Track surface temperature (°C). Typically 10–20°C above ambient in direct sun. |
| wind_direction | BIGINT | Yes | Wind direction in degrees (0–360). Meteorological convention: direction *from* which wind blows. |
| wind_speed_ms | DOUBLE | Yes | Wind speed in metres per second |
| race_id | VARCHAR | Yes | Hive partition-race name slug |
| season | BIGINT | Yes | Hive partition-calendar year |
| session_time_s | DOUBLE | Yes | Session elapsed time (seconds)-used for joining to laps |
| race | VARCHAR | Yes | Race name (redundant with race_id) |

**Columns that do NOT exist (phantom from earlier docs):**
- `rainfall_mm`-rain is boolean only; no cumulative mm channel
- `wind_direction_deg`-column is `wind_direction` (BIGINT)
- `wind_speed_kmh`-column is `wind_speed_ms` (metres per second, not km/h)
- `track_status`-not in weather data

---

### Race Control

**File:** `bronze/race_control/season=YYYY/race=<slug>/race_control.parquet`

**Type:** Event log. One row per race-control message. ~50–200 rows per race (~100 average).
148 season-race partitions in the 2018–2024 dataset.

**Grain:** `(race_id, season, index)`

| Column | Parquet Type | Nullable | Notes |
|--------|-------------|----------|-------|
| index | BIGINT | Yes | Row index (FastF1 internal) |
| Time | TIMESTAMP_NS | Yes | Message timestamp (session clock) |
| category | VARCHAR | Yes | Message category: `Flag` \| `SafetyCar` \| `CarEvent` \| `Drs` \| `Other` \| … |
| message | VARCHAR | Yes | Free-text message. Highly regular-safe for regex. See examples below. |
| Status | VARCHAR | Yes | Additional status (infrequently populated) |
| Flag | VARCHAR | Yes | Flag colour: `GREEN` \| `YELLOW` \| `DOUBLE YELLOW` \| `RED` \| `CLEAR` \| `CHEQUERED` \| `BLUE` |
| Scope | VARCHAR | Yes | Flag scope: `Track` \| `Sector` \| `Driver` |
| Sector | DOUBLE | Yes | Marshalling sector number for sector-scoped flags; null for track-wide events |
| RacingNumber | VARCHAR | Yes | Car number the message refers to (for CarEvent/penalty messages) |
| Lap | BIGINT | Yes | Lap number when the message was issued; null for pre-race messages |
| race_id | VARCHAR | Yes | Hive partition-race name slug |
| season | BIGINT | Yes | Hive partition-calendar year |
| session_time_s | TIMESTAMP_NS | Yes | Session elapsed time. **Null/unreliable for 2024** (FastF1 v3.8.3 API regression). Use `Lap` for joins. |
| race | VARCHAR | Yes | Race name (redundant with race_id) |

**Columns that do NOT exist (phantom from earlier docs):**
- `lap` (lowercase)-column is `Lap` (Title-Case, BIGINT)
- `time` (lowercase)-column is `Time` (Title-Case, TIMESTAMP_NS)
- `flag` (lowercase)-column is `Flag` (Title-Case, VARCHAR)
- `code`-does not exist in any partition; was never ingested

**Common `message` values (verified, regex-parseable):**
```
SAFETY CAR DEPLOYED
SAFETY CAR IN THIS LAP          ← SC ending signal
SAFETY CAR WILL ENTER PITS      ← alternate ending phrasing
VIRTUAL SAFETY CAR DEPLOYED
VIRTUAL SAFETY CAR ENDING
RED FLAG
DRS ENABLED
DRS DISABLED
CAR 33 (VER) STOPPED AT TURN 9
INCIDENT INVOLVING CARS 33 (VER) AND 44 (HAM) ... UNDER INVESTIGATION
TIME PENALTY ... CAR 16 (LEC)
```

**Known issues:**
- `session_time_s` is null for all 2024 races (FastF1 v3.8.3 regression). Join to laps via `Lap`.
- Some messages have null `Lap` (pre-race briefings, formation-lap events)-retain these rows;
  downstream models must filter `WHERE lap_number IS NOT NULL` as needed.
- `RacingNumber` is the *car number* (string), not the driver code.

---

## File Sizes & Row Counts (2024 Season Baseline)

| Dataset | Rows (2024) | File size (2024) | Rows (2018–2024) |
|---------|------------|-----------------|-----------------|
| Laps (race) | ~27k | ~2 MB | ~160k |
| Telemetry | ~90M | ~2.5 GB | ~550M |
| Weather | ~7k | ~100 KB | ~40k |
| Race Control | ~2.3k | ~200 KB | ~14k |

---

## Partition Pruning

All datasets are partitioned by `season` and `race`. Always include both in WHERE clauses:

```sql
-- Good: partition-pruned
SELECT * FROM read_parquet('data/bronze/telemetry/season=2024/race=bahrain_grand_prix/*.parquet')

-- Bad: full scan across ~550M telemetry rows
SELECT * FROM read_parquet('data/bronze/telemetry/*/*/*.parquet')
WHERE race_id = 'bahrain_grand_prix'
```

---

## Version History

- **v1.0** (May 2024)-Initial Bronze schema for 2018–2024
- **v1.1** (May 2024)-Added `session` column to laps and telemetry
- **v1.2** (May 2026)-Full accuracy audit against real Parquet DESCRIBE output:
 -Corrected race_control column names to Title-Case; removed phantom `code` column
 -Added telemetry columns: RPM, nGear, DRS (integer enum), DistanceToDriverAhead, DriverAhead,
    RelativeDistance, X, Y, Z, SessionTime; removed phantom `brake_pct` and boolean `drs`
 -Corrected weather columns: removed phantom `rainfall_mm`, `wind_direction_deg`, `wind_speed_kmh`;
    added `pressure_hpa`; documented `rainfall_flag` as boolean-only
 -Added `DeletedReason`, `LapStartDate`, `LapStartTime`, `Team`, `Position` to laps
 -Documented Spa distance bug (7077 m exceeds previous 6500 m clip in stg_telemetry)
 -Registered race_control as a dbt source (was previously unconsumed by any model)
