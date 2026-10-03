"""Design 3 (evidence, WI-16b W63, 2026-10-03): ONE constant age adjustment per stint overlap.
usage (from transform/): python <this file> [--boot N]      read-only on data/dev.duckdb

A stint overlap is (race, unordered pair, stint_id, peer_stint_id): the pair-laps where both
cars sit on one particular set each. Peers share lap and compound with |age gap| <= 3, and both
ages advance one per lap, so the age gap dage = peer_age - age is CONSTANT inside an overlap
(checked below). Hence:
  - any LINEAR age adjustment beta * dage is already constant per overlap;
  - the shipped per-lap curve E, g(b) - g(a), moves inside an overlap only through curvature.

Candidates (all cross-fitted by race on the shipped 5 folds, F.race_folds):
  E     shipped per-lap curve (relative_pace_raw_gain_s - relative_pace_gain_s), reference
  3a    overlap mean of E's per-lap adjustment (E's level, no within-overlap movement)
  3b    field LINEAR slope beta_G * dage, beta_G from E's own design with age linear:
        lap_time_s ~ sum_G 1[G]*age | race_driver_compound + race_lap   (G = era|compound)
  3c    pair-identified linear slope: raw ~ sum_G 1[G]*dage | pair  (the "mean pace gap vs
        mean age gap per overlap" estimator, pooled over the other folds' overlaps; this is
        design A's identification, made linear)
  seed  relative_pace_seed_adj_gain_s, and seed-3a (its overlap mean), for reference

Test: the validator's tier-3 (ii) statistic, pooled within-(race, unordered pair) variance,
pairs with >= 3 pair-laps, change vs raw; 2018-2024 decides, 2025 confirms. Subsets: all
pairs, teammates (design 1's rule), non-teammates. 95% CIs race-clustered bootstrap.
"""
import sys, warnings
import numpy as np, pandas as pd, duckdb, pyfixest as pf

sys.path.insert(0, "/Users/justin/github/off-the-pace/transform")
from tasks.coefficients import fit_isolation_age_curve as F

warnings.filterwarnings("ignore")
DB = "/Users/justin/github/off-the-pace/data/dev.duckdb"
B = int(sys.argv[sys.argv.index("--boot") + 1]) if "--boot" in sys.argv else 2000
rng = np.random.default_rng(20261003)
PAIR = ["race_id", "driver_id", "peer_driver_id"]
SEG = PAIR + ["stint_id", "peer_stint_id"]

con = duckdb.connect(DB, read_only=True)
P = con.execute("""
  SELECT race_year, race_id, lap_number, compound, driver_id, peer_driver_id, stint_id, peer_stint_id,
         is_teammate, CAST(age_in_stint AS DOUBLE) a, CAST(peer_age_in_stint AS DOUBLE) b,
         relative_pace_raw_gain_s raw, relative_pace_gain_s adjE, relative_pace_seed_adj_gain_s adjS
  FROM fct_driver_isolation_pair_lap
  WHERE driver_id < peer_driver_id AND relative_pace_raw_gain_s IS NOT NULL AND relative_pace_gain_s IS NOT NULL
""").df()
panel = con.execute(F.PANEL_QUERY).fetchdf()
con.close()

panel["tag"] = F.era_tag(panel.race_year, panel.era)
folds = F.race_folds(panel.race_id)
panel["fold"] = panel.race_id.map(folds)
tag_of = panel.groupby("race_id").tag.first()
P["tag"] = P.race_id.map(tag_of)
P["fold"] = P.race_id.map(folds)
P["dage"] = P.b - P.a
P["dgE"] = P.raw - P.adjE
P["dgS"] = P.raw - P.adjS
P["seg"] = P[SEG].astype(str).agg("|".join, axis=1)
P["pair"] = P[PAIR].astype(str).agg("|".join, axis=1)
assert P.tag.notna().all() and P.fold.notna().all()
nonconst = (P.groupby("seg").dage.nunique() > 1).sum()
print(f"pair-laps {len(P)}, overlaps {P.seg.nunique()}, overlaps with non-constant age gap: {nonconst}")
seg_n = P.groupby("seg").size()
print(f"pair-laps in overlaps with dage != 0: {(P.dage != 0).mean():.3f}; "
      f"overlap length median {seg_n.median():.0f} laps")

