"""
WC-03 / WC-04 report-only pieces of the scorecard (§12b, §15 Table 2): coverage per team and the contest per
team, the §12b counts, the older-car figures, mixed stints, each candidate's gain over no traffic term, the
under-attack difference, and the text of Table 2. Never a verdict input; never "pass" or "fail"; unavailable
is "—" with a reason, never 0 (rule 7). The WC-03/WC-04 scorecard has no modelled value (A4 ruling 4f).

Rules: pre-registration §5 "Coverage per team", §8d, §12b, §15; decision records L5, L6
(wi/WC-03-lead-decisions-2026-10-28-DRAFT.md, DRAFT, Opus-delegated).

SYNTHETIC ONLY; NOT RUN ON REAL DATA (tests/test_report.py). Apart from lap_info_from_bronze, which reads bronze
lap files when the run calls it, these are pure functions.
"""

from __future__ import annotations

import glob
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd

from tasks.wake_calibration import contest as C
from tasks.wake_calibration import estimator as E

UNAVAILABLE = C.UNAVAILABLE
TABLE2_TITLE = "Table 2 (context, never a verdict input; figures, never pass or fail)"


# --------------------------------------------------------------------------- bronze lap info (L5)


def lap_info_from_bronze(bronze: Path, seasons: Iterable[int]) -> pd.DataFrame:
    """season, race_id, driver, lap, team, position from bronze race laps (session= folders skipped)."""
    want = set(int(s) for s in seasons)
    frames = []
    for f in sorted(glob.glob(str(Path(bronze) / "laps/season=*/race=*/*.parquet"))):
        if "session=" in f:
            continue
        season = int(Path(f).parent.parent.name.split("=")[1])
        if season not in want:
            continue
        d = pd.read_parquet(f, columns=["Driver", "LapNumber", "Team", "Position", "race_id", "season"])
        frames.append(d)
    cols = ["season", "race_id", "driver", "lap", "team", "position"]
    if not frames:
        return pd.DataFrame(columns=cols)
    d = pd.concat(frames, ignore_index=True).dropna(subset=["Driver", "LapNumber"])
    return pd.DataFrame({"season": d["season"].astype(int), "race_id": d["race_id"].astype(str),
                         "driver": d["Driver"].astype(str), "lap": d["LapNumber"].astype(int),
                         "team": d["Team"], "position": d["Position"]})[cols]


def team_map(lap_info: pd.DataFrame) -> pd.DataFrame:
    """season, race_id, driver -> team (most frequent value; "—" if none)."""
    def mode(s):
        s = s.dropna()
        return s.mode().iloc[0] if len(s) else UNAVAILABLE
    return lap_info.groupby(["season", "race_id", "driver"])["team"].agg(mode).reset_index()


# --------------------------------------------------------------------------- coverage per team (§5, L5)


def following_braking(prepared: pd.DataFrame) -> pd.Series:
    """§5 following braking passes: braking corner, reason NULL, not no_car_ahead, finite gap_s < 3.0."""
    gap = prepared["gap_s"].to_numpy(dtype=float)
    return ((prepared["segment_basis"] == E.BRAKING_BASIS) & prepared["reason"].isna()
            & prepared["reason_wc03"].isna() & np.isfinite(gap) & (gap < E.FOLLOW_MAX_GAP_S))


def coverage_per_team(prepared: pd.DataFrame, teams: pd.DataFrame,
                      scored_laps: pd.DataFrame | None = None) -> pd.DataFrame:
    """Per season and team: following braking passes and the share with a measured reference; with the scored
    laps (held-out season), also scored laps and the share in the clean-reference half."""
    f = prepared[following_braking(prepared)]
    m = f[["season", "race_id", "driver", "ref_status"]].merge(teams, on=["season", "race_id", "driver"], how="left")
    m["team"] = m["team"].fillna(UNAVAILABLE)
    m["measured"] = m["ref_status"] == "measured"
    out = m.groupby(["season", "team"]).agg(following_braking_passes=("measured", "size"),
                                            measured=("measured", "sum")).reset_index()
    out["share_following_measured"] = out["measured"] / out["following_braking_passes"]
    if scored_laps is not None and len(scored_laps):
        s = scored_laps[["season", "race_id", "driver", "clean_reference"]].merge(
            teams, on=["season", "race_id", "driver"], how="left")
        s["team"] = s["team"].fillna(UNAVAILABLE)
        sl = s.groupby(["season", "team"]).agg(scored_laps=("clean_reference", "size"),
                                               clean_reference_laps=("clean_reference", "sum")).reset_index()
        sl["share_scored_clean_reference"] = sl["clean_reference_laps"] / sl["scored_laps"]
        out = out.merge(sl, on=["season", "team"], how="outer")
    return out


