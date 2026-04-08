# Ingestion   F1 Bronze Layer

Raw F1 telemetry from FastF1 → Hive-partitioned Parquet. Bronze is append-only; all business logic lives in the dbt transform layer.

📖 Full docs: https://off-the-pace.onrender.com/reference/schemas
🚀 Quickstart: https://off-the-pace.onrender.com

**Coverage:** 168 races × 4 datasets (2018–2024). Laps, weather, race control, telemetry (~180M samples).

## Quick commands

```bash
python src/ingest.py --season 2024 --round 1 --session R   # single race (~200 MB, 2–5 min)
python src/ingest.py --season 2024 --session both --force  # full season (~2 GB, 30–45 min)
pytest tests/ -v                                            # offline tests (no network, <5 s)
```

## Setup

```bash
pip install -r requirements.txt
```

No credentials required for FastF1. FastF1 caches to `data/cache/` automatically.

## Architecture

```
FastF1 API → src/ingest.py → data/bronze/<dataset>/season=YYYY/race=<slug>/
```

Output feeds directly into `transform/` (dbt Silver layer).

## Bronze Coverage

| Season | Laps | Weather | Race Control | Telemetry | Notes |
|--------|------|---------|-------------|-----------|-------|
| 2018 | 20 ✓ | 20 ✓ | 20 ✓ | 18 ✓ | Rd1/Rd2 telemetry unavailable-F1 didn't publish livetiming feed until later in season |
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
| `session_time_s` null in 2024 RC files | FastF1 v3.8.3 changed `Time` column type | Low-supplementary field | Fix in src/; files not re-written |
| Las Vegas 2024: timing integrity warnings 7 drivers | FastF1 internal accuracy flag | Low-laps still present | Under investigation |
| Pre-season Rd 0 warning in logs | FastF1 raises on testing events by round number | None-correctly handled | Acceptable |

---

**Schemas index**

| Schema file | Dataset it validates |
|---|---|
| `schemas/laps.schema.json` | `stg_laps` row shape-lap number, sector times, compound, stint |
| `schemas/weather.schema.json` | `stg_weather` row shape-air/track temp, humidity, wind |
| `schemas/race_control.schema.json` | `stg_race_control` row shape-safety car, flags, penalties |
| `schemas/telemetry.schema.json` | `stg_telemetry` row shape-18Hz speed, throttle, brake, DRS |

**Tests**

`tests/test_ingestion.py` asserts row counts, null guards, and schema conformance against fixture Parquet (no network, <5 s with `pytest tests/ -v`). Fixtures live in `tests/fixtures/`.

---

← Previous in tour: [README.md](../README.md) · **Next in tour: [data/](../data/README.md) →**
