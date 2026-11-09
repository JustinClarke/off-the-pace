"""
WC-03 preparation: outcome-blind noise inventory on the registered pass table (pass "d").

    .venv/bin/python _roadmap/_wake-calibration/_evidence/WC-03-prep-2026-10-28/noise_counts.py \
        _roadmap/_wake-calibration/_artifacts/WC-01-pass-table-d  <out folder>

Rules (decision record wi/WC-03-lead-decisions-2026-10-28-DRAFT.md, L2): structural columns only. No
segment time, reference time, loss, speed or lap time is read. No pass is classified (no prepare_passes,
no pass_class), no loss trim is applied, no gate is run. Counts only.
"""

from __future__ import annotations

import glob
import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[4]
BRONZE = REPO / "data/bronze"
GAP_EDGES = np.array([0.0, 0.3, 0.5, 0.75, 1.0, 1.5, 2.0, 2.5, 3.0])
COLUMNS = ["season", "race_id", "race", "driver", "lap", "stint", "compound", "corner_id", "corner_class",
           "segment_basis", "gap_s", "gap_n", "clear_ahead", "behind_1s", "tag", "reason", "clean", "ref_status",
           "leader", "leader_lap", "leader_track_limits", "layout_changed", "circuit_info_season"]
FORBIDDEN = {"seg_time_s", "ref_time_s", "delta_time_s", "min_speed_kph", "apex_kph", "brake_offset_m"}
MAIN_FIT, OLDER_FIT = (2022, 2023, 2024), (2018, 2019, 2020)
# The 34 races flagged by the first WC-02 timing check (prereg section 2b); all stay in.
FIRST_CHECK_FLAGGED = {
    2018: ["azerbaijan", "chinese", "united_states"],
    2019: ["azerbaijan", "chinese", "german", "mexican", "russian", "united_states"],
    2020: ["austrian", "hungarian"], 2021: ["azerbaijan", "belgian"],
    2022: ["azerbaijan", "belgian", "japanese", "singapore", "united_states"],
    2023: ["azerbaijan", "belgian", "dutch", "las_vegas", "united_states"],
    2024: ["azerbaijan", "chinese", "las_vegas"],
    2025: ["azerbaijan", "bahrain", "belgian", "british", "chinese", "las_vegas", "saudi_arabian", "united_states"],
}


def load(pass_dir: Path) -> pd.DataFrame:
    assert not (set(COLUMNS) & FORBIDDEN)
    files = sorted(glob.glob(str(pass_dir / "pass_table_*.parquet")))
    return pd.concat([pd.read_parquet(f, columns=COLUMNS) for f in files], ignore_index=True)


def teams() -> pd.DataFrame:
    rows = []
    for f in sorted(glob.glob(str(BRONZE / "laps/season=*/race=*/*.parquet"))):
        if "session=" in f:
            continue
        d = pd.read_parquet(f, columns=["Driver", "Team", "race_id", "season"])
        rows.append(d)
    lap = pd.concat(rows, ignore_index=True)
    lap = lap.dropna(subset=["Driver"])
    t = (lap.groupby(["season", "race_id", "Driver"])["Team"]
         .agg(lambda s: s.mode().iloc[0] if s.notna().any() else None).reset_index())
    return t.rename(columns={"Driver": "driver", "Team": "team"})