def contest_per_team(res: C.EraResult, teams: pd.DataFrame) -> pd.DataFrame:
    """§12b "the contest result per team": point MSEs and R_flat, R_now on each team's scored laps (the §8b
    residual is taken over all scored laps, then each team's laps are scored). No interval and no minimum are
    registered for teams, so none is given; a team with no scored lap is absent, not 0."""
    if res.contest is None or res.scored is None or res.design is None:
        return pd.DataFrame(columns=["team", "laps", "races", "r_flat", "r_now"])
    laps = res.scored.laps
    t = laps[["season", "race_id", "driver"]].merge(teams, on=["season", "race_id", "driver"], how="left")
    team = t["team"].fillna(UNAVAILABLE).to_numpy()
    y = laps["partial_residual_s"].to_numpy(dtype=float)
    x = {"none": np.zeros(len(laps)), "flat": laps["x_flat"].to_numpy(dtype=float),
         "now": E.flat_now(laps["dirty_air_share_lap"].to_numpy(dtype=float), res.contest.theta_point),
         "measured": res.design @ C.curve_array(res.main_table).ravel()}
    masks = {k: team == k for k in sorted(set(team))}
    sc = C.score(y, x, laps["stint_id"].to_numpy(), laps["age_bin"].to_numpy(), masks)
    rows = []
    for k, r in sc.items():
        rows.append({"team": k, "laps": int(r["laps"]), "races": int(laps.loc[masks[k], "race_id"].nunique()),
                     "mse_flat": r["mse_flat"], "mse_now": r["mse_now"], "mse_measured": r["mse_measured"],
                     "r_flat": r["r_flat"], "r_now": r["r_now"]})
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------- §12b counts


def no_car_ahead_counts(prepared: pd.DataFrame, lap_info: pd.DataFrame | None = None) -> pd.DataFrame:
    """§12b: no_car_ahead passes per season and corner class, and for the race leader (position 1 on that lap,
    from bronze laps; "—" when positions are not given)."""
    nca = prepared[prepared["reason_wc03"] == E.NO_CAR_AHEAD]
    out = nca.groupby(["season", "corner_class"]).size().rename("no_car_ahead_passes").reset_index()
    if lap_info is not None and len(lap_info):
        lead = lap_info.loc[lap_info["position"] == 1, ["season", "race_id", "driver", "lap"]].assign(leader_p1=True)
        m = nca.merge(lead, on=["season", "race_id", "driver", "lap"], how="left")
        p1 = m[m["leader_p1"].eq(True)].groupby(["season", "corner_class"]).size().rename("of_which_race_leader")
        out = out.join(p1, on=["season", "corner_class"])
        out["of_which_race_leader"] = out["of_which_race_leader"].fillna(0).astype(int)
    else:
        out["of_which_race_leader"] = UNAVAILABLE
    return out


def class_bin_counts(prepared: pd.DataFrame) -> pd.DataFrame:
    """§12b: following braking passes per pass class, gap bin, season and race (gap < 0: bin 'racecraft_neg')."""
    f = prepared[prepared["pass_class"].notna()].copy()
    f["bin"] = np.where(f["gap_s"] < 0, "negative_gap", f["gap_bin"].astype(str))
    return f.groupby(["season", "race_id", "pass_class", "bin"]).size().rename("passes").reset_index()


# --------------------------------------------------------------------------- Table 2 rows


def _fmt(v: float, nd: int = 4, reason: str = "not computable") -> str:
    return C.fmt(v, nd, reason)


def _interval(draws: np.ndarray, nd: int = 4) -> str:
    d = np.asarray(draws, dtype=float)
    if d.size == 0 or not np.isfinite(d).all():
        return f"{UNAVAILABLE} (undefined in some draw)"
    lo, hi = np.percentile(d, E.CI_PERCENTILES)
    return f"[{lo:.{nd}f}, {hi:.{nd}f}]"


