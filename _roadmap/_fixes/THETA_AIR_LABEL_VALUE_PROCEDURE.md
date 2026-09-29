# Procedure: Updating theta_air_label_value when the calibration panel moves

**Related watch rule:** W47 (WI-12) — theta_air_label_value is a frozen external fit

## Overview

`theta_air_label_value` is a constant declared in `transform/dbt_project.yml` that prices dirty-air tax in the label. It is fitted outside dbt (by `WI-12`'s d1/d2 scripts) and applied inside dbt via SQL. When the calibration panel moves, the fitted value may change, and the declared var must be updated to keep them in sync.

**The W40 gate in `d2_fit_wi12.py` enforces this:** it exits with error if the declared value does not match the fitted F2 coefficient to 3 decimal places.

## When the calibration panel moves

The panel (`int_dirty_air_tax_component.calibration_panel`) changes when:

1. **WI-02b lands:** Compound seed refit changes `compound_component_s`, which is part of the outcome (`y = lap_time - base - fuel - tyre_cost`)
2. **FD6 is ruled:** 2018 no-telemetry laps get a new treatment flag (moves rows in or out of the panel)
3. **`theta_air_fit_season_max` is changed:** Moves the panel's season boundary
4. **A new season is ingested:** Expands the panel to include new laps (when it reaches the `theta_air_fit_season_max` window)

## Procedure: Re-run d1/d2 and update the var

Include these steps in the definition of done for any item that moves the calibration panel:

### Step 1: Rebuild the warehouse

Ensure `data/dev.duckdb` is rebuilt from the working tree with all upstream changes:

```bash
dbt build
```

This ensures the calibration panel is computed on the new label/seed state.

### Step 2: Run d1 (build panels)

```bash
export WI12_SCRATCH=/tmp/wi12-scratch
mkdir -p $WI12_SCRATCH
./.venv/bin/python _roadmap/_fixes/_evidence/wi-12-2026-09-27/d1_build_panels_wi12.py
```

**What it checks:**
- Panel row count matches `calibration_sample_n` (138,970 as of 2026-09-27; may grow when new seasons are ingested)
- Pooled OLS slope (fingerprint of panel composition) matches the expected value
- Shipped `theta_air` equals the declared `theta_air_label_value` in dbt_project.yml

**Stops if:** The panel has changed unexpectedly, indicating something went wrong upstream

### Step 3: Run d2 (fit and gate)

```bash
./.venv/bin/python _roadmap/_fixes/_evidence/wi-12-2026-09-27/d2_fit_wi12.py
```

**What it does:**
- Fits the F2 estimator (stint FE + six tyre-age bins, race-clustered) on the new panel
- Runs the W40 gate: checks that F2 coefficient rounds to `theta_air_label_value` to 3 dp

**Stops if:** The W40 gate fails (F2 does not match the declared value)

### Step 4: If W40 gate fails, update the var

If `d2` exits with error on the W40 gate:

```
W40 GATE FAILED: F2 0.332456 does not round to the declared theta_air_label_value 0.331
```

Then the panel has moved enough that the fitted value changed. Update `transform/dbt_project.yml`:

```yaml
# Line 259: update to the new F2 fit, rounded to 3 dp
theta_air_label_value: 0.332  # was 0.331; F2 fit 0.332456 on the 2026-XX-XX panel
```

Add a comment noting the date and reason (which item moved the panel).

### Step 5: Re-run d2 to confirm the gate passes

After updating the var:

```bash
./.venv/bin/python _roadmap/_fixes/_evidence/wi-12-2026-09-27/d2_fit_wi12.py
```

It should now exit cleanly with:
```
W40 GATE PASS: declared theta_air_label_value 0.332 = F2 0.332456 to 3 dp
```

### Step 6: Re-take the label-stability baseline

If the var changed, re-take the snapshot that `T9` (assert_prior_season_labels_frozen) uses to detect unintended label changes:

```bash
dbt build -s seed_label_stability_baseline.sql
```

This writes `transform/seeds/label_stability_baseline.csv` with the new label's statistics.

### Step 7: Verify tests pass

Run the relevant test suite:

```bash
dbt test -s int_dirty_air_tax_component T9 assert_prior_season_labels_frozen
```

Should show:
- `assert_prior_season_labels_frozen`: PASSED (T9 now sees the new baseline)
- No warnings about stale theta values

## Items that trigger this procedure (as of 2026-09-29)

| Item | Reason | Status |
|:-----|:-------|:--------|
| WI-02b | Compound seed refit (moved 2025 rows) | LANDED |
| WI-17 (future) | If it moves the panel | pending |
| FD6 ruling (future) | If 2018 no-telemetry treatment changes | open |
| New seasons (2026+) | When ingested and reach theta_air_fit_season_max | future |

## If the var does NOT change

If `d1`/`d2` run successfully and W40 gate passes **without updating** `theta_air_label_value`, that means the calibration panel moved but the F2 fit remained stable (or changed by less than 0.0005). This is normal; no edit needed.

**Example:** WI-02b's compound seed refit moved 2,025 training rows, but the fitted theta stayed 0.331 to 3 dp. The pool was large enough (138,679 laps) that the change did not cross a rounding boundary.

## References

- **WI-12 doc:** `_roadmap/_fixes/wi/WI-12-06b-remeasure.md` (Gate results, W40 gate details)
- **d1 script:** `_roadmap/_fixes/_evidence/wi-12-2026-09-27/d1_build_panels_wi12.py`
- **d2 script:** `_roadmap/_fixes/_evidence/wi-12-2026-09-27/d2_fit_wi12.py`
- **Script README:** `_roadmap/_fixes/_evidence/wi-12-2026-09-27/README.md`
- **dbt var:** `transform/dbt_project.yml` line 259
- **Label baseline:** `transform/seeds/label_stability_baseline.csv`
- **Test (T9):** `transform/tests/assert_prior_season_labels_frozen.sql`
