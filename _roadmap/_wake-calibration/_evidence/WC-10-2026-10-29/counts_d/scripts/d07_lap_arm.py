import sys, numpy as np, pandas as pd, pyarrow.parquet as pq
sys.path.insert(0, "/Users/justin/github/off-the-pace/transform")
from tasks.wake_calibration import estimator as E
R = "/Users/justin/github/off-the-pace/_roadmap/_wake-calibration/_artifacts"
COLS = ["season","race_id","driver","lap","stint","compound","corner_id","corner_number","segment_basis","leader","gap_s","clear_ahead","tag","reason"]
p = pd.concat([pq.read_table(f"{R}/WC-03-run/pass-table/pass_table_{s}.parquet", columns=COLS).to_pandas() for s in (2022, 2023)], ignore_index=True)
sb = p.groupby(["race_id","corner_id"]).segment_basis.nunique()
print("corners with >1 segment_basis:", int((sb>1).sum()), "of", len(sb))
print(p.segment_basis.value_counts(dropna=False).to_dict())
mix = p.groupby(["race_id","corner_id"]).segment_basis.agg(lambda x: (x=="brake_onset").mean())
print("brake_onset share per corner quantiles", mix.quantile([0,.05,.1,.25,.5,.75,.9,1]).round(3).to_dict())
p["rc"] = E.racecraft(p).to_numpy()
tag = p.tag.fillna("").astype(str)
p["elig"] = p.reason.isna() & (p.segment_basis=="brake_onset") & ~tag.str.contains("yielding") & p.stint.notna() & ~p.rc
# define braking corner of race = corner with brake_onset share >= 0.5
bc = mix[mix>=0.5].reset_index()[["race_id","corner_id"]]
print("braking corners (majority) per race median", bc.groupby("race_id").size().median())
q = p.merge(bc, on=["race_id","corner_id"])
# a pass row at a majority-braking corner that is fixed_before_apex counts as not eligible
lp = q.groupby(["race_id","driver","lap"]).agg(n=("elig","size"), ne=("elig","sum")).reset_index()
lp["nb"] = lp.race_id.map(bc.groupby("race_id").size())
print("driver-laps", len(lp), "rows==nb", int((lp.n==lp.nb).sum()), "all eligible", int((lp.ne==lp.nb).sum()))
print("share of driver-laps missing >=1 braking corner for segment_basis alone:",
      round(float(q[q.segment_basis!="brake_onset"].groupby(["race_id","driver","lap"]).ngroups/len(lp)),3))
q["e0"] = q.reason.isna() & ~q.tag.fillna("").astype(str).str.contains("yielding") & q.stint.notna()
l2 = q.groupby(["race_id","driver","lap"]).agg(ne0=("e0","sum"), ne=("elig","sum"), n=("e0","size")).reset_index()
l2["nb"] = l2.race_id.map(bc.groupby("race_id").size())
print("laps all eligible ignoring racecraft:", int((l2.ne0==l2.nb).sum()))
print("per-lap ineligible corner count quantiles (no racecraft):", (l2.nb-l2.ne0).quantile([.1,.25,.5,.75]).to_dict())
print("reasons:", q.reason.value_counts(dropna=False).head(12).to_dict())
print("rc share among e0:", round(float(q[q.e0].rc.mean()),3))
l3 = q.groupby(["race_id","driver","lap"]).agg(nrc=("rc","sum"), n=("rc","size"), ne0=("e0","sum")).reset_index()
print("laps with zero racecraft:", int((l3.nrc==0).sum()), "of", len(l3))
print("rc share by segment_basis in p:", p.groupby("segment_basis").rc.mean().round(3).to_dict())
print("dtype elig", p.elig.dtype, p.rc.dtype, "elig sum", int(p.elig.sum()))
l4 = q.groupby(["race_id","driver","lap"]).agg(ne=("elig","sum"), ne0=("e0","sum"), nrc=("rc","sum")).reset_index()
l4["nb"] = l4.race_id.map(bc.groupby("race_id").size())
print("check:", int(((l4.ne0==l4.nb)&(l4.nrc==0)).sum()), int((l4.ne==l4.nb).sum()))
x = q.e0 & ~q.rc
print("elig vs e0&~rc disagree:", int((x != q.elig).sum()), "elig sum q", int(q.elig.sum()), "x sum", int(x.sum()))
print(q.loc[x != q.elig, ["segment_basis","reason","tag","rc","e0","elig"]].head())
print(l4.dtypes.to_dict()); print(l4[(l4.ne0==l4.nb)&(l4.nrc==0)].head(3).to_string())
q["isfree"] = q.clear_ahead.fillna(False).astype(bool) | (q.gap_s >= 3)
q["gfill"] = np.where(q.isfree, 3.0, q.gap_s)
lp = q.groupby(["race_id","driver","lap"]).agg(n=("elig","size"), nel=("elig","sum"), nfree=("isfree","sum"),
        med=("gfill","median"), stint=("stint","first"), comp=("compound","first")).reset_index()
lp["nb"] = lp.race_id.map(bc.groupby("race_id").size())
sc = lp[(lp["nel"]==lp["nb"]) & (lp["n"]==lp["nb"])].copy()
sc["free"] = sc.nfree==sc.nb
sc["fol"] = (sc.med>=0)&(sc.med<3)&~sc.free
sc["near"] = (sc.med>=0.5)&(sc.med<1.0)&~sc.free
sc["sid"] = sc.groupby(["race_id","driver","stint","comp"], dropna=False).ngroup()
sc["nfl"] = sc.sid.map(sc[sc.free].groupby("sid").size()).fillna(0)
sc["sup"] = sc.fol & (sc.nfl>=3)
f2 = sc[sc.free][["sid","lap"]].sort_values(["sid","lap"])
e2 = f2.sid.to_numpy(np.int64)*1000 + f2.lap.to_numpy(np.int64)
q2 = sc.sid.to_numpy(np.int64)*1000 + sc.lap.to_numpy(np.int64)
a0 = np.searchsorted(e2,q2,"left")-1; a1 = np.searchsorted(e2,q2,"right")
c0=np.clip(a0,0,len(e2)-1); c1=np.clip(a1,0,len(e2)-1); sid=sc.sid.to_numpy()
pv = np.where((a0>=0)&(e2[c0]//1000==sid), e2[c0]%1000, -999); nx = np.where((a1<len(e2))&(e2[c1]//1000==sid), e2[c1]%1000, 99999)
print("LAP ARM scored", len(sc), "free", int(sc.free.sum()), "following", int(sc.fol.sum()), "supported following", int(sc.sup.sum()),
      "supported near", int((sc.sup&sc.near).sum()))
for W in (5,8):
    b = (sc.lap.to_numpy()-pv<=W)&(nx-sc.lap.to_numpy()<=W)
    print(f" W={W} near bracketed", int((sc.sup&sc.near&b).sum()), "following bracketed", int((sc.sup&b).sum()))