# ── 3a: overlap mean of E (and of the seed) ─────────────────────────────────────────────
P["g3a"] = P.groupby("seg").dgE.transform("mean")
P["gS3a"] = P.groupby("seg").dgS.transform("mean")


# ── 3b: field linear slope, E's FE design with age linear ────────────────────────────────
def fit_field_linear(train):
    counts = train.groupby(["tag", "compound"]).size()
    big = {k for k, v in counts.items() if v >= F.N_MIN_LAPS}
    grp = np.array([F.group_key(t, c, big) for t, c in zip(train.tag, train.compound)])
    df = pd.DataFrame({f"x{i}": np.where(grp == g, train.age.to_numpy(), 0.0)
                       for i, g in enumerate(sorted(set(grp)))})
    names = dict(zip(df.columns, sorted(set(grp))))
    df["y"] = train.lap_time_s.to_numpy()
    df["rdc"] = (train.race_id + "|" + train.driver_id.astype(str) + "|" + train.compound).to_numpy()
    df["race_lap"] = (train.race_id + "|" + train.lap_number.astype(str)).to_numpy()
    m = pf.feols("y ~ " + " + ".join(names) + " | rdc + race_lap", data=df, fixef_tol=1e-10,
                 fixef_maxiter=100_000, vcov={"CRV1": "rdc"})
    co, se = m.coef(), m.se()
    return {names[c]: (co[c], se[c]) for c in names}, big


# ── 3c: pair-identified linear slope, raw ~ 1[G]*dage | pair ───────────────────────────────
def fit_pair_linear(train):
    groups = sorted(set(train.tag + "|" + train.compound))
    g = (train.tag + "|" + train.compound).to_numpy()
    codes = pd.factorize(train.pair)[0]
    def dm(v):
        return v - (np.bincount(codes, v) / np.bincount(codes))[codes]
    X = np.column_stack([dm(np.where(g == G, train.dage.to_numpy(), 0.0)) for G in groups])
    keep = (X ** 2).sum(0) > 0
    beta, *_ = np.linalg.lstsq(X[:, keep], dm(train.raw.to_numpy()), rcond=None)
    return dict(zip(np.array(groups)[keep], beta))


fs = panel[panel.in_fit]
P["g3b"] = np.nan
P["g3c"] = np.nan
slopes_b, slopes_c = {}, {}
for k in [None] + list(range(F.K_FOLDS)):
    trb = fs if k is None else fs[fs.fold != k]
    cb, big = fit_field_linear(trb)
    trc = P[P.race_year <= 2024] if k is None else P[(P.fold != k) & (P.race_year <= 2024)]
    cc = fit_pair_linear(trc)
    slopes_b["all" if k is None else f"excl{k}"] = {g: v[0] for g, v in cb.items()}
    slopes_c["all" if k is None else f"excl{k}"] = cc
    if k is None:
        se_b = {g: v[1] for g, v in cb.items()}
        continue
    te = P.fold == k
    gk = np.array([F.group_key(t, c, big) for t, c in zip(P.tag[te], P.compound[te])])
    P.loc[te, "g3b"] = np.array([cb[x][0] for x in gk]) * P.dage[te].to_numpy()
    raw_g = (P.tag[te] + "|" + P.compound[te]).to_numpy()
    P.loc[te, "g3c"] = np.array([cc.get(x, 0.0) for x in raw_g]) * P.dage[te].to_numpy()
assert P.g3b.notna().all() and P.g3c.notna().all()

print("\n(3b) field linear slope beta_G, s per lap of age (all races; then fold-held-out fits):")
for g in sorted(slopes_b["all"]):
    folds_v = [slopes_b[f"excl{k}"].get(g, np.nan) for k in range(F.K_FOLDS)]
    print(f"  {g:18s} {slopes_b['all'][g]:+.4f} (SE {se_b[g]:.4f})   folds " + " ".join(f"{v:+.4f}" for v in folds_v))
print("\n(3c) pair-identified linear slope, s per lap of age gap (2018-2024; then fold-held-out fits):")
for g in sorted(slopes_c["all"]):
    folds_v = [slopes_c[f"excl{k}"].get(g, np.nan) for k in range(F.K_FOLDS)]
    print(f"  {g:18s} {slopes_c['all'][g]:+.4f}   folds " + " ".join(f"{v:+.4f}" for v in folds_v))

