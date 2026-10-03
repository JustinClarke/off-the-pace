"""Design A (evidence, WI-16b 2026-09-30): a B-spline age curve fitted INSIDE the pair design.
usage: AGE_OUT=<dir> python proto.py <dev.duckdb> [--clean]
(--clean = design A on clean-air, non-recovery pair-laps only.) Writes <dir>/proto_out[_clean].parquet,
the pair-laps with raw, seed-adjusted and design-A adjusted deltas, read by proto3.py and ci.py.

Prototype: cross-fitted B-spline tyre-age adjustment for tier-3 relative pace.
Pre-declared design (fixed before results):
  raw_{p,l} = alpha_p + [g_G(age_b) - g_G(age_a)] + e,  p = (race, unordered pair)
  g_G: cubic B-spline in age_in_stint, 3 interior knots at the fit folds' age quartiles,
       boundary = fit folds' 1st/99th age percentiles (ages clipped to it), one curve per
       group G = era_tag|compound (era_tag 2018 / pre2022 / post2022); groups with
       < 5000 pair-laps in the fit folds pooled into era_tag|OTHER.
  5 folds by race (sorted race key, round-robin); curve for a race is fitted on the
  other 4 folds. Metric: the validator's pooled within-pair variance, 2018-2024."""
import sys, numpy as np, pandas as pd, duckdb
from scipy.interpolate import BSpline
from scipy.sparse import csr_matrix
from scipy.sparse.linalg import lsqr

K_FOLDS, N_MIN, DEG = 5, 5000, 3
import os; OUTDIR = os.environ.get("AGE_OUT", ".")
db = sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith("--") else "/Users/justin/github/off-the-pace/data/dev.duckdb"
con = duckdb.connect(db, read_only=True)
d = con.execute("""
  SELECT race_year, race_id, driver_id, peer_driver_id, compound,
         CAST(age_in_stint AS DOUBLE) a, CAST(peer_age_in_stint AS DOUBLE) b,
         relative_pace_raw_gain_s raw, relative_pace_seed_adj_gain_s adj_seed,
         (NOT is_dirty_air_lap AND NOT peer_is_dirty_air_lap AND stint_phase <> 'recovery' AND peer_stint_phase <> 'recovery') AS clean
  FROM fct_driver_isolation_pair_lap
  WHERE driver_id < peer_driver_id AND relative_pace_raw_gain_s IS NOT NULL
""").df()
d["era_tag"] = np.where(d.race_year == 2018, "2018", np.where(d.race_year < 2022, "pre2022", "post2022"))
d["pair"] = d.race_id + "|" + d.driver_id + "|" + d.peer_driver_id
races = sorted(d.race_id.unique(), key=lambda r: (int(r.split("_")[0]), int(r.split("_")[1])))
fold_of = {r: i % K_FOLDS for i, r in enumerate(races)}
d["fold"] = d.race_id.map(fold_of)

def basis(x, t):
    x = np.clip(x, t[DEG], t[-DEG - 1])
    return BSpline.design_matrix(x, t, DEG).toarray()

def fit_curves(tr):
    tr = tr.copy()
    cnt = tr.groupby(["era_tag", "compound"]).size()
    big = {k for k, v in cnt.items() if v >= N_MIN}
    tr["grp"] = [f"{e}|{c}" if (e, c) in big else f"{e}|OTHER" for e, c in zip(tr.era_tag, tr.compound)]
    curves, cols, blocks = {}, [], []
    for g, gg in tr.groupby("grp"):
        ages = np.concatenate([gg.a, gg.b])
        lo, hi = np.percentile(ages, [1, 99])
        inner = np.percentile(ages, [25, 50, 75])
        inner = inner[(inner > lo) & (inner < hi)]
        t = np.r_[[lo] * (DEG + 1), inner, [hi] * (DEG + 1)]
        curves[g] = {"t": t}
    # joint within-pair regression over all groups
    X = np.zeros((len(tr), 0)); spans = {}
    mats = []
    for g in curves:
        m = (tr.grp == g).to_numpy()
        t = curves[g]["t"]; nb = len(t) - DEG - 1
        Z = np.zeros((len(tr), nb - 1))  # drop first basis col: g anchored at the low end
        Z[m] = (basis(tr.b.to_numpy()[m], t) - basis(tr.a.to_numpy()[m], t))[:, 1:]
        spans[g] = (sum(M.shape[1] for M in mats), nb - 1); mats.append(Z)
    X = np.hstack(mats)
    y = tr.raw.to_numpy()
    # demean within pair
    codes = pd.factorize(tr.pair)[0]
    def dm(v):
        s = np.bincount(codes, weights=v); n = np.bincount(codes)
        return v - (s / n)[codes]
    yd = dm(y); Xd = np.column_stack([dm(X[:, j]) for j in range(X.shape[1])])
    beta, *_ = np.linalg.lstsq(Xd, yd, rcond=None)
    for g, (s0, k) in spans.items():
        curves[g]["beta"] = np.r_[0.0, beta[s0:s0 + k]]
    return curves, big

