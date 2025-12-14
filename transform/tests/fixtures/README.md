# Test Fixtures

Small, committed parquet files used by CI to run `dbt build` without the full 168-race bronze dataset.

## Why fixtures exist

The source paths in `src_formula1.yml` default to relative local paths (`../data/bronze`). CI can override this by using a `--vars '{"bronze_base": "..."}'` parameter pointing at this fixture directory. The fixture contains 3 representative races across all 4 datasets (laps, weather, telemetry, race_control).

## Chosen races

| Race | Season | Why |
|---|---|---|
| Bahrain Grand Prix | 2023 | Clean dry race, multi-compound, good baseline |
| Italian Grand Prix | 2020 | Monza   low-energy, sprint-style strategy, used tyres common |
| Brazilian Grand Prix | 2024 | Wet/mixed conditions, exercises rain-lap handling |

## Directory layout

Mirrors bronze Hive partitioning so `read_parquet(.../*/*/*.parquet)` globs work:

```
fixtures/
  bronze/
    laps/
      season=2020/race_id=italian_grand_prix/data.parquet
      season=2023/race_id=bahrain_grand_prix/data.parquet
      season=2024/race_id=sao_paulo_grand_prix/data.parquet
    weather/   (same structure)
    telemetry/ (same structure)
    race_control/ (same structure)
```

## Generating / refreshing fixtures

Run from the repo root (`.venv` must be active):

```bash
python ingestion/src/create_fixtures.py \
  --races 2020/italian_grand_prix 2023/bahrain_grand_prix 2024/sao_paulo_grand_prix \
  --output transform/tests/fixtures/bronze
```

After generating, commit the parquet files. Target size < 15 MB per race across all 4 datasets (exclude telemetry columns not needed by any model if over budget).

## Status

Fixture parquet files are committed for all three races × four datasets (laps, weather,
telemetry, race_control). CI runs `dbt build` against these files on every PR via the
`ci` dbt target in `profiles/profiles.yml`.