# ── (1) per-overlap slopes: each overlap's mean pace gap against its pair's dage = 0 overlap ──
S = P[P.race_year <= 2024].groupby(SEG + ["pair", "tag", "compound", "is_teammate"]).agg(
    n=("raw", "size"), r=("raw", "mean"), v=("raw", "var"), dage=("dage", "first"),
    gE=("dgE", "mean"), g3b=("g3b", "mean")).reset_index()
# lag-1 autocorrelation of raw around its overlap mean (for an honest per-overlap SE)
Pd = P[P.race_year <= 2024].sort_values(SEG + ["lap_number"])
e = Pd.raw - Pd.groupby("seg").raw.transform("mean")
nxt = (Pd.seg == Pd.seg.shift(-1)) & (Pd.lap_number.shift(-1) == Pd.lap_number + 1)
rho = float(np.corrcoef(e[nxt.to_numpy()], e.shift(-1)[nxt.to_numpy()])[0, 1])
infl = (1 + rho) / (1 - rho)
S["se2"] = S.v.fillna(S.v.median()) / S.n * infl
print(f"\nper-overlap noise: lag-1 autocorrelation of the raw gap around its overlap mean {rho:.3f} "
      f"(SE^2 inflated x{infl:.2f})")
print(f"naive per-overlap slope = mean pace gap / age gap (dage != 0 overlaps, no pair baseline):")
nz = S[S.dage != 0]
naive = nz.r / nz.dage
print(f"  n {len(nz)}, median {naive.median():+.3f}, IQR [{naive.quantile(.25):+.3f}, {naive.quantile(.75):+.3f}] s/lap, "
      f"share > 0 {(naive > 0).mean():.3f}   <- mostly the pair's skill+car gap, not age")


def overlap_slopes(S, same_compound):
    ref_keys = ["pair"] + (["compound"] if same_compound else [])
    z = S[S.dage == 0]
    ref = z.groupby(ref_keys).apply(lambda d: pd.Series({
        "r0": np.average(d.r, weights=d.n), "se2_0": 1 / (1 / d.se2).sum()})).reset_index()
    x = S[S.dage != 0].merge(ref, on=ref_keys)
    x["slope"] = (x.r - x.r0) / x.dage
    x["se_slope"] = np.sqrt(x.se2 + x.se2_0) / x.dage.abs()
    x["slopeE"] = x.gE / x.dage                       # what E says for the same overlap
    return x


def dl(x):  # DerSimonian-Laird: is the spread more than sampling noise?
    w = 1 / x.se_slope ** 2
    mu = (w * x.slope).sum() / w.sum()
    Q = (w * (x.slope - mu) ** 2).sum(); k = len(x)
    tau2 = max(0.0, (Q - (k - 1)) / (w.sum() - (w ** 2).sum() / w.sum()))
    return mu, np.sqrt(1 / w.sum()), np.sqrt(tau2), max(0.0, (Q - (k - 1)) / Q)


for same in (False, True):
    x = overlap_slopes(S, same)
    lab = "same-compound dage=0 reference" if same else "any-compound dage=0 reference"
    print(f"\nper-overlap slope vs the pair's {lab}: (r_overlap - r_ref) / dage, s per lap")
    print(f"  {'group':18s} {'n':>5s} {'median':>8s} {'IQR':>18s} {'>0':>6s} {'medSE':>6s} {'FE-mean':>15s} {'tau':>6s} {'I2':>5s} {'E says':>7s}")
    for g, xx in [("ALL", x)] + [(f"{t}|{c}", d) for (t, c), d in x.groupby(["tag", "compound"])] + \
                 [("teammates", x[x.is_teammate]), ("non-teammates", x[~x.is_teammate])]:
        if len(xx) < 10:
            continue
        mu, mse, tau, i2 = dl(xx)
        print(f"  {g:18s} {len(xx):5d} {xx.slope.median():+8.3f} [{xx.slope.quantile(.25):+.3f}, {xx.slope.quantile(.75):+.3f}] "
              f"{(xx.slope > 0).mean():6.2f} {xx.se_slope.median():6.3f} {mu:+.3f}±{1.96*mse:.3f} {tau:6.3f} {i2:5.2f} {xx.slopeE.median():+7.3f}")

# ── (2)-(3) the tier-3 (ii) statistic ─────────────────────────────────────────────────────
D = P.copy()
D = D[D.groupby(PAIR).raw.transform("size") >= 3].reset_index(drop=True)
CANDS = [("E (shipped, per-lap curve)", "dgE"), ("3a overlap mean of E", "g3a"),
         ("3b field linear slope", "g3b"), ("3c pair-identified slope", "g3c"),
         ("seed dC (old)", "dgS"), ("seed-3a overlap mean", "gS3a")]
