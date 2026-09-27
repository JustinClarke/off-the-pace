#!/usr/bin/env python3
"""
Diagnose tactical rating instability: coefficient of variation, window sensitivity,
and clean-lap filter impact.
"""

import duckdb
import numpy as np
import pandas as pd
from scipy import stats
import argparse
from pathlib import Path

def get_db():
    """Connect to dev database."""
    return duckdb.connect("data/dev.duckdb", read_only=True)

def test_coefficient_of_variation(con):
    """Measure CV within vs across seasons for tactical ratings."""
    print("\n" + "="*80)
    print("1. COEFFICIENT OF VARIATION: within-season vs cross-season stability")
    print("="*80)

    # Get tactical ratings at window grain (most granular, most noisy)
    query = """
    SELECT
        race_year,
        driver_id,
        stint_id,
        tactical_5lap_gain_s as tactical_rating
    FROM fct_driver_isolation_lap
    WHERE tactical_5lap_gain_s IS NOT NULL
        AND race_year BETWEEN 2018 AND 2024
    ORDER BY race_year, driver_id
    """

    df = con.execute(query).df()

    # Per-season within-driver statistics
    print("\nWithin-season variability (per driver-season):")
    print("-" * 80)

    for year in sorted(df['race_year'].unique()):
        year_df = df[df['race_year'] == year]
        drivers = year_df['driver_id'].unique()

        # Compute CV per driver-season
        cvs = []
        for drv in drivers:
            drv_df = year_df[year_df['driver_id'] == drv]
            if len(drv_df) >= 5:  # Need samples
                mean = drv_df['tactical_rating'].mean()
                std = drv_df['tactical_rating'].std()
                cv = abs(std / mean) if abs(mean) > 0.001 else np.nan
                cvs.append(cv)

        if cvs:
            median_cv = np.nanmedian(cvs)
            mean_cv = np.nanmean(cvs)
            print(f"  {year}: median CV = {median_cv:.2f}, mean CV = {mean_cv:.2f} " +
                  f"(n_drivers={len(cvs)})")

    # Cross-season variability for consistent drivers
    print("\nCross-season variability (drivers appearing in ≥2 seasons):")
    print("-" * 80)

    drivers_per_season = df.groupby(['driver_id', 'race_year'])['tactical_rating'].mean().reset_index()
    multi_season_drivers = drivers_per_season.groupby('driver_id').size()
    multi_season_drivers = multi_season_drivers[multi_season_drivers >= 2].index.tolist()

    cross_season_changes = []
    for drv in multi_season_drivers:
        drv_data = drivers_per_season[drivers_per_season['driver_id'] == drv].sort_values('race_year')
        if len(drv_data) >= 2:
            for i in range(1, len(drv_data)):
                prev = drv_data.iloc[i-1]['tactical_rating']
                curr = drv_data.iloc[i]['tactical_rating']
                change = abs(curr - prev)
                cross_season_changes.append(change)

    if cross_season_changes:
        print(f"  Median year-to-year change: {np.median(cross_season_changes):.4f} s")
        print(f"  Mean year-to-year change: {np.mean(cross_season_changes):.4f} s")
        print(f"  95th percentile: {np.percentile(cross_season_changes, 95):.4f} s")


def test_window_size_sensitivity(con):
    """Test different window sizes and measure cross-season correlation."""
    print("\n" + "="*80)
    print("2. WINDOW SIZE SENSITIVITY")
    print("="*80)

    window_sizes = [5, 10, 20]

    for window_size in window_sizes:
        print(f"\n  Testing window size = {window_size} laps:")
        print(f"  {'-'*76}")

        # Simulate window aggregation (crude: just use rolling mean on the lap-grain data)
        query = f"""
        WITH driver_season_avg AS (
            SELECT
                race_year,
                driver_id,
                -- Approximate coarser grain by using stint-level aggregation
                AVG(tactical_5lap_gain_s) as tactical_rating
            FROM fct_driver_isolation_lap
            WHERE tactical_5lap_gain_s IS NOT NULL
                AND race_year BETWEEN 2018 AND 2024
            GROUP BY race_year, driver_id
        ),
        split_half AS (
            SELECT
                race_year,
                driver_id,
                AVG(CASE WHEN driver_id % 2 = 0 THEN tactical_rating END) as half1,
                AVG(CASE WHEN driver_id % 2 = 1 THEN tactical_rating END) as half2
            FROM driver_season_avg
            GROUP BY race_year, driver_id
        )
        SELECT * FROM driver_season_avg LIMIT 1
        """

        # For now, use stint aggregation as proxy for different grain
        query = """
        SELECT
            race_year,
            driver_id,
            AVG(tactical_5lap_gain_s) as tactical_rating
        FROM fct_driver_isolation_lap
        WHERE tactical_5lap_gain_s IS NOT NULL
            AND race_year BETWEEN 2018 AND 2024
        GROUP BY race_year, driver_id, stint_id
        """

        df = con.execute(query).df()

        # Split-half per season
        for year in sorted(df['race_year'].unique()):
            year_df = df[df['race_year'] == year]
            drivers = year_df.groupby('driver_id').size()

            # Use odd/even stints as proxy for split-half
            year_df['stint_rank'] = year_df.groupby('driver_id').cumcount()
            odd_df = year_df[year_df['stint_rank'] % 2 == 0].groupby('driver_id')['tactical_rating'].mean()
            even_df = year_df[year_df['stint_rank'] % 2 == 1].groupby('driver_id')['tactical_rating'].mean()

            merged = pd.DataFrame({
                'odd': odd_df,
                'even': even_df
            }).dropna()

            if len(merged) >= 3:
                corr, _ = stats.spearmanr(merged['odd'], merged['even'])
                print(f"    {year}: Spearman r = {corr:.3f} (n={len(merged)})")


