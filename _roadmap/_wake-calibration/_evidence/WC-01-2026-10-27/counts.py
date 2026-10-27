"""WC-01 coverage counts from the scratch pass table. Counts and shares only; nothing is fitted.

    python counts.py <scratch dir with pass_table_*.parquet and races.csv> <evidence dir>
"""
import glob
import sys
from pathlib import Path

import pandas as pd

# Must match build_pass_table.REASONS (priority order). flat_kink was removed on 2026-10-27 (flat-out
# corners now get a fixed segment start); track_limits and no_segment were added; yellow_sector was added
# on 2026-10-27 (pass c) when yellow stopped neutralising the whole lap.
REASONS = ["lap_1", "no_lap_record", "no_lap_time", "neutralised", "yellow_sector", "restart", "pit_lap",
           "pit_lap_leader", "wet", "track_limits", "no_segment", "off_track", "no_gap"]

src, dst = Path(sys.argv[1]), Path(sys.argv[2])
races = pd.read_csv(src / "races.csv")
t = pd.concat([pd.read_parquet(p) for p in sorted(glob.glob(str(src / "pass_table_*.parquet")))], ignore_index=True)


def summarise(g: pd.DataFrame) -> dict:
    n = len(g)
    kept = g[g["reason"].isna()]
    row = {
        "races": g["race_id"].nunique(),
        "passes": n,
        "excluded": int(g["reason"].notna().sum()),
        "kept": len(kept),
        "clean": int(g["clean"].sum()),
        "measured": int((g["ref_status"] == "measured").sum()),
        "no_clean_reference": int((g["ref_status"] == "no_clean_reference").sum()),
        "share_excluded": round(g["reason"].notna().mean(), 4),
        "share_measured_of_all": round((g["ref_status"] == "measured").mean(), 4),
        "share_no_clean_ref_of_all": round((g["ref_status"] == "no_clean_reference").mean(), 4),
        "share_measured_of_kept": round((kept["ref_status"] == "measured").mean(), 4) if len(kept) else None,
        "share_no_clean_ref_of_kept": round((kept["ref_status"] == "no_clean_reference").mean(), 4) if len(kept) else None,
        "tag_lapped": int(g["tag"].fillna("").str.contains("lapped").sum()),
        "tag_yielding": int(g["tag"].fillna("").str.contains("yielding").sum()),
        "passes_fixed_before_apex": int((g["segment_basis"] == "fixed_before_apex").sum()),
        "kept_fixed_before_apex": int((kept["segment_basis"] == "fixed_before_apex").sum()),
        "kept_leader_track_limits": int(kept["leader_track_limits"].sum()),
    }
    if "layout_changed" in g:  # DD-WC6 layout flag (pass d onward): a flag, not an exclusion
        lc = g["layout_changed"].astype(bool)
        row["races_layout_changed"] = int(g.loc[lc, "race_id"].nunique())
        row["passes_layout_changed"] = int(lc.sum())
        row["kept_layout_changed"] = int(kept["layout_changed"].astype(bool).sum())
        row["measured_layout_changed"] = int((lc & (g["ref_status"] == "measured")).sum())
    for r in REASONS:
        row[f"reason_{r}"] = int((g["reason"] == r).sum())
    # Stint view (for comparison with the memo's lap-end count): stints with at least one kept pass,
    # and how many of those have no pass with a measured reference.
    st = kept.groupby(["race_id", "driver", "stint"], dropna=False)["ref_status"].apply(lambda s: (s == "measured").any())
    row["stints_with_kept_passes"] = int(len(st))
    row["stints_no_measured_pass"] = int((~st).sum())
    row["share_stints_no_measured_pass"] = round(float((~st).mean()), 4) if len(st) else None
    return row


rows = [{"season": s, **summarise(g)} for s, g in t.groupby("season")]
rows.append({"season": "all", **summarise(t)})
counts = pd.DataFrame(rows)
skipped = races[races["status"] != "ok"].groupby("season").size()
counts.insert(2, "races_skipped", counts["season"].map(lambda s: int(skipped.get(s, 0)) if s != "all" else int(skipped.sum())))
counts.to_csv(dst / "counts_by_season.csv", index=False)

# Exclusion-reason breakdown: passes per season and reason (priority order; "kept" = no reason).
reason = t["reason"].fillna("kept")
br = pd.crosstab(t["season"], reason).reindex(columns=REASONS + ["kept"], fill_value=0)
br.loc["all"] = br.sum()
br["passes"] = br.sum(axis=1)
br.to_csv(dst / "exclusion_reasons_by_season.csv")
basis = pd.crosstab([t["season"], t["segment_basis"]], reason).reindex(columns=REASONS + ["kept"], fill_value=0)
basis.to_csv(dst / "exclusion_reasons_by_segment_basis.csv")

cls = t.groupby(["season", "corner_class"]).size().unstack(fill_value=0)
cls.to_csv(dst / "passes_by_corner_class.csv")
races.to_csv(dst / "races.csv", index=False)
fallback = t[t["circuit_info_season"] != t["season"]].groupby(["season", "race", "circuit_info_season"]).size()
fallback.rename("passes").reset_index().to_csv(dst / "circuit_info_fallbacks.csv", index=False)
if "layout_changed" in t:  # DD-WC6: one row per flagged race, with its pass counts and the note
    flagged = t[t["layout_changed"].astype(bool)]
    lf = flagged.groupby(["season", "race", "layout_note"]).agg(
        passes=("reason", "size"), kept=("reason", lambda r: int(r.isna().sum())),
        measured=("ref_status", lambda r: int((r == "measured").sum()))).reset_index()
    lf.to_csv(dst / "layout_flagged_races.csv", index=False)
    print(lf.to_string())

with pd.option_context("display.width", 250, "display.max_columns", 50):
    print(counts.T.to_string())
    print(cls)
    print(fallback)
