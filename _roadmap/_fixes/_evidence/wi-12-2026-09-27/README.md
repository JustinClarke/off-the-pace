# WI-12 evidence: the 06b ladder re-run on the WI-01 label (2026-09-27)

Read-only against `data/dev.duckdb` (WI-01 verification-pass build, theta_air 0.5033; re-run
after W40 on the rebuild with theta_air 0.331, see Gates) and
`../wi-15a-2026-09-25/dev_unfixed.duckdb`. Nothing in the warehouse was written.

| File | What it is |
| :--- | :--- |
| `d1_build_panels_wi12.py` | Builds the lap panels (and the corner panel into `$WI12_SCRATCH`). Stops unless the `wi01` panel reproduces the shipped calibration panel (row count and pooled slope). |
| `d2_fit_wi12.py` | Every fit: 06b reproduction, the F0-F3 ladder, the lead placebo, the 2022 question, the 2025 check, the decomposition, the W40 estimator comparison, the corner split. Stops unless 06b's committed panel reproduces 06b's published table. |
| `d2_output.txt` | The printed tables from `d2` (the numbers quoted in the WI doc). |
| `wi12_fits.json` | Every coefficient, SE, CI and n behind `d2_output.txt` (224 entries). |
| `panel_wi12_lap_wi01.parquet` | The headline panel: 138,970 laps, 2018-2025, `int_dirty_air_tax_component`'s calibration panel on the WI-01 label. |
| `panel_wi12_lap_as06b_now.parquet` | 06b's own panel SQL on the current warehouse (fabricated base via COALESCE, fuel only). |
| `panel_wi12_lap_as06b_0925.parquet` | 06b's own panel SQL on the 2026-09-25 pre-WI-15a/WI-01 warehouse. Not 06b's substrate (WI-02a, WI-05, WI-09, WI-13 had landed), so it is an intermediate arm, not the reproduction target. |

The "before" is `_roadmap/_improvements/implementations/06b/panel_06b_lap.parquet`, the panel
06b committed at publication; the warehouse it came from no longer exists.

## Gates

- **Panel reproduction:** 138,970 rows = shipped `calibration_sample_n`; pooled OLS slope
  0.5033413666 vs the shipped `theta_air` 0.5033413666 (|d| 3.3e-15). **Since W40** the model
  applies the declared `theta_air_label_value` (0.331) instead of shipping that slope, so `d1`
  now checks three things: the row count; the pooled slope against the pre-W40 value as a
  fingerprint of the panel (y and x are upstream of theta, so it does not move with it); and
  shipped `theta_air` = the declared var.
- **W40 gate (`d2`, section W):** the declared `theta_air_label_value` must equal the F2 fit
  (0.331347) to 3 dp, or `d2` stops. The model no longer fits theta, so this is the one place
  the declared value is tied back to data.
- **Estimator reproduction:** 06b's committed panel through `d2`'s code gives 06b's published F2
  table in all seven seasons, and its era contrast (-0.2188), trend (-0.0667) and six placebo
  boundaries exactly.
- **Determinism:** `d2` re-run after a file rename gives byte-identical output.
- **Re-run after W40 (2026-09-27), on `data/dev.duckdb` rebuilt with theta_air 0.331:** all
  three lap panels are identical in content to the first run (same rows, same values). `d2`'s
  printed tables are identical except two renamed W-section labels (F0 "shipped label value"
  -> "WI-01 interim label value", F2 gains "label value since W40") and the new W40 gate line.
  Full-precision entries in `wi12_fits.json` differ by at most 4.6e-8, because the rebuilt
  parquet's row order differs (the panel query has no ORDER BY) and pyfixest's iterative
  demeaning is order-sensitive at that level. This is expected: the ladder fits theta from the
  calibration panel, whose outcome (lap - base - fuel - tyre cost) is upstream of the label's
  theta, so the label's value cannot move these numbers.

## Run

```sh
export WI12_SCRATCH=/some/scratch/dir      # corner panel (~30 MB) goes here
./.venv/bin/python _roadmap/_fixes/_evidence/wi-12-2026-09-27/d1_build_panels_wi12.py
./.venv/bin/python _roadmap/_fixes/_evidence/wi-12-2026-09-27/d2_fit_wi12.py
```

pyfixest 0.60.0, duckdb 1.5.3, pandas 2.3.3. A rebuild of `data/dev.duckdb` after this date
changes the `wi01` and `as06b_now` panels; the committed parquets are the record.