def contest_context_rows(res: C.EraResult, label: str = "") -> list[dict]:
    """Mixed stints (§8d), the no-reference half, and each candidate's gain over no traffic term (point)."""
    if res.contest is None:
        return [{"item": f"{label}contest context", "value": f"{UNAVAILABLE} (no contest: {res.verdict_line})"}]
    rows = []
    for s in (C.SET_MIXED, C.SET_NOREF):
        r = res.contest.point[s]
        if r["laps"] <= 0:
            rows.append({"item": f"{label}{s}: R_flat, R_now", "value": f"{UNAVAILABLE} (no laps)"})
            continue
        rows.append({"item": f"{label}{s}: R_flat, R_now (laps {int(r['laps'])}, races {res.contest.races[s]})",
                     "value": f"R_flat {_fmt(r['r_flat'])} {_interval(res.contest.r_flat_draws[s])}; "
                              f"R_now {_fmt(r['r_now'])} {_interval(res.contest.r_now_draws[s])}"})
    r = res.contest.point[C.SET_ALL]
    rows.append({"item": f"{label}gain over no traffic term, all scored laps (point)",
                 "value": "; ".join(f"{c} {_fmt(r.get(f'gain_{c}', np.nan))}" for c in ("flat", "now", "measured"))})
    return rows


def older_rows(res: C.EraResult | None, error: str = "") -> list[dict]:
    """The older-car check (2018-2020 fit, 2021 scored): W1-W3 computed the same way, shown as figures."""
    lab = "older cars (2018-2020 fit, 2021 scored; never decides the verdict)"
    if res is None:
        return [{"item": lab, "value": f"{UNAVAILABLE} (not computed: {error})"}]
    rows = [{"item": f"{lab}: setup", "value": "; ".join(f"{c.name} {c.value}" for c in res.checks
                                                       if c.name in ("G4", "G5", "G6", "G7"))}]
    for name in ("W1", "W2"):
        c = next((c for c in res.checks if c.name == name), None)
        rows.append({"item": f"{lab}: {name}", "value": c.value if c else f"{UNAVAILABLE} (not reached)"})
    for c, name in ((res.p1, "P1"), (res.p2, "P2")):
        rows.append({"item": f"{lab}: {name}", "value": c.value if c else f"{UNAVAILABLE} (not reached)"})
    return rows + contest_context_rows(res, "older cars, ")


def under_attack_rows(table: pd.DataFrame | None) -> list[dict]:
    if table is None or table.empty:
        return [{"item": "under-attack difference at the same gap", "value": f"{UNAVAILABLE} (no fit passes)"}]
    near = table[table["bin"].isin(C.NEAR_BINS)]
    rows = []
    for cls, g in near.groupby("corner_class", sort=False):
        parts = []
        for _, r in g.iterrows():
            ci = (f"[{r['ci_lower_s']:.4f}, {r['ci_upper_s']:.4f}]" if r["status"] == E.CURVE_OK
                  else f"{UNAVAILABLE} (not estimable)")
            parts.append(f"{r['gap_lower_s']}-{r['gap_upper_s']} s: {_fmt(r['difference_s'])} {ci}")
        rows.append({"item": f"under-attack difference, {cls} (expected near zero)", "value": "; ".join(parts)})
    return rows


def team_rows(cov: pd.DataFrame | None, per_team: pd.DataFrame | None, season: int) -> list[dict]:
    rows = []
    if cov is not None and len(cov):
        c = cov[cov["season"] == season]
        for _, r in c.sort_values("team").iterrows():
            scored = (f"; scored laps {int(r['scored_laps'])}, clean-reference share "
                      f"{r['share_scored_clean_reference']:.3f}" if "scored_laps" in r and pd.notna(r.get("scored_laps"))
                      else f"; scored laps {UNAVAILABLE} (none)")
            rows.append({"item": f"coverage {season}, {r['team']}",
                         "value": f"following braking passes {int(r['following_braking_passes'])}, measured share "
                                  f"{r['share_following_measured']:.3f}{scored}"})
    if per_team is not None and len(per_team):
        for _, r in per_team.sort_values("team").iterrows():
            rows.append({"item": f"contest {season}, {r['team']} (point; laps {r['laps']}, races {r['races']})",
                         "value": f"R_flat {_fmt(r['r_flat'], reason='no laps')}; R_now {_fmt(r['r_now'], reason='no laps')}"})
    return rows or [{"item": f"coverage per team {season}", "value": f"{UNAVAILABLE} (no team data)"}]


def table2_text(rows: list[dict]) -> str:
    """Markdown Table 2. Refuses the words pass/fail in a value (they never belong in Table 2)."""
    lines = ["", TABLE2_TITLE, "", "| Item | Figure |", "|---|---|"]
    for r in rows:
        v = str(r["value"]).replace("|", "/")
        low = f" {v.lower()} "
        if " pass " in low or " fail " in low or " passed " in low or " failed " in low:
            raise E.EstimatorError(f"Table 2 must not say pass or fail: {r['item']}")
        lines.append(f"| {str(r['item']).replace('|', '/')} | {v} |")
    return "\n".join(lines) + "\n"
