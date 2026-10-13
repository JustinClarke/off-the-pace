# Seeds

Static CSV files loaded into DuckDB as tables. Every seed except the (currently empty)
`seed_manual_lap_exceptions.csv` has a `schema.yml` entry with column tests and descriptions;
its column types are pinned in `dbt_project.yml`.

| Seed | Grain | Source | Refresh |
|---|---|---|---|
| `circuit_reference.csv` | circuit | First-stint regression (`fit_weight_penalty.py`) | `make coefficients-fit` |
| `compound_cliff_params.csv` | circuit × compound × season | KM survival fitter (`fit_compound_cliff.py`) | `make coefficients-fit` |
| `race_to_track.csv` | race | Manual | When new seasons are ingested |
| `race_scheduled_laps.csv` | race | Manual (scheduled race distance, the fuel model's pre-race lap count) | When new seasons are ingested |
| `tyre_allocations.csv` | race | Pirelli weekend compound nominations, 2019 onward | When new seasons are ingested |
| `compound_hardness_scale.csv` | compound × era | Declared cross-era hardness rank (1 = hardest) for the power-law tyre curve | When Pirelli changes the range |
| `raw_dim_events.csv` | event | Manual (2021 season only) | Expand as automated detection is built |
| `seed_manual_lap_exceptions.csv` | driver × lap | Manual correction-weight overrides, read by `int_event_corrections` (empty today) | As needed |
| `driver_isolation_method_scores.csv` | rating | Written by `scripts/validate_driver_isolation.py --write-seed` | When the isolation validation reruns |
| `label_stability_baseline.csv` | season | Frozen per-season label snapshot that `assert_prior_season_labels_frozen` compares against | Only when the label version bumps |

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