def g_eval(curves, big, era_tag, comp, age):
    key = f"{era_tag}|{comp}" if (era_tag, comp) in big else f"{era_tag}|OTHER"
    c = curves.get(key)
    if c is None:
        return np.zeros_like(age)
    return basis(age, c["t"]) @ c["beta"]

def adjust(df, curves, big):
    out = np.zeros(len(df))
    for (e, c), idx in df.groupby(["era_tag", "compound"]).groups.items():
        sub = df.loc[idx]
        out[df.index.get_indexer(idx)] = g_eval(curves, big, e, c, sub.b.to_numpy()) - g_eval(curves, big, e, c, sub.a.to_numpy())
    return df.raw.to_numpy() - out

d = d.reset_index(drop=True)
CLEAN = "--clean" in sys.argv  # fit only on pair-laps with both cars in clean air, not recovering
FITMASK = d.clean.to_numpy() if CLEAN else np.ones(len(d), bool)
print("fit sample pair-laps:", int(FITMASK.sum()), "of", len(d))
d["adj_spline_cf"] = np.nan
for k in range(K_FOLDS):
    curves, big = fit_curves(d[(d.fold != k) & FITMASK])
    te = d[d.fold == k]
    d.loc[te.index, "adj_spline_cf"] = adjust(te, curves, big)
curves_all, big_all = fit_curves(d[FITMASK])
d["adj_spline_insample"] = adjust(d, curves_all, big_all)

def pooled(df, col):
    g = df.groupby(["race_id", "driver_id", "peer_driver_id"])[col]
    n = g.transform("size")
    dd = df[n >= 3]
    gg = dd.groupby(["race_id", "driver_id", "peer_driver_id"])[col]
    ss = gg.var(ddof=1) * (gg.size() - 1)
    return ss.sum() / (gg.size() - 1).sum()

for label, sel in [("2018-2024 (decides)", d.race_year <= 2024), ("2025 (confirm)", d.race_year == 2025),
                   ("both pre-cliff n/a", None)]:
    if sel is None: continue
    s = d[sel]
    vr = pooled(s, "raw")
    print(f"{label}: raw var {vr:.5f}")
    for c in ("adj_seed", "adj_spline_cf", "adj_spline_insample"):
        v = pooled(s, c); print(f"   {c:22s} var {v:.5f}  change vs raw {100*(v/vr-1):+.3f}%")
print("\nIn-sample curves g(age) - g(lo), s:")
for g, c in curves_all.items():
    ages = np.array([2, 5, 10, 15, 20, 25, 30])
    print(f"  {g:22s} knots {np.round(c['t'][DEG:-DEG],1)}  g: " + " ".join(f"{a}:{v:+.3f}" for a, v in zip(ages, basis(ages.astype(float), c['t']) @ c['beta'])))
d[["race_year","race_id","driver_id","peer_driver_id","compound","a","b","raw","adj_seed","adj_spline_cf","adj_spline_insample","fold"]].to_parquet(OUTDIR + "/" + ("proto_out_clean.parquet" if CLEAN else "proto_out.parquet"))
