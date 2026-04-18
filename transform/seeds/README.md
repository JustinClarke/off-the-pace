# Seeds

Static CSV files loaded into DuckDB as tables. All seeds have a `schema.yml` entry with
column tests and descriptions.

| Seed | Rows | Source | Refresh |
|---|---|---|---|
| `circuit_reference.csv` | 44 circuits | First-stint regression (`fit_weight_penalty.py`) | `make coefficients-fit` |
| `compound_cliff_params.csv` | 401 groups | KM survival fitter (`fit_compound_cliff.py`) | `make coefficients-fit` |
| `dim_corners.csv` | ~400 corners | Manual from circuit maps | When track layouts change |
| `race_to_track.csv` | 168 races | Manual | When new seasons are ingested (covers all 168 races; telemetry incomplete for 2 of them) |
| `raw_dim_events.csv` | ~30 events | Manual (2021 season only) | Expand as automated detection is built |
| `tyre_allocations.csv` | stub | Not yet populated | When Pirelli allocation sheets are scraped |

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
