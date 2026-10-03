"""Design C: lap-level two-way FE age curve.
  lap_time_s ~ sum_G 1[G] * B_G(age)[,1:] | stint_id + race_lap
fit sample: Omega panel laps, clean air, not recovery. Cubic B-spline, 3 interior knots at
the fit sample's age quartiles, boundary 1st/99th pct (clipped); G = era_tag|compound,
groups < N_MIN laps pooled to era_tag|OTHER. 5 race folds (same assignment as proto.py).
Applied to every pair-lap: adj = raw - (g(age_b) - g(age_a))."""
import sys, warnings, numpy as np, pandas as pd, duckdb, pyfixest as pf
from scipy.interpolate import BSpline
warnings.filterwarnings("ignore")
K_FOLDS, N_MIN, DEG = 5, 3000, 3
db = sys.argv[1]
MONO = "--mono" in sys.argv
con = duckdb.connect(db, read_only=True)
L = con.execute("""
  SELECT race_year, race_id, driver_id, stint_id, lap_number, compound,
         CAST(age_in_stint AS DOUBLE) age, lap_time_s
  FROM int_driver_isolation_lap_panel
  WHERE NOT is_dirty_air_lap AND stint_phase <> 'recovery' AND age_in_stint IS NOT NULL
""").df()
P = pd.read_parquet(sys.argv[2])  # pair-laps from proto.py (raw, adj_seed, a, b, compound, fold)
def era_tag(y): return np.where(y == 2018, "2018", np.where(y < 2022, "pre2022", "post2022"))
L["era_tag"] = era_tag(L.race_year); P["era_tag"] = era_tag(P.race_year)
races = sorted(set(L.race_id) | set(P.race_id), key=lambda r: (int(r.split("_")[0]), int(r.split("_")[1])))
fold_of = {r: i % K_FOLDS for i, r in enumerate(races)}
L["fold"] = L.race_id.map(fold_of); P["fold"] = P.race_id.map(fold_of)
L["race_lap"] = L.race_id + "|" + L.lap_number.astype(str)

def basis(x, t):
    return BSpline.design_matrix(np.clip(x, t[DEG], t[-DEG - 1]), t, DEG).toarray()

def fit(tr):
    cnt = tr.groupby(["era_tag", "compound"]).size()
    big = {k for k, v in cnt.items() if v >= N_MIN}
    grp = np.array([f"{e}|{c}" if (e, c) in big else f"{e}|OTHER" for e, c in zip(tr.era_tag, tr.compound)])
    curves, cols = {}, {}
    X = {}
    for g in np.unique(grp):
        m = grp == g; ages = tr.age.to_numpy()[m]
        lo, hi = np.percentile(ages, [1, 99]); inner = np.percentile(ages, [20, 40, 60, 80])
        t = np.r_[[lo] * (DEG + 1), inner[(inner > lo) & (inner < hi)], [hi] * (DEG + 1)]
        B = basis(tr.age.to_numpy(), t)[:, 1:]
        B[~m] = 0.0
        names = [f"z{len(X) + j}" for j in range(B.shape[1])]
        for j, n in enumerate(names): X[n] = B[:, j]
        curves[g] = {"t": t, "cols": names}
    df = pd.DataFrame(X); df["y"] = tr.lap_time_s.to_numpy()
    df["stint_id"] = tr.stint_id.to_numpy(); df["race_lap"] = tr.race_lap.to_numpy()
    m = pf.feols("y ~ " + " + ".join(X) + " | stint_id + race_lap", data=df)
    co = m.coef()
    for g, c in curves.items():
        c["beta"] = np.r_[0.0, [co.get(n, 0.0) for n in c["cols"]]]
    return curves, big

def g_eval(curves, big, e, c, age):
    key = f"{e}|{c}" if (e, c) in big else f"{e}|OTHER"
    cv = curves.get(key)
    return np.zeros_like(age) if cv is None else basis(age, cv["t"]) @ cv["beta"]

def adjust(df, curves, big):
    out = np.zeros(len(df))
    for (e, c), idx in df.groupby(["era_tag", "compound"]).groups.items():
        pos = df.index.get_indexer(idx); sub = df.loc[idx]
        out[pos] = g_eval(curves, big, e, c, sub.b.to_numpy()) - g_eval(curves, big, e, c, sub.a.to_numpy())
    return df.raw.to_numpy() - out

P = P.reset_index(drop=True); P["adj_C_cf"] = np.nan
for k in range(K_FOLDS):
    cv, big = fit(L[L.fold != k])
    te = P[P.fold == k]; P.loc[te.index, "adj_C_cf"] = adjust(te, cv, big)
cv_all, big_all = fit(L)
P["adj_C_in"] = adjust(P, cv_all, big_all)

def pooled(df, col):
    g = df.groupby(["race_id", "driver_id", "peer_driver_id"])[col]
    dd = df[g.transform("size") >= 3]; gg = dd.groupby(["race_id", "driver_id", "peer_driver_id"])[col]
    return (gg.var(ddof=1) * (gg.size() - 1)).sum() / (gg.size() - 1).sum()
for label, sel in [("2018-2024 (decides)", P.race_year <= 2024), ("2025 (confirm)", P.race_year == 2025)]:
    s = P[sel]; vr = pooled(s, "raw"); print(f"{label}: raw var {vr:.5f}")
    for c in ("adj_seed", "adj_C_cf", "adj_C_in"):
        v = pooled(s, c); print(f"   {c:10s} var {v:.5f}  change vs raw {100*(v/vr-1):+.3f}%")
    # level effect: mean |adjustment| per pair-lap
    print(f"   mean |seed dC| {np.abs(s.raw - s.adj_seed).mean():.3f} s; mean |spline dg| {np.abs(s.raw - s.adj_C_cf).mean():.3f} s")
print("\nIn-sample curves g(age) - g(lo), s  [laps in group]:")
cnt = L.groupby(["era_tag", "compound"]).size()
for g, c in cv_all.items():
    ages = np.array([2, 5, 10, 15, 20, 25, 30, 40])
    vals = basis(ages.astype(float), c["t"]) @ c["beta"]
    print(f"  {g:18s} knots {np.round(c['t'][DEG:-DEG],0)}  " + " ".join(f"{a}:{v:+.2f}" for a, v in zip(ages, vals)))
P.to_parquet(sys.argv[2].replace(".parquet", "_C4.parquet"))