def test_clean_lap_filter_impact(con):
    """Test impact of excluding restart+1 laps on tactical stability."""
    print("\n" + "="*80)
    print("3. CLEAN-LAP FILTER IMPACT: Does excluding restart+1 improve stability?")
    print("="*80)

    # Current clean filter (Ω)
    current_query = """
    SELECT
        race_year,
        driver_id,
        AVG(tactical_5lap_gain_s) as tactical_rating
    FROM fct_driver_isolation_lap
    WHERE tactical_5lap_gain_s IS NOT NULL
        AND race_year BETWEEN 2018 AND 2024
    GROUP BY race_year, driver_id
    HAVING COUNT(*) >= 8
    ORDER BY race_year, driver_id
    """

    df_current = con.execute(current_query).df()

    # Test split-half on current
    print("\nCurrent filter (Ω from WI-16):")
    print("-" * 80)
    current_corrs = []
    for year in sorted(df_current['race_year'].unique()):
        year_df = df_current[df_current['race_year'] == year]

        # Naive split on driver_id parity
        odd = year_df[year_df['driver_id'].str.slice(-1).astype(int) % 2 == 0]
        even = year_df[year_df['driver_id'].str.slice(-1).astype(int) % 2 == 1]

        merged = pd.merge(
            odd[['driver_id', 'tactical_rating']].rename(columns={'tactical_rating': 'r_odd'}),
            even[['driver_id', 'tactical_rating']].rename(columns={'tactical_rating': 'r_even'}),
            on='driver_id',
            how='inner'
        )

        if len(merged) >= 3:
            corr, _ = stats.spearmanr(merged['r_odd'], merged['r_even'])
            current_corrs.append(corr)
            print(f"  {year}: Spearman r = {corr:.3f}")

    if current_corrs:
        print(f"  Median: {np.median(current_corrs):.3f}")


def test_team_order_and_upgrades(con):
    """Check if teammate stability suggests car/upgrade confounding."""
    print("\n" + "="*80)
    print("4. TEAMMATE STABILITY: Are stable teammate pairs also stable tactically?")
    print("="*80)

    query = """
    SELECT
        race_year,
        race_id,
        driver_id,
        constructor_id,
        lap_number,
        tactical_5lap_gain_s,
        pure_skill_5lap_gain_s
    FROM fct_driver_isolation_lap
    WHERE tactical_5lap_gain_s IS NOT NULL
        AND pure_skill_5lap_gain_s IS NOT NULL
        AND race_year BETWEEN 2018 AND 2024
    ORDER BY race_year, race_id, constructor_id, driver_id, lap_number
    """

    df = con.execute(query).df()

    # Find teammate pairs
    pair_stats = []
    for year in sorted(df['race_year'].unique()):
        for race_id in df[df['race_year'] == year]['race_id'].unique():
            race_df = df[(df['race_year'] == year) & (df['race_id'] == race_id)]

            # Find teams with 2+ drivers
            teams = race_df.groupby('constructor_id')
            for team_id, team_df in teams:
                drivers = team_df['driver_id'].unique()
                if len(drivers) >= 2:
                    # Get teammate with most data
                    d1_df = team_df[team_df['driver_id'] == drivers[0]]
                    d2_df = team_df[team_df['driver_id'] == drivers[1]]

                    if len(d1_df) >= 3 and len(d2_df) >= 3:
                        gap_tactical = abs(d1_df['tactical_5lap_gain_s'].mean() -
                                          d2_df['tactical_5lap_gain_s'].mean())
                        gap_pure = abs(d1_df['pure_skill_5lap_gain_s'].mean() -
                                      d2_df['pure_skill_5lap_gain_s'].mean())

                        pair_stats.append({
                            'year': year,
                            'team': team_id,
                            'tactical_gap': gap_tactical,
                            'pure_gap': gap_pure,
                            'ratio_tactical_to_pure': gap_tactical / gap_pure if gap_pure > 0.001 else np.nan
                        })

    if pair_stats:
        pair_df = pd.DataFrame(pair_stats)
        print(f"\n  Teammate tactical gaps (within same team, same race):")
        print(f"    Median gap: {pair_df['tactical_gap'].median():.4f} s")
        print(f"    Mean gap: {pair_df['tactical_gap'].mean():.4f} s")
        print(f"    Tactical:Pure gap ratio median: {pair_df['ratio_tactical_to_pure'].median():.2f}")
        print(f"    (ratio > 1 suggests tactical is noisier)")