for c in ["raw"] + [c for _, c in CANDS]:
    D["w_" + c] = D[c] - D.groupby(PAIR)[c].transform("mean")
    D["s_" + c] = D[c] - D.groupby("seg")[c].transform("mean")   # within-overlap part


def test(df, c):
    t = pd.DataFrame({"race": df.race_id, "rr": df.w_raw ** 2, "aa": (df.w_raw - df["w_" + c]) ** 2}) \
          .groupby("race")[["rr", "aa"]].sum().to_numpy()
    pt = 100 * (t[:, 1].sum() / t[:, 0].sum() - 1)
    idx = rng.integers(0, len(t), (B, len(t)))
    s = t[idx].sum(1)
    bs = 100 * (s[:, 1] / s[:, 0] - 1)
    return pt, np.percentile(bs, 2.5), np.percentile(bs, 97.5)


def kstar(df, c):  # within-pair response of raw to the adjustment; > 0.5 needed to reduce variance
    return (df.w_raw * df["w_" + c]).sum() / (df["w_" + c] ** 2).sum()


for period, sel in [("2018-2024 (decides)", D.race_year <= 2024), ("2025 (confirm)", D.race_year == 2025)]:
    print(f"\n=== tier-3 (ii) pooled within-pair variance change vs raw, {period} ===")
    for sub, m in [("all pairs", np.ones(len(D), bool)), ("teammates", D.is_teammate.to_numpy()),
                   ("non-teammates", ~D.is_teammate.to_numpy())]:
        X = D[sel.to_numpy() & m]
        print(f"-- {sub}: pairs {X.groupby(PAIR).ngroups}, pair-laps {len(X)}, overlaps {X.seg.nunique()}, "
              f"raw within-pair var {(X.w_raw**2).sum()/ (X.groupby(PAIR).size()-1).sum():.4f}")
        for lab, c in CANDS:
            pt, lo, hi = test(X, c)
            verdict = "REDUCES" if pt < 0 else "adds"
            print(f"   {lab:30s} {pt:+.3f}%  [{lo:+.3f}, {hi:+.3f}]  k*={kstar(X, c):+.3f}  {verdict}")

# ── (4) what going to stint level saves: E's change split inside vs between overlaps ──────
print("\n=== E's change split: within-overlap (curvature) vs between-overlap (level), 2018-2024 ===")
for sub, m in [("all pairs", np.ones(len(D), bool)), ("teammates", D.is_teammate.to_numpy()),
               ("non-teammates", ~D.is_teammate.to_numpy())]:
    X = D[(D.race_year <= 2024).to_numpy() & m]
    tot = (X.w_raw ** 2).sum()
    w_in, r_in = X.s_dgE, X.s_raw
    w_bt, r_bt = X.w_dgE - X.s_dgE, X.w_raw - X.s_raw
    c_in = 100 * ((w_in ** 2).sum() - 2 * (r_in * w_in).sum()) / tot
    c_bt = 100 * ((w_bt ** 2).sum() - 2 * (r_bt * w_bt).sum()) / tot
    print(f"  {sub:14s} E {c_in + c_bt:+.3f}% = within-overlap {c_in:+.3f}pp + between-overlap {c_bt:+.3f}pp | "
          f"E's within-pair adj variance: {100*(X.w_dgE**2).sum()/tot:.3f}% of raw, of which within-overlap "
          f"{100*(w_in**2).sum()/(X.w_dgE**2).sum():.0f}% | raw var within-overlap share {100*(r_in**2).sum()/tot:.1f}% | "
          f"k*(within) {(r_in*w_in).sum()/(w_in**2).sum():+.3f}")

# ── does going to stint level move any published rating? (race-level pair mean) ──────────
R = P.groupby(PAIR).agg(dE=("dgE", "mean"), d3a=("g3a", "mean"), d3b=("g3b", "mean"), n=("raw", "size"))
print(f"\npair-race mean adjustment, 3a vs E: max |diff| {np.abs(R.dE - R.d3a).max():.2e} s "
      f"(identical by construction); 3b vs E: median |diff| {np.abs(R.dE - R.d3b).median():.3f} s, "
      f"p90 {np.abs(R.dE - R.d3b).quantile(.9):.3f} s")
