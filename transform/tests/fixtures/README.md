# Test Fixtures

Small, committed parquet files used by CI to run `dbt build` without the full 168-race bronze dataset.

## Why fixtures exist

The source paths in `src_formula1.yml` default to relative local paths (`../data/bronze`). CI can override this by using a `--vars '{"bronze_base": "..."}'` parameter pointing at this fixture directory. The fixture contains 3 representative races across all 8 source datasets: `laps`, `weather`, `telemetry`, `race_control`, `track_status`, `session_status`, `results`, and `circuit_info`. (Earlier the first four were enough; the staging models `stg_track_status`, `stg_session_status`, `stg_results`, and `stg_circuit_info` made the remaining four required for a complete `dbt build` on fixtures.)

## Chosen races

| Race | Season | Why |
|---|---|---|
| Bahrain Grand Prix | 2023 | Clean dry race, multi-compound, good baseline |
| Italian Grand Prix | 2020 | Monza  -  low-energy, sprint-style strategy, used tyres common |
| Brazilian Grand Prix | 2024 | Wet/mixed conditions, exercises rain-lap handling |

## Directory layout

Mirrors bronze Hive partitioning so `read_parquet(.../*/*/*.parquet)` globs work:

```
fixtures/
  bronze/
    laps/
      season=2020/race=italian_grand_prix/data.parquet
      season=2023/race=bahrain_grand_prix/data.parquet
      season=2024/race=são_paulo_grand_prix/data.parquet
    weather/        (same structure, + session=Q subdirectory)
    telemetry/      (same structure)
    race_control/   (same structure)
    track_status/   (same structure)
    session_status/ (same structure)
    results/        (same structure)
    circuit_info/   (same structure)
```

## Generating / refreshing fixtures

Run from the repo root (`.venv` must be active):

```bash
python ingestion/src/create_fixtures.py \
  --races 2020/italian_grand_prix 2023/bahrain_grand_prix 2024/sao_paulo_grand_prix \
  --output transform/tests/fixtures/bronze
```

After generating, commit the parquet files. Target size < 15 MB per race across all datasets (exclude telemetry columns not needed by any model if over budget).

## Status

Fixture parquet files are committed for all three races × eight datasets (`laps`, `weather`,
`telemetry`, `race_control`, `track_status`, `session_status`, `results`, `circuit_info`). CI runs
`dbt build` against these files on every PR via the `ci` dbt target in `profiles/profiles.yml`,
and `dbt build` reaches `ERROR=0` on the fixture set.