def main(pass_dir: str, out: str) -> None:
    pass_dir, out = Path(pass_dir), Path(out)
    out.mkdir(parents=True, exist_ok=True)
    p = load(pass_dir)
    braking = p["segment_basis"] == "brake_onset"
    kept = p["reason"].isna()
    nca = kept & p["clear_ahead"].astype(bool)
    gap = p["gap_s"].to_numpy(dtype=float)
    yielding = p["tag"].fillna("").astype(str).isin({"yielding", "lapped+yielding"})
    following = braking & kept & ~nca & np.isfinite(gap) & (gap < 3.0)
    measured = p["ref_status"] == "measured"
    fit_pre = following & measured & ~yielding & (gap >= 0)
    p["bin"] = np.where(np.isfinite(gap) & (gap >= 0) & (gap < 3), np.searchsorted(GAP_EDGES, gap, "right") - 1, -1)
    lines = []

    def put(k, v):
        lines.append({"measure": k, "value": v})

    put("rows", len(p))
    put("rows_unique_race_driver_lap_corner", int(~p.duplicated(["race_id", "driver", "lap", "corner_id"]).any()))
    put("kept", int(kept.sum()))
    put("kept_braking", int((kept & braking).sum()))
    put("kept_flat_out", int((kept & ~braking).sum()))
    put("no_car_ahead_kept", int(nca.sum()))
    put("following_braking", int(following.sum()))
    put("following_braking_measured", int((following & measured).sum()))
    put("following_braking_negative_gap", int((following & (gap < 0)).sum()))
    put("following_braking_yielding", int((following & yielding).sum()))
    put("following_braking_lapped_tag", int((following & p["tag"].fillna("").str.startswith("lapped")).sum()))
    put("following_braking_leader_track_limits", int((following & p["leader_track_limits"].astype(bool)).sum()))
    put("following_braking_leader_other_lap", int((following & (p["lap"] != p["leader_lap"])).sum()))
    put("following_braking_gap_n_under_26", int((following & (p["gap_n"] < 26)).sum()))
    put("following_braking_gap_n_under_10", int((following & (p["gap_n"] < 10)).sum()))
    put("kept_no_stint", int((kept & p["stint"].isna()).sum()))
    put("kept_compound_unknown", int((kept & (p["compound"].fillna("UNKNOWN") == "UNKNOWN")).sum()))
    put("kept_behind_1s", int((kept & p["behind_1s"].astype(bool)).sum()))
    put("kept_layout_changed", int((kept & p["layout_changed"].astype(bool)).sum()))
    put("fit_eligible_pre_trim_main", int((fit_pre & p["season"].isin(MAIN_FIT)).sum()))
    put("fit_eligible_pre_trim_older", int((fit_pre & p["season"].isin(OLDER_FIT)).sum()))
    lv = p["race_id"].isin(p.loc[(p["season"] == 2024) & (p["race"] == "las_vegas_grand_prix"), "race_id"].unique())
    put("lv2024_passes", int(lv.sum()))
    put("lv2024_fit_eligible_pre_trim", int((lv & fit_pre).sum()))
    flagged = np.zeros(len(p), dtype=bool)
    for s, names in FIRST_CHECK_FLAGGED.items():
        flagged |= ((p["season"] == s) & p["race"].isin([f"{n}_grand_prix" for n in names])).to_numpy()
    put("first_check_flagged_races_found", int(p.loc[flagged, "race_id"].nunique()))
    put("first_check_flagged_fit_eligible_pre_trim_main", int((flagged & fit_pre & p["season"].isin(MAIN_FIT)).sum()))
    pd.DataFrame(lines).to_csv(out / "noise_summary.csv", index=False)

    # By season: following braking passes and measured share; fit-eligible before the trim.
    g = p.assign(following=following, measured_f=following & measured, fit_pre=fit_pre, nca=nca,
                 layout=kept & p["layout_changed"].astype(bool), ltl=following & p["leader_track_limits"].astype(bool))
    by_season = g.groupby("season").agg(
        races=("race_id", "nunique"), kept_no_car_ahead=("nca", "sum"), following_braking=("following", "sum"),
        following_braking_measured=("measured_f", "sum"), fit_eligible_pre_trim=("fit_pre", "sum"),
        following_leader_track_limits=("ltl", "sum"))
    by_season["share_following_measured"] = (by_season["following_braking_measured"]
                                             / by_season["following_braking"]).round(4)
    by_season.to_csv(out / "following_by_season.csv")

    # Fit-eligible before the trim, per era x class x bin: passes and distinct races (G7 foresight, not G7).
    rows = []
    for era, seasons in (("main", MAIN_FIT), ("older", OLDER_FIT)):
        sub = p[fit_pre & p["season"].isin(seasons)]
        for (cls, b), h in sub.groupby(["corner_class", "bin"]):
            rows.append({"era": era, "corner_class": cls, "bin": int(b), "gap_lower_s": GAP_EDGES[b],
                         "gap_upper_s": GAP_EDGES[b + 1], "passes": len(h), "races": h["race_id"].nunique(),
                         "corners": h[["race", "corner_id"]].drop_duplicates().shape[0]})
    pd.DataFrame(rows).to_csv(out / "fit_eligible_pre_trim_by_bin.csv", index=False)

    # Coverage per team (L5, count part): share of following braking passes with a measured reference.
    t = teams()
    m = p[following].merge(t, on=["season", "race_id", "driver"], how="left")
    m["team"] = m["team"].fillna("—")
    m["measured"] = m["ref_status"] == "measured"
    cov = m.groupby(["season", "team"]).agg(following_braking=("measured", "size"),
                                            measured=("measured", "sum")).reset_index()
    cov["share_measured"] = (cov["measured"] / cov["following_braking"]).round(4)
    cov.to_csv(out / "coverage_per_team.csv", index=False)
    print((out / "noise_summary.csv").read_text())


if __name__ == "__main__":
    main(*sys.argv[1:3])


def fit_population_flags(pass_dir: str, out: str) -> pd.DataFrame:
    """Main-era fit-eligible passes (before the loss trim) carrying each noise flag. Counts only."""
    p = load(Path(pass_dir))
    gap = p["gap_s"].to_numpy(dtype=float)
    y = p["tag"].fillna("").astype(str).isin({"yielding", "lapped+yielding"})
    fit = ((p["segment_basis"] == "brake_onset") & p["reason"].isna() & ~p["clear_ahead"].astype(bool)
           & np.isfinite(gap) & (gap >= 0) & (gap < 3) & (p["ref_status"] == "measured") & ~y)
    lv = (p["season"] == 2024) & (p["race"] == "las_vegas_grand_prix")
    flags = {
        "all": np.ones(len(p), dtype=bool),
        "lv2024_feed": lv.to_numpy(),
        "layout_changed_race": p["layout_changed"].astype(bool).to_numpy(),
        "leader_track_limits": p["leader_track_limits"].astype(bool).to_numpy(),
        "leader_lapped_car": (p["leader_lap"] < p["lap"]).to_numpy(),
        "leader_one_lap_up": (p["leader_lap"] > p["lap"]).to_numpy(),
        "gap_bin0_under_0p3s": (gap < 0.3),
    }
    rows = []
    for era, seasons in (("main", MAIN_FIT), ("older", OLDER_FIT)):
        base = fit & p["season"].isin(seasons)
        n = int(base.sum())
        for k, f in flags.items():
            c = int((base & f).sum())
            rows.append({"era": era, "flag": k, "fit_eligible_pre_trim": c, "share": round(c / n, 4),
                         "races": int(p.loc[base & f, "race_id"].nunique())})
    t = pd.DataFrame(rows)
    t.to_csv(Path(out) / "fit_population_flags.csv", index=False)
    return t
