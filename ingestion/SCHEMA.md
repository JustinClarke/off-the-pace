# Bronze Layer Schema Reference

Complete schema documentation for ingestion output files. **All column names and types are verified
against actual Parquet `DESCRIBE` output**-do not rely on FastF1 documentation or prior versions
of this file, which contained inaccuracies (missing columns, phantom columns, wrong case).

Always re-verify with:
```bash
python3.14 -c "import duckdb,glob; f=glob.glob('data/bronze/<dataset>/season=*/race=*/*.parquet')[0]; print(duckdb.sql(f\"DESCRIBE SELECT * FROM '{f}'\").df().to_string())"
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
│           ├── race_control.parquet
│           └── session=Q/race_control.parquet        # Qualifying (session_type = 'Q')
├── session_info/
│   └── season=YYYY/
│       └── race=<slug>/
│           ├── session_info.parquet                  # One row: FastF1 Session.session_info + scalars
│           └── session=Q/session_info.parquet
├── circuit_info/                                     # Corners only (read by stg_circuit_info)
│   └── season=YYYY/race=<slug>/[session=Q/]circuit_info.parquet
├── circuit_markers/                                  # Corners + marshal lights + marshal sectors + rotation
│   └── season=YYYY/race=<slug>/[session=Q/]circuit_markers.parquet
├── telemetry/
│   └── season=YYYY/
│       └── race=<slug>/
│           └── telemetry.parquet
└── manifests/
    └── run_<run_id>.parquet                          # One file per ingestion run
```

Manifests are append-only: each ingestion run writes a single
`run_<run_id>.parquet` (where `run_id` is the run's UTC timestamp, e.g.
`run_20260612T080731Z.parquet`), never a rolling `manifests.parquet`. Read them
back with `make manifest-report` (run status + schema-drift across all runs).

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
| TrackStatus | VARCHAR | Yes | Single-digit string: 1=green, 2=yellow, 4=SC, 5=red flag, 6=VSC deployed, 7=VSC ending (per `stg_laps.sql:121-126`) |
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
| session_time_s | TIMESTAMP_NS | Yes | **Time of day in seconds (UTC), not time since session start.** Filled for 2024. For time since session start use `session_time_corrected_s`. |
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

**Qualifying:** `race_control/season=YYYY/race=<slug>/session=Q/race_control.parquet`, same
columns plus `session_type` = `'Q'` and `session_time_corrected_s` (seconds from `t0_date`). It
sits one level below the race file, so the race glob `race_control/*/*/*.parquet` does not read it.
`Lap` is usually all-null in qualifying (stored as a null-typed column). Written from the change
that added it on; older sessions are filled by `ingest.py --fill-missing`.

**Known issues:**
- `session_time_s` is time of day in seconds (UTC), not time since session start; do not join it to lap or telemetry clocks. It is filled for 2024. Use `session_time_corrected_s` (seconds since session start, on the laps/telemetry SessionTime clock); it is filled everywhere except 69 rows in 2018 Bahrain R. Joining via `Lap` also works.
- Some messages have null `Lap` (pre-race briefings, formation-lap events)-retain these rows;
  downstream models must filter `WHERE lap_number IS NOT NULL` as needed.
- `RacingNumber` is the *car number* (string), not the driver code.

---

### Session Info

**File:** `bronze/session_info/season=YYYY/race=<slug>/[session=Q/]session_info.parquet`

**Type:** One row per session. FastF1 `Session.session_info` (the livetiming `SessionInfo`
endpoint) flattened with `_` as the separator, plus scalars FastF1 derives at load.

| Column | Notes |
|--------|-------|
| Key, Type, Name, Path | Livetiming session key, type and name, archive path |
| StartDate, EndDate | Local (track) start and end, naive datetime |
| GmtOffset | Track offset from UTC (duration) |
| Meeting_Key, Meeting_Name, Meeting_Location, Meeting_Country_Key/Code/Name | Meeting ids and names |
| Meeting_Circuit_Key, Meeting_Circuit_ShortName | Circuit key (the one FastF1 uses for circuit info) |
| ArchiveStatus_Status | Archive status at fetch time |
| total_laps | Scheduled race distance in laps (`Int64`, null for qualifying) |
| session_start_time_s | `Session.session_start_time` in seconds on the SessionTime clock |
| t0_date | `Session.t0_date`: UTC at SessionTime 0 (null without telemetry) |
| session_date_utc | `Session.date` (scheduled start, UTC) |
| api_path, f1_api_support | FastF1 API path and whether the F1 live-timing API covers the session |
| race_id, season, session_type | `YYYY_R`, year, `R` or `Q` |

