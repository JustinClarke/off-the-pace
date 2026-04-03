# `ingestion/` F1 Bronze Layer

Raw F1 telemetry from FastF1 → Hive-partitioned Parquet. Bronze is append-only; all business logic lives in the dbt transform layer.

📖 Full docs: https://offthepace.mintlify.app/reference/schemas
🚀 Quickstart: https://offthepace.mintlify.app

**Coverage:** 168 races × 4 datasets (2018–2024). Laps, weather, race control, telemetry (~180M samples).

Follow steps 1–5 in order; step 6 hands off to the downstream layers. The reference tables below the steps document coverage, known issues, and schemas.

## 1. Setup

```bash
pip install -r requirements.txt
```

No credentials required for FastF1. FastF1 caches to `data/cache/` automatically.

## 2. Choose your data scope

Pick the smallest scope that fits your task most contributors never need a full backfill:

| Scenario | What you need | Time | Size | Command |
|----------|---------------|------|------|---------|
| **Experimenting with dbt SQL transforms** | Test fixtures only | 0 min | – | `make dbt-dev` (uses `transform/tests/fixtures/bronze/`) |
| **Scale-testing transforms, validation before PR** | Recent seasons (2023–2024) | ~15 min | ~200 MB | `make ingest-recent` |
| **Full feature verification, ML training** | All 168 races (2018–2024) | 30–45 min | ~2 GB | `make ingest-all` |
| **Single race smoke test** | One race only | 2–5 min | ~100 MB | `python src/ingest.py --season 2024 --round 1 --session R` |
| **Ingestion development** | Verify one race, run offline tests | <5 s | – | `pytest tests/ -v` (no network) |

**Default:** most contributors start with fixtures for SQL work, then run `make ingest-recent` to validate their dbt changes scale. The full `make ingest-all` is optional unless working on ML models or verification.

## 3. Ingest

```bash
python src/ingest.py --season 2024 --round 1 --session R   # single race (~100 MB, 2–5 min)
python src/ingest.py --season 2024 --session both --force  # full season (~2 GB, 30–45 min)
pytest tests/ -v                                            # offline tests (no network, <5 s)
```

The `make` targets in step 2 wrap `src/ingest.py` with the season ranges shown.

## 4. Monitor long runs

For full backfills (hours-long runs), use the monitor to catch failures early instead of watching the terminal:

```bash
# Terminal 1: Start ingestion in background
python src/ingest.py --start-season 2018 --end-season 2024 --session R > ingest.log 2>&1 &

# Terminal 2: Monitor for failures/completion (exits when done)
make monitor-ingest LOG=ingest.log
# or directly:  python scripts/monitor_ingest.py ingest.log   (stdlib-only, no deps)
```

The monitor polls every 10 seconds and exits immediately (non-zero) if:
- Data quality failures ([DQ FAIL])
- Process errors (OOM, disk full, killed, etc.)

…or exits 0 when ingestion completes (`=== COMPLETE:`). Ignores FastF1 DEBUG-level noise.
The monitor is stdlib-only Python no extra dependencies.

## 5. Verify

After ingesting, confirm Bronze integrity (race counts, nulls, duplicates, schema):

```bash
make verify-bronze   # or: python verify_bronze.py
```

Only seasons present on disk are checked, so it works after a partial
`make ingest-recent` as well as a full `make ingest-all`. Exits non-zero if anything is off.

Two companion views read what each run recorded:

```bash
make manifest-report                 # last-run status per session + schema-drift across runs
python verify_bronze.py --markdown   # regenerate the Bronze Coverage table below from disk
```

`manifest-report` turns the per-run manifests (`data/bronze/manifests/run_<id>.parquet`)
into observability: it surfaces the latest `ok`/`skip`/`error` per session and flags any
change in a dataset's schema fingerprint between runs (FastF1 column drift). The
`--markdown` mode of `verify_bronze.py` emits the coverage table straight from the files
on disk, so the docs stay honest instead of being hand-maintained.

## 6. Next: build features

Ingestion stops at raw Bronze **no features are engineered here** (see Architecture below). Once Bronze is in place, feature creation happens in two downstream layers.

### 6a. transform/ (dbt) SQL feature marts

`make dbt-dev` then `make dbt-test`. Builds three feature marts:

| Mart | Features |
|------|----------|
| `fct_stint_features` | Pit-strategy value per stint `opportunity_cost_s`, `optimal_pit_lap`, `actual_pit_lap` |
| `fct_driver_skill_features` | Per-lap driver skill `driver_skill_residual_s`, `correction_weight`, `rainfall_flag`, `track_energy_index`, `abrasiveness_index`, `debut_year`, `pu_family` |
| `fct_cliff_prediction_features` | Tyre-degradation cliff compound curve (`compound_grip_peak`, `compound_wear_gradient`, `compound_cliff_onset_laps`, `compound_cliff_severity`), thermal load (`push_residual`, `cumulative_push_load_surface/bulk`), dirty air (`dirty_air_share_lap`, `dirty_air_thermal_load_surface/bulk`, `air_state_dominant`), cliff priors (`expected_degradation_rate_s_per_lap`, `cliff_onset_passed`, `laps_past_cliff`), plus `fuel_mass_kg`, `event_flag_any`; targets `next_lap_degradation_jump_s`, `laps_until_cliff_class` |

