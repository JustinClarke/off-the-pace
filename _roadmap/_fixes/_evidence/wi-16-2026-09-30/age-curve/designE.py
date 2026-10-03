"""Design E vs C: FE spec swap only. Fold stability of g, and the pair-variance check."""
import sys, warnings, duckdb, numpy as np, pandas as pd, pyfixest as pf
warnings.filterwarnings("ignore")
sys.path.insert(0, "/Users/justin/github/off-the-pace/transform")
from tasks.coefficients import fit_isolation_age_curve as F
FE = sys.argv[1]  # e.g. "rdc + race_lap"
con = duckdb.connect("/Users/justin/github/off-the-pace/data/dev.duckdb", read_only=True)
panel = con.execute(F.PANEL_QUERY).fetchdf()
pairs = con.execute("""SELECT race_year, race_id, driver_id, peer_driver_id, compound, age_in_stint a, peer_age_in_stint b,
   relative_pace_raw_gain_s raw FROM fct_driver_isolation_pair_lap WHERE driver_id < peer_driver_id""").df()
con.close()
panel["rdc"] = panel.race_id + "|" + panel.driver_id + "|" + panel.compound
st = panel[panel.in_fit].groupby("rdc").stint_id.nunique()
print(f"fit-sample laps in (race,driver,compound) cells with >=2 stints: {panel[panel.in_fit].rdc.map(st).ge(2).mean():.3f}")

def fit_curves(train):
    counts = train.groupby(["tag", "compound"]).size()
    big = {k for k, v in counts.items() if v >= F.N_MIN_LAPS}
    grp = np.array([F.group_key(t, c, big) for t, c in zip(train.tag, train.compound)])
    age = train.age.to_numpy(); cols, curves = {}, {}
    for g in sorted(set(grp)):
        m = grp == g; t = F.knots_for(age[m]); z = F.basis(age, t)[:, 1:]; z[~m] = 0
        names = [f"z{len(cols)+j}" for j in range(z.shape[1])]
        for j, n in enumerate(names): cols[n] = z[:, j]
        curves[g] = {"t": t, "cols": names}
    df = pd.DataFrame(cols); df["y"] = train.lap_time_s.to_numpy()
    df["stint_id"] = train.stint_id.astype(str).to_numpy(); df["rdc"] = train.rdc.to_numpy()
    df["race_lap"] = (train.race_id + "|" + train.lap_number.astype(str)).to_numpy()
    co = pf.feols("y ~ " + " + ".join(cols) + " | " + FE, data=df, fixef_tol=1e-10).coef()
    for g, c in curves.items(): c["beta"] = np.r_[0.0, [co.get(n, np.nan) for n in c["cols"]]]
    return curves, big

panel["tag"] = F.era_tag(panel.race_year, panel.era)
folds = F.race_folds(panel.race_id); panel["fold"] = panel.race_id.map(folds)
pairs["fold"] = pairs.race_id.map(folds)
pairs["tag"] = np.where(pairs.race_year == 2018, "2018", np.where(pairs.race_year < 2022, "pre2022", "post2022"))
fs = panel[panel.in_fit]; ref = np.array([2.0, 5.0, 10.0, 20.0])
pairs["adj"] = np.nan
for label, k in [("all", None)] + [(f"excl{k}", k) for k in range(5)]:
    cv, big = fit_curves(fs if k is None else fs[fs.fold != k])
    print(label.ljust(6), " ".join(f"{g}:{F.evaluate(cv[g], ref)[3]:+.2f}" for g in sorted(cv)))
    if k is None: allcv = cv; continue
    te = pairs[pairs.fold == k]
    d = np.zeros(len(te))
    for (t, c), idx in te.groupby(["tag", "compound"]).groups.items():
        cvg = cv[F.group_key(t, c, big)]; pos = te.index.get_indexer(idx)
        d[pos] = F.evaluate(cvg, te.loc[idx, "b"].to_numpy().astype(float)) - F.evaluate(cvg, te.loc[idx, "a"].to_numpy().astype(float))
    pairs.loc[te.index, "adj"] = te.raw.to_numpy() - d
print("\nall-race slopes s/lap over ages 2-5 / 5-10 / 10-20:")
for g in sorted(allcv):
    v = F.evaluate(allcv[g], ref); print(f"  {g:18s} {(v[1]-v[0])/3:+.3f} {(v[2]-v[1])/5:+.3f} {(v[3]-v[2])/10:+.3f}")
key = ["race_id", "driver_id", "peer_driver_id"]
for lab, sel in [("2018-2024", pairs.race_year <= 2024), ("2025", pairs.race_year == 2025)]:
    s = pairs[sel]; s = s[s.groupby(key).raw.transform("size") >= 3]; g = s.groupby(key)
    vr = (g.raw.var(ddof=1) * (g.size() - 1)).sum(); va = (g.adj.var(ddof=1) * (g.size() - 1)).sum()
    print(f"{lab}: cross-fitted variance change vs raw {100*(va/vr-1):+.3f}%")
