"""
Fit a weighted isotonic tyre-degradation curve + modulation coefficients for the
Degradation Simulator headline: observed deg → monotone, with dirty-air/temp physics.

What this produces
------------------
data/fits/degradation_isotonic.parquet
  grain: (circuit_id, era, compound, lap_in_stint)

  Isotonic base (P1.1):
    obs_deg_from_fresh_p10_mono_s  monotone-fitted p10
    obs_deg_from_fresh_p50_mono_s  monotone-fitted p50
    obs_deg_from_fresh_p90_mono_s  monotone-fitted p90

  Dirty-air multiplier (P1.2):
    dirty_air_deg_mult  [1.0, 1.15]; 1.0 when sign/significance gate fails

  Temp-window penalty (P1.3):
    temp_headroom_c        °C of ambient_temp_delta before penalty engages
    temp_penalty_s_per_deg s per °C past the headroom (small calibrated constant)

The app reads these columns from mart_degradation_history_envelope after P1.4 wires
the parquet in. The formula in transform.ts (post-P2.2):
    M = clamp(1 + (dirty_air_share>0 ? dirty_air_deg_mult−1 : 0)
                + temp_penalty_s_per_deg × max(0, temp_delta − temp_headroom_c),
              1.0, 1.5)
    tyre(k) = mono_p50(k) × M
    net(k)  = ref_green_pace + fuel(k) + tyre(k)

Design
------
• Isotonic base: IsotonicRegression(increasing=True, out_of_bounds='clip')
  fit on laps with n_observations ≥ N_FLOOR, n-weighted. Predict on all laps in the
  cell; sklearn clips beyond the training range (flat-hold). Quantiles sorted per lap.
• Dirty-air: within-(circuit, era, compound, race) centred contrast on deg_from_fresh,
  age_in_stint ≥ 6, clean dry laps. Positive + (n_dirty ≥ N_AIR_MIN and n_clean ≥
  N_AIR_MIN) → dirty_air_deg_mult = clamp(1 + contrast / ref_deg, 1.0, 1.15).
  Falls back to 1.0 (no bump) for noisy or negative-contrast cells.
• Temp penalty: per-compound calibrated headroom (softs overheat sooner) + fixed
  temp_penalty_s_per_deg = TEMP_PENALTY. Does NOT fit a raw linear temp→deg slope
  (which is non-monotone in the raw data a U-shaped confound).

Usage
-----
    python -m tasks.coefficients.fit_degradation_isotonic
    python -m tasks.coefficients.fit_degradation_isotonic --dry-run
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd
from sklearn.isotonic import IsotonicRegression

from .provenance import build_provenance

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).parents[3]
DB_PATH = REPO_ROOT / "data" / "dev.duckdb"
OUT_PATH = REPO_ROOT / "data" / "fits" / "degradation_isotonic.parquet"

# ── Regulation era boundary ───────────────────────────────────────────────────
# Must match dbt_project.yml vars.era_boundary (default 2022).
# Overridable via --era-boundary CLI arg; kept in sync with the dbt var so a
# one-line change to dbt_project.yml + this constant re-splits both pipelines.
ERA_BOUNDARY = 2022

# ── Isotonic fit parameters ──────────────────────────────────────────────────
# Minimum observations per lap to include in the isotonic fit. Laps below this
# threshold are skipped during fit; the sklearn clip (out_of_bounds='clip') then
# flat-holds the last fitted value beyond the thin survivor tail.
N_FLOOR = 10

# ── Dirty-air gate parameters ────────────────────────────────────────────────
# Minimum laps in each group (dirty/clean) for the contrast to be significant enough
# to use. Cells with fewer laps fall back to dirty_air_deg_mult = 1.0 (no bump).
N_AIR_MIN = 20
# Upper bound on the dirty-air multiplier. Keeps the slider honest even for
# extremely dirty-air circuits like Monaco where the raw contrast can be +0.8s.
DIRTY_AIR_MULT_MAX = 1.15
# Reference lap used to normalise the additive contrast into a multiplicative factor.
# Chosen to be mid-stint (laps typically have good n coverage here).
REF_LAP_FOR_NORM = 20

# ── Temp-penalty parameters (P1.3) ───────────────────────────────────────────
# °C of ambient_temp_delta before the overheating penalty engages per compound.
# Physically: softer compounds overheat sooner (narrower optimal window), so they
# get a smaller headroom. Calibrated to keep the slider effect in the ~0.1–0.3s
# range at max temp_delta = 30 °C (per SLIDERS in inputs.ts).
COMPOUND_HEADROOM_C: dict[str, float] = {
    "HARD":        15.0,
    "MEDIUM":      10.0,
    "SOFT":         5.0,
    "SUPERSOFT":    3.0,
    "ULTRASOFT":    2.0,
    "HYPERSOFT":    1.0,
    "INTERMEDIATE": 20.0,  # not meaningfully heat-limited in dry-condition terms
    "WET":          25.0,
    "_all":          8.0,  # conservative fallback (between MEDIUM and SOFT)
}
# s per °C of ambient_temp_delta past the headroom. Calibrated so SOFT at 30 °C
# delta yields ≈ 0.25 s and HARD at 30 °C yields ≈ 0.15 s in the "modestly
# interactive" range stated in the plan.
TEMP_PENALTY = 0.010

# ── Query to pull the raw envelope ──────────────────────────────────────────
ENVELOPE_QUERY = """
    SELECT
        circuit_id, era, compound, lap_in_stint, n_observations,
        obs_deg_from_fresh_p10_s,
        obs_deg_from_fresh_p50_s,
        obs_deg_from_fresh_p90_s
    FROM mart_degradation_history_envelope
    ORDER BY circuit_id, era, compound, lap_in_stint
