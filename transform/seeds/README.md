# Seeds

Static CSV files loaded into DuckDB as tables. All seeds have a `schema.yml` entry with
column tests and descriptions.

| Seed | Rows | Source | Refresh |
|---|---|---|---|
| `circuit_reference.csv` | 44 circuits | First-stint regression (`fit_weight_penalty.py`) | `make coefficients-fit` |
| `compound_cliff_params.csv` | 401 groups | KM survival fitter (`fit_compound_cliff.py`) | `make coefficients-fit` |
| `race_to_track.csv` | 148 races | Manual | When new seasons are ingested (2018_14 is missing from it; models that need corner geometry read dim_corners, which resolves that race from its own FastF1 corner table) |
| `raw_dim_events.csv` | ~30 events | Manual (2021 season only) | Expand as automated detection is built |

## Promotion workflow

Fitted seeds are written to `_pending/` first for human review. Never edit the live CSVs directly.

```bash
make coefficients-fit      # writes to seeds/_pending/
# review _pending/*.csv
make coefficients-promote  # archives old → seeds/_archive/, installs new → seeds/
```

Previous seed versions are retained in `_archive/` with a date suffix for rollback.
The `_pending/` and `_archive/` directories are disabled in `dbt_project.yml` so dbt
ignores them during seeding.