Extra keys FastF1 adds in later seasons (e.g. `Meeting_OfficialName`, `Meeting_Number`) appear as
extra columns; read with `union_by_name=true`.

---

### Circuit Markers

**File:** `bronze/circuit_markers/season=YYYY/race=<slug>/[session=Q/]circuit_markers.parquet`

**Type:** One row per track marker from FastF1 `CircuitInfo`: `X, Y, Number, Letter, Angle,
Distance` (Distance fitted to that session's fastest lap), plus `marker_type` (`corner` \|
`marshal_light` \| `marshal_sector`), `rotation_deg` (track-map rotation), `race_id`, `season`
and, for qualifying, `session_type`. A separate dataset rather than extra files in
`circuit_info/`, because `stg_circuit_info` reads `circuit_info/*/*/*.parquet` with
`union_by_name` and would union them into the corners. `circuit_info/` keeps the race corners
file unchanged and gains `session=Q/circuit_info.parquet` for qualifying.

---

### Manifests

**File:** `bronze/manifests/run_<run_id>.parquet`

**Type:** Audit log. One row per (season, round, session) attempted in a run.

**Grain:** `(run_id, season, round_number, session_type)`

| Column | Type | Notes |
|--------|------|-------|
| run_id | VARCHAR | UTC timestamp of the run (e.g. `20260612T080731Z`) |
| ingested_at_utc | VARCHAR | ISO-8601 timestamp the row was written |
| season | BIGINT | Calendar year |
| round_number | BIGINT | Round within the season |
| race_slug | VARCHAR | Event name slug (e.g. `bahrain_grand_prix`) |
| session_type | VARCHAR | `R` or `Q` |
| status | VARCHAR | `ok` \| `skip` \| `error` \| `thin` |
| row_count | BIGINT | Laps written (0 for skip/error) |
| dq_passed | BOOLEAN | True if data-quality schema check passed |
| duplicate_lap_keys | BIGINT | Count of duplicate lap keys detected |
| schema_fingerprint | VARCHAR | SHA-1 (first 12 chars) of sorted column names; blank for skip/error. Used to detect FastF1 schema drift between runs. |
| reason | VARCHAR | Why a session was not written: `rate_limited` (FastF1 500 calls/h outlasted the run's wait budget), `source_empty` (FastF1 returned an empty or partial session), `error` (anything else). Blank for ok/skip. Absent in older files. |
| attempts | BIGINT | Loader calls made for the session (0 for skip). Absent in older files. |
| rate_limit_waits | BIGINT | Rate-limit waits spent on the session (each `RATE_LIMIT_WAIT_S`, 3600 s; a run stops after `MAX_RATE_LIMIT_WAITS` = 24). Absent in older files. |
| rate_limit_wait_s | DOUBLE | Seconds spent in those waits. Absent in older files. |
| telemetry_full_status | VARCHAR | Only with `--telemetry-full`: `ok` \| `empty` (car_data/pos_data missing or no samples) \| `error` (a driver write failed or the channel was unreadable); the worse of the two channels. Blank when not requested. A non-ok value is also logged at ERROR; the session itself still counts as ok. Absent in older files. |
| telemetry_full_note | VARCHAR | Reason and drivers written per channel, e.g. `car_data: 20 drivers; pos_data: no samples`. Absent in older files. |
| circuit_info_status | VARCHAR | `ok: N corners` \| `none` \| `failed: ...`, with `; markers failed: ...` appended if only the markers file failed. Race only in older files; R and Q now. |
| session_info_status | VARCHAR | `ok` \| `none` (no SessionInfo loaded) \| `failed: ...`; blank when not attempted. Absent in older files. |
| fill_note | VARCHAR | `--fill-missing` on a session already on disk: `filled: <datasets>` and `source has none: <datasets>`; `fill failed for ...` on an `error` row. The row's status is `skip` (laps untouched). Blank otherwise. Absent in older files. |

`make manifest-report` reads every `run_*.parquet`, reports the latest status per
session, and flags any `schema_fingerprint` change over time as schema drift.

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
