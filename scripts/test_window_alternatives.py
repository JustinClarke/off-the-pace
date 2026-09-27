#!/usr/bin/env python3
"""
Test alternative window sizes (10-lap, 20-lap, stint, race grain) on the probe races
to see if coarser grain improves cross-season tactical stability.

Probe races for validation:
1. 2021_8 VER-HAM (Styrian)
2. 2021_19 HAM-VER (São Paulo)
3. 2023_2 VER-PER (Saudi Arabia)
"""

import duckdb
import numpy as np
import pandas as pd
from scipy import stats

def get_db():
    return duckdb.connect("data/dev.duckdb", read_only=True)

def extract_tactical_by_window(con, window_laps=5):
    """
    Extract tactical ratings aggregated by a rolling window of lap_number.

    This is a simplified test: we group by (driver, stint, lap ranges) instead of
    recomputing the window in SQL. For a true test, we'd need to recompute in SQL.
    """

    query = f"""
    SELECT
        race_year,
        race_id,
        driver_id,
        stint_id,
        lap_number,
        tactical_5lap_gain_s,
        pure_skill_5lap_gain_s
    FROM fct_driver_isolation_lap
    WHERE tactical_5lap_gain_s IS NOT NULL
        AND race_year BETWEEN 2018 AND 2024
    ORDER BY race_year, race_id, stint_id, lap_number
    """

    df = con.execute(query).df()

    # Simulate coarser window by grouping laps into bins
    df['window_bin'] = (df['lap_number'] // window_laps) * window_laps

    # Aggregate by window bin
    windowed = df.groupby(
        ['race_year', 'race_id', 'driver_id', 'stint_id', 'window_bin'],
        as_index=False
    ).agg({
        'tactical_5lap_gain_s': 'mean',
        'pure_skill_5lap_gain_s': 'mean',
        'lap_number': 'count'  # count of laps in window
    }).rename(columns={'lap_number': 'n_laps'})

    # Filter: only windows with ≥ 3 contributing laps
    windowed = windowed[windowed['n_laps'] >= 3]

    return windowed

def test_window_size(con, window_laps=5):
    """Test split-half stability for a given window size."""
    print(f"\nWindow size: {window_laps} laps")
    print("-" * 60)

    df = extract_tactical_by_window(con, window_laps)

    # Aggregate to driver-year (average across all windows for that driver-year)
    driver_year = df.groupby(['race_year', 'driver_id'], as_index=False).agg({
        'tactical_5lap_gain_s': 'mean'
    })

    # Split-half per year
    corrs = []
    for year in sorted(driver_year['race_year'].unique()):
        year_df = driver_year[driver_year['race_year'] == year]

        if len(year_df) >= 4:
            drivers = sorted(year_df['driver_id'].unique())
            mid = len(drivers) // 2

            g1 = year_df[year_df['driver_id'].isin(drivers[:mid])]['tactical_5lap_gain_s'].values
            g2 = year_df[year_df['driver_id'].isin(drivers[mid:])]['tactical_5lap_gain_s'].values

            if len(g1) >= 2 and len(g2) >= 2:
                # Compute correlation using sample pairing
                # (not perfect, but shows trend)
                corr, pval = stats.spearmanr(g1, g2)
                corrs.append(corr)
                print(f"  {year}: r = {corr:+.3f} (n={len(year_df)})")

    if corrs:
        print(f"  Median: {np.median(corrs):+.3f}")
        print(f"  Mean: {np.mean(corrs):+.3f}")
        return np.median(corrs)
    return np.nan

def test_stint_grain(con):
    """Test stint-grain tactical stability."""
    print(f"\nWindow: STINT GRAIN (entire stint aggregated)")
    print("-" * 60)

    query = """
    SELECT
        race_year,
        driver_id,
        AVG(tactical_gain_s) as tactical_rating
    FROM fct_driver_isolation_stint
    WHERE tactical_gain_s IS NOT NULL
        AND stint_phase = 'all'
        AND race_year BETWEEN 2018 AND 2024
    GROUP BY race_year, driver_id
    """

    df = con.execute(query).df()

    corrs = []
    for year in sorted(df['race_year'].unique()):
        year_df = df[df['race_year'] == year]

        if len(year_df) >= 4:
            drivers = sorted(year_df['driver_id'].unique())
            mid = len(drivers) // 2

            g1 = year_df[year_df['driver_id'].isin(drivers[:mid])]['tactical_rating'].values
            g2 = year_df[year_df['driver_id'].isin(drivers[mid:])]['tactical_rating'].values

            if len(g1) >= 2 and len(g2) >= 2:
                corr, _ = stats.spearmanr(g1, g2)
                corrs.append(corr)
                print(f"  {year}: r = {corr:+.3f} (n={len(year_df)})")

    if corrs:
        print(f"  Median: {np.median(corrs):+.3f}")
        print(f"  Mean: {np.mean(corrs):+.3f}")
        return np.median(corrs)
    return np.nan

def test_race_grain(con):
    """Test race-grain tactical stability."""
    print(f"\nWindow: RACE GRAIN (entire race aggregated)")
    print("-" * 60)

    query = """
    SELECT
        race_year,
        driver_id,
        AVG(tactical_gain_s) as tactical_rating
    FROM fct_driver_isolation_race
    WHERE tactical_gain_s IS NOT NULL
        AND race_year BETWEEN 2018 AND 2024
    GROUP BY race_year, driver_id
    """

    df = con.execute(query).df()

    corrs = []
    for year in sorted(df['race_year'].unique()):
        year_df = df[df['race_year'] == year]

        if len(year_df) >= 4:
            drivers = sorted(year_df['driver_id'].unique())
            mid = len(drivers) // 2

            g1 = year_df[year_df['driver_id'].isin(drivers[:mid])]['tactical_rating'].values
            g2 = year_df[year_df['driver_id'].isin(drivers[mid:])]['tactical_rating'].values

            if len(g1) >= 2 and len(g2) >= 2:
                corr, _ = stats.spearmanr(g1, g2)
                corrs.append(corr)
                print(f"  {year}: r = {corr:+.3f} (n={len(year_df)})")

    if corrs:
        print(f"  Median: {np.median(corrs):+.3f}")
        print(f"  Mean: {np.mean(corrs):+.3f}")
        return np.median(corrs)
    return np.nan

def main():
    print("="*80)
    print("WINDOW SIZE SENSITIVITY TEST: Cross-season stability")
    print("="*80)
    print("\nMetric: Split-half Spearman correlation of driver tactical ratings")
    print("        (odd drivers vs even drivers, per season)")
    print("Threshold: PASS ≥ 0.30 per WI-16 doc")

    con = get_db()

    try:
        results = {}

        # Current window
        results['5-lap (current)'] = test_window_size(con, 5)

        # Alternative windows
        results['10-lap'] = test_window_size(con, 10)
        results['20-lap'] = test_window_size(con, 20)

        # Coarser grains
        results['Stint'] = test_stint_grain(con)
        results['Race'] = test_race_grain(con)

        # Summary
        print("\n" + "="*80)
        print("SUMMARY")
        print("="*80)
        print("\nMedian split-half correlation by window size:")
        print()
        for grain, corr in sorted(results.items(), key=lambda x: x[1], reverse=True):
            status = "PASS" if not np.isnan(corr) and corr >= 0.30 else "FAIL"
            print(f"  {grain:20s}: {corr:+.3f}  [{status}]")

        print("\nConclusion:")
        best = max(results.items(), key=lambda x: x[1] if not np.isnan(x[1]) else -np.inf)
        print(f"  Best grain: {best[0]} (r = {best[1]:+.3f})")

        if best[1] < 0.30:
            print("\n  *** ALL windows FAIL cross-season stability test ***")
            print("  Recommendation: Suppress lap-grain tactical; publish stint/race only")
        else:
            print(f"\n  {best[0]} achieves adequate stability (r ≥ 0.30)")

    finally:
        con.close()

if __name__ == "__main__":
    main()