def test_stint_vs_race_grain(con):
    """Compare cross-season stability at stint vs race grain."""
    print("\n" + "="*80)
    print("5. GRAIN COMPARISON: Stint vs Race grain cross-season stability")
    print("="*80)

    # Stint-grain
    stint_query = """
    SELECT
        race_year,
        driver_id,
        AVG(tactical_gain_s) as tactical_rating
    FROM fct_driver_isolation_stint
    WHERE tactical_gain_s IS NOT NULL
        AND stint_phase = 'all'
        AND race_year BETWEEN 2018 AND 2024
    GROUP BY race_year, driver_id
    HAVING COUNT(*) >= 3
    """

    # Race-grain
    race_query = """
    SELECT
        race_year,
        driver_id,
        tactical_gain_s as tactical_rating
    FROM fct_driver_isolation_race
    WHERE tactical_gain_s IS NOT NULL
        AND race_year BETWEEN 2018 AND 2024
    """

    print("\nStint-grain split-half:")
    print("-" * 80)
    try:
        df_stint = con.execute(stint_query).df()
        stint_corrs = []
        for year in sorted(df_stint['race_year'].unique()):
            year_df = df_stint[df_stint['race_year'] == year]
            if len(year_df) >= 3:
                # Crude split: first half vs second half drivers
                drivers = sorted(year_df['driver_id'].unique())
                mid = len(drivers) // 2
                half1 = year_df[year_df['driver_id'].isin(drivers[:mid])]['tactical_rating']
                half2 = year_df[year_df['driver_id'].isin(drivers[mid:])]['tactical_rating']

                if len(half1) >= 2 and len(half2) >= 2:
                    corr, _ = stats.spearmanr(
                        year_df[year_df['driver_id'].isin(drivers[:mid])]['tactical_rating'],
                        year_df[year_df['driver_id'].isin(drivers[mid:])]['tactical_rating']
                    )
                    stint_corrs.append(corr)
                    print(f"  {year}: {corr:.3f}")

        if stint_corrs:
            print(f"  Median: {np.median(stint_corrs):.3f}")
    except Exception as e:
        print(f"  Error: {e}")

    print("\nRace-grain split-half:")
    print("-" * 80)
    try:
        df_race = con.execute(race_query).df()
        race_corrs = []
        for year in sorted(df_race['race_year'].unique()):
            year_df = df_race[df_race['race_year'] == year]
            if len(year_df) >= 3:
                drivers = sorted(year_df['driver_id'].unique())
                mid = len(drivers) // 2

                corr, _ = stats.spearmanr(
                    year_df[year_df['driver_id'].isin(drivers[:mid])]['tactical_rating'],
                    year_df[year_df['driver_id'].isin(drivers[mid:])]['tactical_rating']
                )
                race_corrs.append(corr)
                print(f"  {year}: {corr:.3f}")

        if race_corrs:
            print(f"  Median: {np.median(race_corrs):.3f}")
    except Exception as e:
        print(f"  Error: {e}")


def main():
    parser = argparse.ArgumentParser(description="Diagnose tactical rating instability")
    args = parser.parse_args()

    con = get_db()

    try:
        test_coefficient_of_variation(con)
        test_window_size_sensitivity(con)
        test_clean_lap_filter_impact(con)
        test_team_order_and_upgrades(con)
        test_stint_vs_race_grain(con)

        print("\n" + "="*80)
        print("SUMMARY")
        print("="*80)
        print("""
Key findings to analyze:
1. Is CV high within-season? (suggests tactical measurement is noisy per lap)
2. Is CV stable across seasons? (suggests a systematic shift year-to-year)
3. Does coarser grain (stint/race) show better stability? (window too fine)
4. Are teammate tactical gaps large relative to pure? (suggests noisiness)
5. Does excluding restart+1 improve stability? (filter lets through artefacts)
        """)

    finally:
        con.close()


if __name__ == "__main__":
    main()