"""

# ── Query to pull the clean lap panel for dirty-air coefficient ──────────────
DIRTY_AIR_QUERY = """
WITH base AS (
    SELECT
        dc.circuit_id,
        CASE WHEN lrd.race_year < {era_boundary} THEN 'pre2022' ELSE 'post2022' END AS era,
        lrd.compound,
        lrd.race_id,
        lrd.weight_corrected_lap_time AS wclt,
        lrd.age_in_stint,
        (lrd.dirty_air_intensity_lag1 > 0) AS in_dirty_air
    FROM int_lap_residual_decomposed lrd
    JOIN race_to_track rt
        ON CAST(REPLACE(lrd.race_id, '_', '') AS INTEGER) = rt.race_id
    JOIN dim_circuits dc
        ON rt.track_id = dc.circuit_key
    WHERE lrd.correction_weight = 1
      AND NOT lrd.is_major_outlier_lap
      AND lrd.rainfall_flag = FALSE
      AND lrd.weight_corrected_lap_time IS NOT NULL
      AND lrd.compound IS NOT NULL
),
ref_pace AS (
    SELECT circuit_id, era, compound,
           MEDIAN(wclt) AS ref_s
    FROM base
    WHERE age_in_stint <= 2
    GROUP BY circuit_id, era, compound
),
worn_laps AS (
    SELECT
        b.circuit_id, b.era, b.compound, b.race_id, b.in_dirty_air,
        b.wclt - rp.ref_s AS deg_from_fresh_s
    FROM base b
    JOIN ref_pace rp USING (circuit_id, era, compound)
    WHERE b.age_in_stint >= 6
),
centred AS (
    SELECT *,
           deg_from_fresh_s
               - AVG(deg_from_fresh_s) OVER (
                   PARTITION BY circuit_id, era, compound, race_id
               ) AS deg_centred
    FROM worn_laps
)
SELECT
    circuit_id, era, compound,
    AVG(CASE WHEN in_dirty_air     THEN deg_centred END) AS mean_deg_dirty,
    AVG(CASE WHEN NOT in_dirty_air THEN deg_centred END) AS mean_deg_clean,
    COUNT(CASE WHEN in_dirty_air     THEN 1 END) AS n_dirty,
    COUNT(CASE WHEN NOT in_dirty_air THEN 1 END) AS n_clean
