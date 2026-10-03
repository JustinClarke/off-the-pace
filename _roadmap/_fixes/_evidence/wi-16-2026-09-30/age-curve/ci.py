import sys, numpy as np, pandas as pd
P = pd.read_parquet(sys.argv[1])
P["era_tag"] = np.where(P.race_year == 2018, "2018", np.where(P.race_year < 2022, "pre2022", "post2022"))
P = P[P.race_year <= 2024]
cols = ["raw", "adj_seed", "adj_spline_cf", "adj_C_cf"]
key = ["race_id", "driver_id", "peer_driver_id"]
n = P.groupby(key).raw.transform("size"); P = P[n >= 3]
g = P.groupby(key)
agg = pd.DataFrame({c: g[c].var(ddof=1) * (g.size() - 1) for c in cols}); agg["df"] = g.size() - 1
agg = agg.reset_index()
by_race = agg.groupby("race_id")[cols + ["df"]].sum()
def change(tab, c): return 100 * (tab[c].sum() / tab["raw"].sum() - 1)
rng = np.random.default_rng(42); idx = np.arange(len(by_race))
for c in cols[1:]:
    boots = [change(by_race.iloc[rng.choice(idx, len(idx))], c) for _ in range(2000)]
    print(f"{c:14s} {change(by_race, c):+.3f}%  95% CI [{np.percentile(boots,2.5):+.3f}, {np.percentile(boots,97.5):+.3f}]")
# where does C add variance: by era_tag x compound of the pair-lap, and by cliff status
first = P.groupby(key).agg(era_tag=("era_tag", "first")).reset_index()
agg = agg.merge(first, on=key)
print("\nby era_tag (pair's era):")
for e, t in agg.groupby("era_tag"):
    print(f"  {e:9s} seed {change(t,'adj_seed'):+.2f}%  A {change(t,'adj_spline_cf'):+.2f}%  C {change(t,'adj_C_cf'):+.2f}%  pairs {len(t)}")