### 6b. ml/ (Python) model features

`make ml-features` → `make ml-all`. Assembles the training frame from `fct_cliff_prediction_features` into 8 grouped feature families (`ml/src/schema.py:FEATURE_GROUPS`):

| Group | Columns |
|-------|---------|
| `stint_position` | `lap_number`, `lap_in_stint`, `age_in_stint`, `fuel_mass_kg` |
| `compound` | `compound`, `compound_grip_peak`, `compound_wear_gradient`, `compound_optimal_temp_low/high`, `compound_cliff_onset_laps`, `compound_cliff_severity` |
| `cliff_prior` | `expected_compound_pace_s`, `expected_degradation_rate_s_per_lap`, `cliff_onset_passed`, `laps_past_cliff`, `cliff_candidate_flag` |
| `thermal` | `push_residual`, `cumulative_push_load_surface`, `cumulative_push_load_bulk` |
| `dirty_air` | `dirty_air_share_lap`, `dirty_air_thermal_load_surface`, `dirty_air_thermal_load_bulk`, `air_state_dominant` |
| `weather_air` | `ambient_temp_delta`, `is_rain_lap` |
| `track` | `track_energy_index`, `circuit_abrasiveness_index` |
| `context` | `constructor_id`, `event_flag_any`, `anomaly_class` |

If you only ingested for dbt/SQL work, `make dbt-dev` is your next step. See `transform/README.md` and `ml/README.md` for details.

---

## Architecture

```
FastF1 API → src/ingest.py → data/bronze/<dataset>/season=YYYY/race=<slug>/
```

Output feeds directly into `transform/` (dbt Silver layer).

For the design decisions behind this layout — why Bronze is dumb, why append-only,
why schema fingerprinting, the retry/backoff contract and DQ severity tiers — see
[DESIGN.md](DESIGN.md).

## Bronze Coverage

| Season | Laps | Weather | Race Control | Telemetry | Notes |
|--------|------|---------|-------------|-----------|-------|
| 2018 | 20 ✓ | 20 ✓ | 20 ✓ | 18 ✓ | Rd1/Rd2 telemetry unavailable F1 didn't publish livetiming feed until later in season |
| 2019 | 21 ✓ | 21 ✓ | 21 ✓ | 21 ✓ | German GP cancelled |
| 2020 | 17 ✓ | 17 ✓ | 17 ✓ | 17 ✓ | Covid-shortened season |
| 2021 | 22 ✓ | 22 ✓ | 22 ✓ | 22 ✓ | |
| 2022 | 22 ✓ | 22 ✓ | 22 ✓ | 22 ✓ | |
| 2023 | 22 ✓ | 22 ✓ | 22 ✓ | 22 ✓ | Emilia Romagna cancelled |
| 2024 | 24 ✓ | 24 ✓ | 24 ✓* | 24 ✓ | *`session_time_s` null |
| **Total** | **168** | **168** | **168** | **166** | Telemetry for 166/168 races; 2018 Rd1/Rd2 missing |

## Known Issues

| Issue | Root cause | Impact | Remediation |
|-------|-----------|--------|-------------|
| `session_time_s` null in 2024 RC files | FastF1 v3.8.3 changed `Time` column type | Low supplementary field | Fix in src/; files not re-written |
| Las Vegas 2024: timing integrity warnings 7 drivers | FastF1 internal accuracy flag | Low laps still present | Under investigation |
| Pre-season Rd 0 warning in logs | FastF1 raises on testing events by round number | None correctly handled | Acceptable |

## Schemas index

| Schema file | Dataset it validates |
|---|---|
| `schemas/laps.schema.json` | `stg_laps` row shape lap number, sector times, compound, stint |
| `schemas/weather.schema.json` | `stg_weather` row shape air/track temp, humidity, wind |
| `schemas/race_control.schema.json` | `race_control` bronze row shape safety car, flags, penalties |
| `schemas/telemetry.schema.json` | `stg_telemetry` row shape 18Hz speed, throttle, brake, DRS |

## Tests

`tests/test_ingestion.py` asserts row counts, null guards, and schema conformance against fixture Parquet (no network, <5 s with `pytest tests/ -v`). Fixtures live in `tests/fixtures/`.

---

← Previous in tour: [README.md](../README.md) · **Next in tour: [data/](../data/README.md) →**
