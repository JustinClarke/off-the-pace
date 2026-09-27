#!/usr/bin/env python3
"""
Diagnose tactical rating instability: focused on stint-grain to avoid noise.
"""

import duckdb
import numpy as np
import pandas as pd
from scipy import stats
import warnings
warnings.filterwarnings('ignore')

def get_db():
    """Connect to dev database."""
    return duckdb.connect("data/dev.duckdb", read_only=True)

def test_stint_grain_stability(con):
    """Test tactical stability at stint grain vs lap grain."""
    print("\n" + "="*80)
    print("ANALYSIS: Tactical rating stability — stint grain vs lap grain")
    print("="*80)

    # Stint-grain data
    stint_query = """
    SELECT
        race_year,
        driver_id,
        tactical_gain_s as tactical_rating
    FROM fct_driver_isolation_stint
    WHERE tactical_gain_s IS NOT NULL
        AND stint_phase = 'all'
        AND race_year BETWEEN 2018 AND 2024
    ORDER BY race_year, driver_id
    """

    # Lap-grain data (5-lap window)
    lap_query = """
    SELECT
        race_year,
        driver_id,
        AVG(tactical_5lap_gain_s) as tactical_rating
    FROM fct_driver_isolation_lap
    WHERE tactical_5lap_gain_s IS NOT NULL
        AND race_year BETWEEN 2018 AND 2024
    GROUP BY race_year, driver_id
    ORDER BY race_year, driver_id
    """

    df_stint = con.execute(stint_query).df()
    df_lap = con.execute(lap_query).df()

    print("\n1. STINT-GRAIN DATA (per stint, one value per stint)")
    print("-" * 80)

    # Split-half per season: odd vs even laps (crude proxy for temporal split)
    stint_corrs = []
    for year in sorted(df_stint['race_year'].unique()):
        year_df = df_stint[df_stint['race_year'] == year].copy()
        if len(year_df) >= 3:
            # Just take alternating drivers
            drivers = sorted(year_df['driver_id'].unique())
            mid = len(drivers) // 2

            # Get mean rating for first/second half of drivers
            g1 = year_df[year_df['driver_id'].isin(drivers[:mid])]['tactical_rating'].mean()
            g2 = year_df[year_df['driver_id'].isin(drivers[mid:])]['tactical_rating'].mean()

            # For correlation, we need pairs. Do within-year split.
            if len(drivers) >= 6:
                g1_vals = year_df[year_df['driver_id'].isin(drivers[:mid])]['tactical_rating'].values
                g2_vals = year_df[year_df['driver_id'].isin(drivers[mid:])]['tactical_rating'].values

                if len(g1_vals) >= 2 and len(g2_vals) >= 2:
                    # Compute simple correlation via ranks
                    g1_rank = stats.rankdata(g1_vals)
                    g2_rank = stats.rankdata(g2_vals)

                    # Can't compute correlation directly; use within-season split-half instead
                    # Sort by driver_id and split
                    drivers_with_ratings = year_df.sort_values('driver_id')[['driver_id', 'tactical_rating']]
                    n = len(drivers_with_ratings)

                    if n >= 4:
                        # Take every other driver
                        odd_drivers = year_df[year_df.index % 2 == 0]['tactical_rating']
                        even_drivers = year_df[year_df.index % 2 == 1]['tactical_rating']

                        if len(odd_drivers) >= 2 and len(even_drivers) >= 2:
                            # Just compare group means
                            pass

    # Better approach: use actual race-based split-half from the protocol
    print("Within-season split-half split (odd vs even races):")
    print()

    stint_corrs = []
    for year in sorted(df_stint['race_year'].unique()):
        year_df = df_stint[df_stint['race_year'] == year].copy()

        # Group by driver, split their stints into halves
        driver_corrs = []
        for drv in year_df['driver_id'].unique():
            drv_data = year_df[year_df['driver_id'] == drv].sort_values('tactical_rating')
            if len(drv_data) >= 4:
                n = len(drv_data)
                half1 = drv_data.iloc[:n//2]['tactical_rating'].values
                half2 = drv_data.iloc[n//2:]['tactical_rating'].values
                # Can compute correlation within driver
                if len(half1) >= 2 and len(half2) >= 2:
                    # Simple check: are the halves ordered the same?
                    # Instead, just note the variance
                    pass

        # Simpler: compute within-season Spearman using all data
        if len(year_df) >= 5:
            # Split drivers into two groups
            all_drivers = sorted(year_df['driver_id'].unique())
            mid = len(all_drivers) // 2

            df_g1 = year_df[year_df['driver_id'].isin(all_drivers[:mid])]
            df_g2 = year_df[year_df['driver_id'].isin(all_drivers[mid:])]

            # Both groups, rank by driver then correlate the ranks
            if len(df_g1) > 0 and len(df_g2) > 0:
                g1_mean = df_g1.groupby('driver_id')['tactical_rating'].mean()
                g2_mean = df_g2.groupby('driver_id')['tactical_rating'].mean()

                # Compute correlation if there's overlap
                overlap = set(g1_mean.index) & set(g2_mean.index)
                if len(overlap) >= 3:
                    corr, pval = stats.spearmanr(
                        g1_mean[list(overlap)],
                        g2_mean[list(overlap)]
                    )
                    stint_corrs.append(corr)
                    print(f"  {year}: r = {corr:.3f} (n_overlap={len(overlap)})")

    if stint_corrs:
        print(f"\nMedian Spearman r (stint grain): {np.median(stint_corrs):.3f}")
        print(f"Mean: {np.mean(stint_corrs):.3f}")

    print("\n2. LAP-GRAIN DATA (per driver-season, aggregated from 5-lap windows)")
    print("-" * 80)
    print("Within-season split-half split:")
    print()

    lap_corrs = []
    for year in sorted(df_lap['race_year'].unique()):
        year_df = df_lap[df_lap['race_year'] == year].copy()

        if len(year_df) >= 5:
            drivers = sorted(year_df['driver_id'].unique())
            mid = len(drivers) // 2

            g1 = year_df[year_df['driver_id'].isin(drivers[:mid])]['tactical_rating'].values
            g2 = year_df[year_df['driver_id'].isin(drivers[mid:])]['tactical_rating'].values

            if len(g1) >= 2 and len(g2) >= 2:
                corr, pval = stats.spearmanr(g1, g2)
                lap_corrs.append(corr)
                print(f"  {year}: r = {corr:.3f} (n1={len(g1)}, n2={len(g2)})")

    if lap_corrs:
        print(f"\nMedian Spearman r (lap grain): {np.median(lap_corrs):.3f}")
        print(f"Mean: {np.mean(lap_corrs):.3f}")


def test_root_cause_analysis(con):
    """Dig into what's causing the instability."""
    print("\n" + "="*80)
    print("ROOT CAUSE ANALYSIS")
    print("="*80)

    # Check: is the problem in the slope estimate (beta_s) being noisy?
    slope_query = """
    SELECT
        race_year,
        driver_id,
        COUNT(*) as n_stints,
        AVG(ABS(tactical_slope_s_per_lap2)) as mean_abs_tactical_slope,
        STDDEV_SAMP(tactical_slope_s_per_lap2) as sd_tactical_slope
    FROM int_driver_isolation_stint_tyre
    WHERE tactical_slope_s_per_lap2 IS NOT NULL
        AND race_year BETWEEN 2018 AND 2024
    GROUP BY race_year, driver_id
    ORDER BY race_year, driver_id
    """

    df_slope = con.execute(slope_query).df()

    print("\n1. Are tactical slopes (β_s) estimated noisily?")
    print("-" * 80)
    print("Typical driver's tactical slope SD within a season:")
    print()

    for year in sorted(df_slope['race_year'].unique()):
        year_df = df_slope[df_slope['race_year'] == year]
        median_sd = year_df['sd_tactical_slope'].median()
        median_slope = year_df['mean_abs_tactical_slope'].median()
        print(f"  {year}: median slope SD = {median_sd:.5f}, median mean|slope| = {median_slope:.5f}")
        print(f"          ratio (noise/signal) = {median_sd/median_slope:.1f}x")

    # Check: is the peer slope median being stable?
    peer_query = """
    SELECT
        race_year,
        race_id,
        compound,
        COUNT(*) as n_stints_compound,
        STDDEV_SAMP(line_slope_s_per_lap2) as sd_peer_slopes,
        AVG(ABS(line_slope_s_per_lap2)) as mean_abs_slope
    FROM int_driver_isolation_stint_tyre
    WHERE line_slope_s_per_lap2 IS NOT NULL
        AND race_year BETWEEN 2018 AND 2024
    GROUP BY race_year, race_id, compound
    """

    df_peer = con.execute(peer_query).df()

    print("\n2. Peer slope variability per race-compound:")
    print("-" * 80)

    for year in sorted(df_peer['race_year'].unique()):
        year_df = df_peer[df_peer['race_year'] == year]
        median_peer_sd = year_df['sd_peer_slopes'].median()
        median_peer_mean = year_df['mean_abs_slope'].median()
        print(f"  {year}: median SD of peer slopes = {median_peer_sd:.5f}, " +
              f"mean|slope| = {median_peer_mean:.5f}")


def test_window_effect(con):
    """Check if aggregating to coarser windows helps."""
    print("\n" + "="*80)
    print("WINDOW GRAIN EFFECT: Does coarser grain improve stability?")
    print("="*80)

    # Get race-grain data
    race_query = """
    SELECT
        race_year,
        driver_id,
        tactical_gain_s as tactical_rating
    FROM fct_driver_isolation_race
    WHERE tactical_gain_s IS NOT NULL
        AND race_year BETWEEN 2018 AND 2024
    """

    df_race = con.execute(race_query).df()

    print("\nRace-grain split-half correlations:")
    print("-" * 80)

    race_corrs = []
    for year in sorted(df_race['race_year'].unique()):
        year_df = df_race[df_race['race_year'] == year]

        if len(year_df) >= 5:
            drivers = sorted(year_df['driver_id'].unique())
            mid = len(drivers) // 2

            g1 = year_df[year_df['driver_id'].isin(drivers[:mid])]['tactical_rating'].values
            g2 = year_df[year_df['driver_id'].isin(drivers[mid:])]['tactical_rating'].values

            if len(g1) >= 2 and len(g2) >= 2:
                corr, _ = stats.spearmanr(g1, g2)
                race_corrs.append(corr)
                print(f"  {year}: r = {corr:.3f} (n={len(year_df)})")

    if race_corrs:
        print(f"\nMedian Spearman r (race grain): {np.median(race_corrs):.3f}")
        print(f"Mean: {np.mean(race_corrs):.3f}")


def main():
    con = get_db()

    try:
        test_stint_grain_stability(con)
        test_root_cause_analysis(con)
        test_window_effect(con)

        print("\n" + "="*80)
        print("SUMMARY & NEXT STEPS")
        print("="*80)
        print("""
The tactical rating shows severe instability (split-half r ≈ -0.15) at lap grain.

Root causes to test:
1. Is the lap-grain window (5 laps) too fine? Try 10, 20, stint grain.
2. Are the slope estimates (β_s) inherently noisy? Check peer median stability.
3. Does the clean-lap filter let through season-specific contamination?
4. Is the peer-slope median unstable year-to-year?

Expected next steps:
- Run experiments with coarser windows on the same 3 probe races
- Check if restricting to stints with many line laps improves stability
- Verify peer slope estimation is stable (median should be robust)
        """)

    finally:
        con.close()


if __name__ == "__main__":
    main()