FROM centred
GROUP BY circuit_id, era, compound
"""


# ── P1.1 Isotonic base fit ─────────────────────────────────────────────────

def fit_cell_isotonic(df: pd.DataFrame) -> pd.DataFrame:
    """
    Fit weighted isotonic regression for one (circuit_id, era, compound) cell.
    Returns a DataFrame with columns [lap_in_stint, p10_mono, p50_mono, p90_mono].
    """
    mask = df["n_observations"] >= N_FLOOR
    if mask.sum() < 2:
        # Too few laps above the floor → use raw values as-is but still sort quantiles
        rows = []
        for _, row in df.iterrows():
            p10, p50, p90 = sorted([
                row["obs_deg_from_fresh_p10_s"],
                row["obs_deg_from_fresh_p50_s"],
                row["obs_deg_from_fresh_p90_s"],
            ])
            rows.append({"lap_in_stint": int(row["lap_in_stint"]),
                         "p10_mono": p10, "p50_mono": p50, "p90_mono": p90})
        return pd.DataFrame(rows)

    x_train = df.loc[mask, "lap_in_stint"].values.astype(float)
    w_train  = df.loc[mask, "n_observations"].values.astype(float)
    x_all    = df["lap_in_stint"].values.astype(float)

    fitted: dict[str, np.ndarray] = {}
    for q in ("p10", "p50", "p90"):
        y = df.loc[mask, f"obs_deg_from_fresh_{q}_s"].values
        ir = IsotonicRegression(increasing=True, out_of_bounds="clip")
        ir.fit(x_train, y, sample_weight=w_train)
        fitted[q] = ir.predict(x_all)

    # Sort quantiles at each lap so p10 ≤ p50 ≤ p90 after independent fits.
    rows = []
    for i, lap in enumerate(df["lap_in_stint"].values):
        p10, p50, p90 = sorted([fitted["p10"][i], fitted["p50"][i], fitted["p90"][i]])
        rows.append({"lap_in_stint": int(lap), "p10_mono": p10, "p50_mono": p50, "p90_mono": p90})
    return pd.DataFrame(rows)


def fit_isotonic_base(envelope: pd.DataFrame) -> pd.DataFrame:
    """
    Fit isotonic regression for every (circuit_id, era, compound) cell.
    Returns a DataFrame at grain (circuit_id, era, compound, lap_in_stint) with
    columns: obs_deg_from_fresh_{p10,p50,p90}_mono_s.
    """
    log.info("Fitting isotonic base (N_FLOOR=%d) ...", N_FLOOR)
    parts = []
    cells = envelope.groupby(["circuit_id", "era", "compound"])
    for (circuit_id, era, compound), cell_df in cells:
        fitted = fit_cell_isotonic(cell_df.reset_index(drop=True))
        fitted["circuit_id"] = circuit_id
        fitted["era"] = era
        fitted["compound"] = compound
        parts.append(fitted)

    base = pd.concat(parts, ignore_index=True).rename(columns={
        "p10_mono": "obs_deg_from_fresh_p10_mono_s",
        "p50_mono": "obs_deg_from_fresh_p50_mono_s",
        "p90_mono": "obs_deg_from_fresh_p90_mono_s",
    })
    log.info("Isotonic base: %d rows across %d cells.", len(base), len(cells))
    return base


# ── P1.2 Dirty-air multiplier ──────────────────────────────────────────────

def compute_dirty_air_mult(
    air_df: pd.DataFrame,
    iso_base: pd.DataFrame,
) -> pd.DataFrame:
    """
    Compute dirty_air_deg_mult per (circuit_id, era, compound).
    The multiplier is 1.0 (no bump) unless:
      • contrast (dirty − clean centred deg) is positive
      • n_dirty ≥ N_AIR_MIN and n_clean ≥ N_AIR_MIN
    When the gate passes: mult = clamp(1 + contrast / ref_deg, 1.0, DIRTY_AIR_MULT_MAX).
    ref_deg is the isotonic-fitted p50 at REF_LAP_FOR_NORM (or nearest available lap).
    """
    log.info("Computing dirty-air multipliers (N_AIR_MIN=%d) ...", N_AIR_MIN)

    # Build a lookup: (circuit_id, era, compound) → ref_deg at REF_LAP_FOR_NORM
    p50_col = "obs_deg_from_fresh_p50_mono_s"
    ref_laps = iso_base.copy()
    # For each cell take the closest lap to REF_LAP_FOR_NORM with a fitted value
    ref_laps["lap_dist"] = (ref_laps["lap_in_stint"] - REF_LAP_FOR_NORM).abs()
    ref_laps = (
        ref_laps.sort_values("lap_dist")
        .drop_duplicates(subset=["circuit_id", "era", "compound"])
        [["circuit_id", "era", "compound", p50_col]]
        .rename(columns={p50_col: "ref_deg_s"})
    )

    merged = air_df.merge(ref_laps, on=["circuit_id", "era", "compound"], how="left")
    merged["contrast_s"] = merged["mean_deg_dirty"] - merged["mean_deg_clean"]

    def compute_mult(row: pd.Series) -> float:
        contrast = row["contrast_s"]
        n_dirty  = row["n_dirty"]
        n_clean  = row["n_clean"]
        ref_deg  = row.get("ref_deg_s", float("nan"))

        passes_gate = (
            contrast > 0
            and n_dirty >= N_AIR_MIN
            and n_clean >= N_AIR_MIN
            and not np.isnan(ref_deg)
            and abs(ref_deg) > 0.05  # guard against near-zero reference (no signal)
        )
        if not passes_gate:
            return 1.0

        raw_mult = 1.0 + contrast / abs(ref_deg)
        return float(np.clip(raw_mult, 1.0, DIRTY_AIR_MULT_MAX))

    merged["dirty_air_deg_mult"] = merged.apply(compute_mult, axis=1)

    n_bumped = (merged["dirty_air_deg_mult"] > 1.0).sum()
    log.info(
        "Dirty-air: %d/%d cells with mult > 1.0; range [%.4f, %.4f].",
        n_bumped, len(merged),
        merged["dirty_air_deg_mult"].min(),
        merged["dirty_air_deg_mult"].max(),
    )
    return merged[["circuit_id", "era", "compound", "dirty_air_deg_mult"]]


# ── P1.3 Temp-window penalty ───────────────────────────────────────────────

def compute_temp_penalty(envelope: pd.DataFrame) -> pd.DataFrame:
    """
    Emit per-(circuit_id, era, compound): temp_headroom_c and temp_penalty_s_per_deg.
    Uses the per-compound headroom table (softs overheat sooner → smaller headroom).
    Does NOT fit a raw linear temp→deg slope (non-monotone confound in raw data).
    """
    log.info("Computing temp-window penalty coefficients ...")
    cells = envelope[["circuit_id", "era", "compound"]].drop_duplicates()

    cells["temp_headroom_c"] = cells["compound"].map(
        lambda c: COMPOUND_HEADROOM_C.get(c, COMPOUND_HEADROOM_C["_all"])
    )
    cells["temp_penalty_s_per_deg"] = TEMP_PENALTY
    log.info("Temp penalty: %d cells; headroom range [%.1f, %.1f] °C.",
             len(cells), cells["temp_headroom_c"].min(), cells["temp_headroom_c"].max())
    return cells


# ── Spot-check against the accuracy basket ───────────────────────────────────

def spot_check_basket(iso_base: pd.DataFrame) -> None:
    """Log weighted MAE vs raw p50 for the 4 basket dry-compound cells."""
    basket = [
        ("red_bull_ring",              "post2022", "HARD"),
        ("autodromo_nazionale_monza",  "post2022", "HARD"),
        ("red_bull_ring",              "post2022", "MEDIUM"),
        ("yas_marina_circuit",         "post2022", "HARD"),
    ]
    for circuit_id, era, compound in basket:
        subset = iso_base[
            (iso_base.circuit_id == circuit_id)
            & (iso_base.era == era)
            & (iso_base.compound == compound)
        ]
        if subset.empty:
            log.warning("Basket cell not found: %s %s %s", circuit_id, era, compound)
            continue
        viols = int((subset["obs_deg_from_fresh_p50_mono_s"].diff().dropna() < 0).sum())
        log.info(
            "Basket %s %s %s: laps=%d  mono_viols=%d  p50@last=%.3fs",
            circuit_id[:20], era, compound,
            len(subset), viols,
            subset["obs_deg_from_fresh_p50_mono_s"].iloc[-1],
        )


# ── Main orchestration ────────────────────────────────────────────────────────

def run_fit(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    log.info("Loading envelope from %s ...", DB_PATH)
    envelope = con.execute(ENVELOPE_QUERY).fetchdf()
    log.info("Loaded %d envelope rows across %d cells.",
             len(envelope),
             envelope.groupby(["circuit_id", "era", "compound"]).ngroups)

    # P1.1 Isotonic base
    iso_base = fit_isotonic_base(envelope)
    spot_check_basket(iso_base)

    # P1.2 Dirty-air multiplier
    log.info("Loading clean lap panel for dirty-air coefficient ...")
    air_df = con.execute(DIRTY_AIR_QUERY.format(era_boundary=ERA_BOUNDARY)).fetchdf()
    log.info("Dirty-air panel: %d cells.", len(air_df))
    air_mult = compute_dirty_air_mult(air_df, iso_base)

    # P1.3 Temp-window penalty
    temp_pen = compute_temp_penalty(envelope)

    # ── Join all three onto the lap grain ────────────────────────────────────
    out = iso_base.merge(
        air_mult,
        on=["circuit_id", "era", "compound"],
        how="left",
    ).merge(
        temp_pen,
        on=["circuit_id", "era", "compound"],
        how="left",
    )

    # Fill any cells missing from the dirty-air panel (e.g., wet/rare compounds)
    out["dirty_air_deg_mult"] = out["dirty_air_deg_mult"].fillna(1.0)
    out["temp_headroom_c"] = out["temp_headroom_c"].fillna(COMPOUND_HEADROOM_C["_all"])
    out["temp_penalty_s_per_deg"] = out["temp_penalty_s_per_deg"].fillna(TEMP_PENALTY)

    # Provenance
    row = con.execute("SELECT MIN(race_year), MAX(race_year) FROM int_lap_residual_decomposed").fetchone()
    min_y, max_y = int(row[0]), int(row[1])
    prov = build_provenance(
        fit_method="degradation_isotonic_v1",
        season_min=min_y,
        season_max=max_y,
    )
    for k, v in prov.items():
        out[k] = v

    out = out.sort_values(["circuit_id", "era", "compound", "lap_in_stint"]).reset_index(drop=True)
    log.info(
        "Final parquet: %d rows, %d cells, %d columns.",
        len(out),
        out.groupby(["circuit_id", "era", "compound"]).ngroups,
        len(out.columns),
    )
    return out


def main(argv: list[str] | None = None) -> int:
    global ERA_BOUNDARY
    parser = argparse.ArgumentParser(
        description="Fit the isotonic tyre-degradation base + modulation coefficients."
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--era-boundary", type=int, default=ERA_BOUNDARY,
        help="Regulation-era split year (default %(default)s; must match dbt_project.yml vars.era_boundary)",
    )
    args = parser.parse_args(argv)

    if args.era_boundary != ERA_BOUNDARY:
        ERA_BOUNDARY = args.era_boundary
        log.info("era_boundary overridden → %d", ERA_BOUNDARY)

    if args.dry_run:
        log.info("DRY RUN would write %s", OUT_PATH)
        return 0

    con = duckdb.connect(str(DB_PATH), read_only=True)
    try:
        out = run_fit(con)
    finally:
        con.close()

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    out.to_parquet(OUT_PATH, index=False)
    log.info("Wrote %d rows → %s", len(out), OUT_PATH)
    return 0


if __name__ == "__main__":
    sys.exit(main())
