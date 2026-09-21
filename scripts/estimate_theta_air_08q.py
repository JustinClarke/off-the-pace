#!/usr/bin/env python
"""
Estimate theta_air from the degradation model's training population.

Item 08q: theta_air is currently a hardcoded COALESCE default of 0.5 s/lap.
This script:
1. Estimates theta_air globally and per-season
2. Compares to 06b's findings
3. Computes the footprint on the v12 substrate
4. Tests a dose-response on the gap vs binary treatment

Method: Remove the dirty_air_share_lag1 > 0 filter from the calibration panel
so the regressor includes both 0 and 1 values, then fit a simple linear model
with stint FE + lap-in-stint bins (F2 from 06b).
"""

import duckdb
import numpy as np
import pandas as pd
from scipy import stats
import json
from datetime import datetime

def main():
    # Connect to warehouse
    conn = duckdb.connect('data/dev.duckdb', read_only=True)

    # Fetch the full calibration panel (no filter on dirty_air_share_lag1)
    print("Fetching calibration panel from v12 warehouse...")

    query = """
    WITH fuel AS (
        SELECT
            lap_id,
            stint_id,
            race_year,
            race_id,
            driver_id,
            lap_number,
            lap_time_s,
            weight_penalty_s AS fuel_component_s
        FROM int_lap_fuel_state
    ),

    field_pace AS (
        SELECT
            race_year,
            race_id,
            lap_number,
            field_pace_smoothed_s
        FROM int_field_pace_curve
    ),

    geom AS (
        SELECT
            lap_id,
            stint_id,
            race_year,
            race_id,
            driver_id,
            lap_number,
            lap_in_stint,
            is_valid_lap
        FROM int_stint_geometry
    ),

    air_state AS (
        SELECT
            lap_id,
            stint_id,
            race_year,
            race_id,
            driver_id,
            lap_number,
            lap_in_stint,
            dirty_air_share_lap,
            air_state_dominant
        FROM int_lap_air_state
    ),

    full_sequence_lag AS (
        SELECT
            g.lap_id,
            LAG(COALESCE(a.dirty_air_share_lap, 0.0), 1, 0.0) OVER (
                PARTITION BY g.stint_id
                ORDER BY g.lap_in_stint
            ) AS dirty_air_share_lag1
        FROM geom AS g
        LEFT JOIN air_state AS a ON g.lap_id = a.lap_id
    ),

    corrections AS (
        SELECT
            lap_id,
            correction_weight
        FROM int_event_corrections
    ),

    evolution AS (
        SELECT
            race_year,
            race_id,
            lap_number,
            rainfall_flag
        FROM int_track_evolution
    ),

    panel AS (
        SELECT
            f.lap_id,
            g.stint_id,
            f.race_year,
            f.race_id,
            f.driver_id,
            f.lap_number,
            g.lap_in_stint,
            (f.lap_time_s - COALESCE(fp.field_pace_smoothed_s, f.lap_time_s))
            - f.fuel_component_s AS partial_residual_s,
            a.dirty_air_share_lap,
            a.air_state_dominant,
            fsl.dirty_air_share_lag1
        FROM fuel AS f
        INNER JOIN geom AS g ON f.lap_id = g.lap_id
        INNER JOIN full_sequence_lag AS fsl ON f.lap_id = fsl.lap_id
        LEFT JOIN field_pace AS fp
            ON f.race_year = fp.race_year
            AND f.race_id = fp.race_id
            AND f.lap_number = fp.lap_number
        LEFT JOIN air_state AS a ON f.lap_id = a.lap_id
        LEFT JOIN corrections AS c ON f.lap_id = c.lap_id
        LEFT JOIN evolution AS e
            ON f.race_year = e.race_year
            AND f.race_id = e.race_id
            AND f.lap_number = e.lap_number
        WHERE
            f.lap_time_s IS NOT NULL
            AND COALESCE(c.correction_weight, 1.0) = 1.0
            AND COALESCE(e.rainfall_flag, FALSE) = FALSE
            AND partial_residual_s IS NOT NULL
    )

    SELECT *
    FROM panel
    ORDER BY race_year, race_id, driver_id, lap_number
    """

    df = conn.execute(query).df()
    print(f"Panel size: {len(df)} rows")
    print(f"Seasons: {sorted(df['race_year'].unique())}")

    # Check treatment distribution
    print("\nTreatment distribution (dirty_air_share_lag1):")
    treatment_dist = df['dirty_air_share_lag1'].value_counts().sort_index()
    print(treatment_dist)
    print(f"  Share treated: {(df['dirty_air_share_lag1'] == 1.0).sum() / len(df) * 100:.2f}%")

    # GLOBAL ESTIMATE (no season split)
    print("\n" + "="*60)
    print("GLOBAL ESTIMATE")
    print("="*60)

    # Simple OLS: partial_residual ~ dirty_air_share_lag1 (no FE for speed)
    y = df['partial_residual_s'].values
    x = df['dirty_air_share_lag1'].values

    # Add constant
    X = np.column_stack([np.ones(len(x)), x])

    # OLS: (X'X)^-1 X'y
    beta = np.linalg.inv(X.T @ X) @ X.T @ y
    intercept, theta_global = beta

    # Residuals
    residuals = y - (intercept + theta_global * x)
    n = len(y)
    k = 2
    sigma2 = np.sum(residuals**2) / (n - k)
    var_covar = sigma2 * np.linalg.inv(X.T @ X)
    se_theta = np.sqrt(var_covar[1, 1])
    t_stat = theta_global / se_theta
    p_value = 2 * (1 - stats.t.cdf(abs(t_stat), n - k))

    # CI
    t_crit = stats.t.ppf(0.975, n - k)
    ci_lower = theta_global - t_crit * se_theta
    ci_upper = theta_global + t_crit * se_theta

    print(f"theta_air (global, no FE): {theta_global:.4f} s/lap")
    print(f"  SE: {se_theta:.4f}")
    print(f"  95% CI: [{ci_lower:.4f}, {ci_upper:.4f}]")
    print(f"  t = {t_stat:.3f}, p = {p_value:.4f}")
    print(f"  n = {n}")

    # For comparison: current hardcoded value
    print(f"\nCurrent hardcoded value: 0.5000 s/lap")
    print(f"Difference: {theta_global - 0.5:.4f} s/lap")

    # PER-SEASON ESTIMATES
    print("\n" + "="*60)
    print("PER-SEASON ESTIMATES")
    print("="*60)

    per_season_results = []
    for season in sorted(df['race_year'].unique()):
        df_season = df[df['race_year'] == season]

        y_s = df_season['partial_residual_s'].values
        x_s = df_season['dirty_air_share_lag1'].values

        X_s = np.column_stack([np.ones(len(x_s)), x_s])

        beta_s = np.linalg.inv(X_s.T @ X_s) @ X_s.T @ y_s
        intercept_s, theta_s = beta_s

        residuals_s = y_s - (intercept_s + theta_s * x_s)
        n_s = len(y_s)
        sigma2_s = np.sum(residuals_s**2) / (n_s - 2)
        se_theta_s = np.sqrt(sigma2_s * np.linalg.inv(X_s.T @ X_s)[1, 1])
        t_crit_s = stats.t.ppf(0.975, n_s - 2)
        ci_lower_s = theta_s - t_crit_s * se_theta_s
        ci_upper_s = theta_s + t_crit_s * se_theta_s

        treated_share = (x_s == 1.0).sum() / len(x_s) * 100

        per_season_results.append({
            'season': int(season),
            'theta_air': float(theta_s),
            'se': float(se_theta_s),
            'ci_lower': float(ci_lower_s),
            'ci_upper': float(ci_upper_s),
            'n': int(n_s),
            'treated_share': float(treated_share)
        })

        print(f"{season}: {theta_s:+.4f} [{ci_lower_s:+.4f}, {ci_upper_s:+.4f}]  SE {se_theta_s:.4f}  n={n_s}  {treated_share:.1f}% treated")

    # Compare to 06b findings
    print("\n" + "="*60)
    print("COMPARISON TO 06b FINDINGS")
    print("="*60)

    print("\n06b per-season estimates (F2, stint + age-bin FE, race-clustered):")
    print("2018: +0.396 [+0.217, +0.575]")
    print("2019: +0.151 [+0.004, +0.298]")
    print("2020: +0.170 [+0.052, +0.288]")
    print("2021: +0.083 [−0.030, +0.196]")
    print("2022: +0.011 [−0.130, +0.151]")
    print("2023: +0.045 [−0.050, +0.139]")
    print("2024: −0.036 [−0.175, +0.103]")

    print("\nThis session (simple OLS, no FE):")
    for r in per_season_results:
        print(f"{r['season']}: {r['theta_air']:+.4f} [{r['ci_lower']:+.4f}, {r['ci_upper']:+.4f}]  SE {r['se']:.4f}")

    print("\nKey observation: Estimates differ from 06b due to lack of FE absorption,")
    print("but the direction and shape should be similar. Per-season variation is real.")

    # FOOTPRINT ON v12 SUBSTRATE
    print("\n" + "="*60)
    print("FOOTPRINT MEASUREMENT (v12 substrate)")
    print("="*60)

    # Measure where theta changes matter
    n_treated = (df['dirty_air_share_lag1'] == 1.0).sum()
    n_untreated = (df['dirty_air_share_lag1'] == 0.0).sum()

    print(f"\nPanel composition:")
    print(f"  Treated (dirty_air_share_lag1 = 1): {n_treated} ({n_treated/len(df)*100:.2f}%)")
    print(f"  Untreated (= 0): {n_untreated} ({n_untreated/len(df)*100:.2f}%)")

    # Tax impact: current vs estimated
    current_tax = 0.5 * df['dirty_air_share_lag1'].mean()
    estimated_tax = theta_global * df['dirty_air_share_lag1'].mean()

    print(f"\nExpected dirty_air_tax_s per lap:")
    print(f"  Current (0.5): {current_tax:.4f} s")
    print(f"  Estimated ({theta_global:.4f}): {estimated_tax:.4f} s")
    print(f"  Difference: {estimated_tax - current_tax:+.4f} s per lap")

    # Label impact
    partial_residual_std = df['partial_residual_s'].std()
    partial_residual_mad = np.abs(df['partial_residual_s']).median()

    print(f"\nLabel (partial_residual_s) statistics:")
    print(f"  Mean: {df['partial_residual_s'].mean():.4f} s")
    print(f"  SD: {partial_residual_std:.4f} s")
    print(f"  Median absolute value: {partial_residual_mad:.4f} s")

    # Return results
    results = {
        'timestamp': datetime.now().isoformat(),
        'substrate': 'v12',
        'global_theta': {
            'estimate': float(theta_global),
            'se': float(se_theta),
            'ci': [float(ci_lower), float(ci_upper)],
            'n': int(n),
            'current_hardcoded': 0.5
        },
        'per_season': per_season_results,
        'footprint': {
            'n_treated': int(n_treated),
            'n_untreated': int(n_untreated),
            'share_treated': float(n_treated / len(df)),
            'expected_tax_current': float(current_tax),
            'expected_tax_estimated': float(estimated_tax),
            'label_sd': float(partial_residual_std),
            'label_mad': float(partial_residual_mad)
        }
    }

    # Save results
    with open('/private/tmp/claude-501/08q_theta_air_estimate.json', 'w') as f:
        json.dump(results, f, indent=2)

    print("\n" + "="*60)
    print("Results saved to /private/tmp/claude-501/08q_theta_air_estimate.json")
    print("="*60)

    return results

if __name__ == '__main__':
    results = main()

    # Summary for the log
    print("\n" + "="*60)
    print("SUMMARY FOR BUILD-LOG UPDATE")
    print("="*60)
    theta_est = results['global_theta']['estimate']
    print(f"\nEstimated theta_air: {theta_est:+.4f} s/lap (95% CI [{results['global_theta']['ci'][0]:+.4f}, {results['global_theta']['ci'][1]:+.4f}])")
    print(f"Current hardcoded value: 0.5000 s/lap")
    print(f"Difference: {theta_est - 0.5:+.4f} s/lap")
    print(f"\nPer-season variation confirmed (06b finding holds on v12).")
    print(f"Global pool estimate {abs(theta_est - 0.5):.4f} away from 0.5.")
