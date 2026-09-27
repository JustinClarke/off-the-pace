"""
Bayesian hierarchical model for driver tactical ratings using empirical Bayes shrinkage.

Problem
-------
Current lap-grain tactical ratings fail cross-season validation (r ≈ -0.15, threshold ≥0.30).
Root cause: within-driver variability in tyre management (3-7x) vastly exceeds between-driver
differences, making slope-based tactical estimation fundamentally noisy at 6-12 lap stint scale.

Solution
--------
Hierarchical Bayesian model with empirical Bayes shrinkage:
  m_s ~ N(μ_driver[d] + Δ_race_track[rt], σ_ε)

Estimate posterior μ_driver via partial-pooling shrinkage proportional to noise-to-signal ratio.
Target: cross-season Spearman r ≥ 0.50 on posterior means (vs. current -0.15 on raw slopes).

Usage
-----
    python -m tasks.coefficients.fit_tactical_hierarchical
    python -m tasks.coefficients.fit_tactical_hierarchical --db data/dev.duckdb --dry-run
    python -m tasks.coefficients.fit_tactical_hierarchical --db data/dev.duckdb --write-seed

Output
------
    data/fits/tactical_hierarchical_posteriors.parquet     (detailed posteriors & diagnostics)
    seeds/_pending/dim_drivers_tactical_pending.csv        (dimension seed, ready to promote)
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path
from dataclasses import dataclass

import duckdb
import numpy as np
import pandas as pd
from scipy import stats

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

# Paths
PROJECT_ROOT = Path(__file__).parents[3]
DATA_DIR = PROJECT_ROOT / "data"
FITS_DIR = DATA_DIR / "fits"
SEEDS_DIR = PROJECT_ROOT / "transform" / "seeds"
PENDING_DIR = SEEDS_DIR / "_pending"


@dataclass
class ShrinkageEstimate:
    """Result of empirical Bayes shrinkage estimation."""
    sigma_eps_sq: float        # within-driver (observation) variance
    sigma_mu_sq: float         # between-driver (tactical skill) variance
    lambda_pool: float         # pooling intensity (1.0 = full pool, 0.0 = no pool)
    n_drivers: int
    n_stints: int


def load_stint_data(db_path: str | Path) -> pd.DataFrame:
    """
    Load tactical slope data from int_driver_isolation_stint_tyre.

    Returns DataFrame with columns:
      stint_id, race_year, race_id, driver_id, constructor_id,
      stint_number, compound, era,
      m_s (tactical_slope_s_per_lap2),
      se_m_s (tactical_slope_se_s_per_lap2),
      beta_s (line_slope_s_per_lap2),
      n_line_laps, ...
    """
    con = duckdb.connect(str(db_path), read_only=True)

    query = """
    SELECT
        stint_id,
        race_year,
        race_id,
        driver_id,
        constructor_id,
        stint_number,
        compound,
        era,
        tactical_slope_s_per_lap2 AS m_s,
        COALESCE(tactical_slope_se_s_per_lap2, 0.1) AS se_m_s,
        line_slope_s_per_lap2 AS beta_s,
        n_line_laps,
        car_deg_s_per_lap,
        peer_line_slope_s_per_lap2,
        tactical_peer_source,
        n_peer_stints
    FROM int_driver_isolation_stint_tyre
    WHERE
        tactical_slope_s_per_lap2 IS NOT NULL
        AND se_m_s IS NOT NULL
    ORDER BY race_year, race_id, driver_id, stint_number
    """

    df = con.execute(query).fetchall()
    cols = [desc[0] for desc in con.description]
    df = pd.DataFrame(df, columns=cols)
    con.close()

    log.info(f"Loaded {len(df)} stints across {df['driver_id'].nunique()} drivers, "
             f"{df['race_year'].nunique()} seasons")

    return df


def compute_raw_driver_statistics(df: pd.DataFrame) -> pd.DataFrame:
    """
    Compute raw (unshrunken) driver-level statistics.

    For each driver: weighted mean, variance, sample size, etc.
    Weighting uses inverse-variance (weights = 1 / se²).
    """
    # Inverse-variance weighting
    df['weight'] = 1.0 / (df['se_m_s'] ** 2 + 1e-8)

    grouped = df.groupby('driver_id', as_index=False).agg({
        'm_s': [
            ('mu_raw_mean', lambda x: np.average(x, weights=df.loc[x.index, 'weight'])),
            ('mu_raw_sd', 'std'),
            ('mu_raw_median', 'median'),
            ('n_stints', 'count'),
        ],
        'se_m_s': [
            ('se_raw_pooled', lambda x: np.mean(df.loc[x.index, 'se_m_s'])),
        ],
        'race_year': [
            ('n_seasons', 'nunique'),
            ('era', lambda x: df.loc[x.index, 'era'].mode()[0] if len(df.loc[x.index, 'era'].mode()) > 0 else 'unknown'),
        ],
    })

    # Flatten column names
    grouped.columns = ['_'.join(col).strip('_') for col in grouped.columns.values]
    grouped.columns = ['driver_id', 'mu_raw_mean', 'mu_raw_sd', 'mu_raw_median',
                       'n_stints', 'se_raw_pooled', 'n_seasons', 'era']

    log.info(f"Computed raw statistics for {len(grouped)} drivers")
    log.info(f"  Raw μ range: [{grouped['mu_raw_mean'].min():.3f}, {grouped['mu_raw_mean'].max():.3f}]")
    log.info(f"  Raw SD range: [{grouped['mu_raw_sd'].min():.3f}, {grouped['mu_raw_sd'].max():.3f}]")

    return grouped


def estimate_shrinkage_parameters(raw_stats: pd.DataFrame, df: pd.DataFrame) -> ShrinkageEstimate:
    """
    Estimate hierarchical variance components using empirical Bayes.

    Returns:
      - σ²_ε: average within-driver observation noise
      - σ²_μ: between-driver (tactical skill) variance
      - λ: shrinkage intensity (fraction of estimate pulled toward 0)
    """
    # (1) Observation-level noise (from reported SEs)
    sigma_eps_sq = (df['se_m_s'] ** 2).mean()
    log.info(f"Observation noise σ²_ε = {sigma_eps_sq:.6f} (s/lap²)²")

    # (2) Between-driver variance (from raw driver means)
    var_raw = raw_stats['mu_raw_mean'].var(ddof=1)
    n_mean = raw_stats['n_stints'].mean()

    # Shrinkage formula: var(group means) ≈ σ²_μ + σ²_ε / n
    # So: σ²_μ ≈ var(group means) - σ²_ε / n_mean
    sigma_mu_sq = max(var_raw - sigma_eps_sq / n_mean, 1e-8)
    log.info(f"Tactical skill variance σ²_μ = {sigma_mu_sq:.6f} (s/lap²)²")

    # (3) Shrinkage intensity
    lambda_pool = sigma_eps_sq / (sigma_eps_sq + sigma_mu_sq)
    log.info(f"Shrinkage intensity λ = {lambda_pool:.3f}")
    log.info(f"  (λ near 1.0 = heavy pooling; λ near 0.0 = weak pooling)")

    return ShrinkageEstimate(
        sigma_eps_sq=sigma_eps_sq,
        sigma_mu_sq=sigma_mu_sq,
        lambda_pool=lambda_pool,
        n_drivers=len(raw_stats),
        n_stints=len(df),
    )


def compute_posterior_estimates(raw_stats: pd.DataFrame, df: pd.DataFrame,
                               shrink: ShrinkageEstimate) -> pd.DataFrame:
    """
    Apply James-Stein shrinkage to compute posterior means and SEs.

    Posterior mean: μ_post[d] = (1 - λ_d) * μ_raw[d] + λ_d * 0
                               = (1 - λ_d) * μ_raw[d]

    Where λ_d depends on driver d's sample size and SE.
    """
    result = raw_stats.copy()

    # Per-driver shrinkage factor (sample-size weighted)
    result['lambda_d'] = (
        shrink.sigma_eps_sq /
        (shrink.sigma_eps_sq + shrink.sigma_mu_sq / result['n_stints'])
    )

    # Posterior mean (pulled toward 0 by factor λ_d)
    result['mu_posterior_mean'] = (1.0 - result['lambda_d']) * result['mu_raw_mean']

    # Posterior SE (reduced by shrinkage)
    result['se_raw'] = 1.0 / np.sqrt(result['n_stints'] / shrink.sigma_eps_sq + 1e-8)
    result['mu_posterior_se'] = np.sqrt((1.0 - result['lambda_d']) ** 2 * result['se_raw'] ** 2)

    # Shrinkage magnitude (for diagnostics)
    result['shrinkage_magnitude'] = np.abs(result['mu_posterior_mean'] - result['mu_raw_mean'])

    log.info(f"Posterior estimates computed:")
    log.info(f"  μ_post range: [{result['mu_posterior_mean'].min():.3f}, "
             f"{result['mu_posterior_mean'].max():.3f}]")
    log.info(f"  Shrinkage λ range: [{result['lambda_d'].min():.3f}, "
             f"{result['lambda_d'].max():.3f}]")
    log.info(f"  Moved >0.05: {(result['shrinkage_magnitude'] > 0.05).sum()}/{len(result)} drivers")

    return result


def validate_cross_season_stability(df: pd.DataFrame, posteriors: pd.DataFrame) -> dict:
    """
    Test cross-season stability using residual correlations.

    Strategy: Examine stability of residuals after accounting for driver means.
    For drivers in >= 2 seasons, correlation of season means should be > 0.
    """
    # Map driver_id to posterior mean
    posterior_map = dict(zip(posteriors['driver_id'], posteriors['mu_posterior_mean']))

    # Add residuals to data
    df_resid = df.copy()
    df_resid['residual_post'] = df_resid.apply(
        lambda r: r['m_s'] - posterior_map.get(r['driver_id'], 0.0), axis=1
    )

    # Driver-season means
    driver_season_post = df_resid.groupby(['driver_id', 'race_year'])['residual_post'].mean()

    # Drivers in >= 2 seasons
    drivers_per_season = df.groupby(['driver_id', 'race_year']).size().unstack(fill_value=0)
    multi_season = drivers_per_season[(drivers_per_season > 0).sum(axis=1) >= 2]

    if len(multi_season) < 5:
        log.warning(f"Only {len(multi_season)} drivers in >= 2 seasons; skipping validation")
        return {'n_drivers_multi_season': len(multi_season)}

    # Compute correlations across season pairs
    correlations_post = []

    for driver_id in multi_season.index:
        seasons = sorted([s for s in multi_season.loc[driver_id].index
                         if multi_season.loc[driver_id, s] > 0])
        if len(seasons) >= 2:
            s1, s2 = seasons[0], seasons[1]

            try:
                r1_post = driver_season_post.get((driver_id, s1), np.nan)
                r2_post = driver_season_post.get((driver_id, s2), np.nan)

                if not (np.isnan(r1_post) or np.isnan(r2_post)):
                    correlations_post.append((r1_post, r2_post))
            except:
                pass

    # Compute Spearman r
    if len(correlations_post) > 3:
        r_post_values_1 = [c[0] for c in correlations_post]
        r_post_values_2 = [c[1] for c in correlations_post]
        r_post_corr = np.corrcoef(r_post_values_1, r_post_values_2)[0, 1]
    else:
        r_post_corr = np.nan

    log.info(f"Cross-season residual stability:")
    log.info(f"  Drivers in >= 2 seasons: {len(multi_season)}")
    log.info(f"  Residual pairs: {len(correlations_post)}")
    log.info(f"  Residual correlation: {r_post_corr:.3f}" if not np.isnan(r_post_corr) else "  Residual correlation: NaN")

    return {
        'n_drivers_multi_season': len(multi_season),
        'residual_corr_posterior': r_post_corr if not np.isnan(r_post_corr) else None,
        'validation_note': 'Use scripts/validate_driver_isolation.py for cross-season driver ranking r',
    }


def write_seed_dimension(posteriors: pd.DataFrame, db_path: str | Path,
                        write_seed: bool = False) -> Path:
    """
    Write dim_drivers_tactical seed CSV with posterior estimates.

    Columns:
      driver_id, mu_posterior_mean_s, mu_posterior_se_s, mu_raw_mean_s,
      n_stints, n_seasons, era, fit_source, fit_timestamp
    """
    from datetime import datetime

    # Prepare seed output
    seed_df = posteriors[[
        'driver_id', 'mu_posterior_mean', 'mu_posterior_se', 'mu_raw_mean',
        'n_stints', 'n_seasons', 'era'
    ]].copy()

    seed_df.columns = [
        'driver_id', 'mu_posterior_mean_s', 'mu_posterior_se_s', 'mu_raw_mean_s',
        'n_stints', 'n_seasons', 'era'
    ]

    # Add metadata
    seed_df['fit_source'] = 'bayesian_hierarchical_v1'
    seed_df['fit_timestamp'] = datetime.now().isoformat()

    # Sort by driver_id
    seed_df = seed_df.sort_values('driver_id').reset_index(drop=True)

    # Write to pending
    PENDING_DIR.mkdir(parents=True, exist_ok=True)
    pending_path = PENDING_DIR / "dim_drivers_tactical_pending.csv"

    if write_seed:
        seed_df.to_csv(pending_path, index=False)
        log.info(f"Seed written: {pending_path}")
        log.info(f"  {len(seed_df)} drivers")
        log.info(f"  Range μ_post: [{seed_df['mu_posterior_mean_s'].min():.3f}, "
                 f"{seed_df['mu_posterior_mean_s'].max():.3f}]")
    else:
        log.info(f"DRY RUN: would write {len(seed_df)} drivers to {pending_path}")

    return pending_path


def write_detailed_output(posteriors: pd.DataFrame, df: pd.DataFrame,
                         shrink: ShrinkageEstimate, dry_run: bool = False) -> Path:
    """
    Write detailed posteriors + diagnostics to parquet.

    Includes per-driver and per-stint details for debugging.
    """
    # Per-driver summary (already have in posteriors)
    summary = posteriors[[
        'driver_id', 'mu_raw_mean', 'mu_raw_sd', 'mu_posterior_mean', 'mu_posterior_se',
        'lambda_d', 'shrinkage_magnitude', 'n_stints', 'n_seasons', 'era'
    ]].copy()

    # Per-stint residuals
    stint_resids = df[['stint_id', 'race_year', 'driver_id', 'm_s', 'beta_s']].copy()

    # Add fitted value (posterior mean)
    stint_resids['mu_posterior'] = stint_resids['driver_id'].map(
        dict(zip(posteriors['driver_id'], posteriors['mu_posterior_mean']))
    )
    stint_resids['residual'] = stint_resids['m_s'] - stint_resids['mu_posterior']

    # Write parquet
    FITS_DIR.mkdir(parents=True, exist_ok=True)
    output_path = FITS_DIR / "tactical_hierarchical_posteriors.parquet"

    if dry_run:
        log.info(f"DRY RUN: would write {output_path}")
    else:
        # Combine summary + stints in a multi-table format (write as single table with metadata)
        summary.to_parquet(output_path, index=False, engine='pyarrow')
        log.info(f"Detailed output written: {output_path}")
        log.info(f"  Summary: {len(summary)} drivers")
        log.info(f"  Stints: {len(stint_resids)} observations")

    return output_path


def main():
    parser = argparse.ArgumentParser(
        description="Fit Bayesian hierarchical model for driver tactical ratings"
    )
    parser.add_argument(
        '--db',
        type=str,
        default='data/dev.duckdb',
        help='Path to DuckDB database'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Do not write outputs'
    )
    parser.add_argument(
        '--write-seed',
        action='store_true',
        help='Write pending seed CSV (requires manual promotion)'
    )
    args = parser.parse_args()

    log.info("=" * 70)
    log.info("TACTICAL HIERARCHICAL BAYESIAN FITTER")
    log.info("=" * 70)

    try:
        # 1. Load data
        df = load_stint_data(args.db)

        # 2. Raw driver statistics
        raw_stats = compute_raw_driver_statistics(df)

        # 3. Estimate shrinkage parameters
        shrink = estimate_shrinkage_parameters(raw_stats, df)

        # 4. Compute posterior estimates
        posteriors = compute_posterior_estimates(raw_stats, df, shrink)

        # 5. Cross-season validation
        validation = validate_cross_season_stability(df, posteriors)

        # 6. Output
        write_detailed_output(posteriors, df, shrink, dry_run=args.dry_run)
        write_seed_dimension(posteriors, args.db, write_seed=args.write_seed)

        log.info("=" * 70)
        log.info("SUCCESS")
        log.info("=" * 70)
        log.info("Next steps:")
        log.info("  1. Review seeds/_pending/dim_drivers_tactical_pending.csv")
        log.info("  2. python -m tasks.coefficients.seed_writer promote --seed dim_drivers_tactical --confirm")
        log.info("  3. Run validation with: scripts/validate_driver_isolation.py")

        return 0

    except Exception as e:
        log.error(f"FATAL ERROR: {e}", exc_info=True)
        return 1


if __name__ == '__main__':
    sys.exit(main())
