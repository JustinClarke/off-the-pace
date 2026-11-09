import sys, numpy as np, pandas as pd, pyarrow.parquet as pq
R = "/Users/justin/github/off-the-pace/_roadmap/_wake-calibration/_artifacts"
C = ["race_id","driver","lap","stint","compound","tyre_life","corner_id","corner_class","segment_basis","gap_s","clear_ahead","tag","reason"]
p = pd.concat([pq.read_table(f"{R}/WC-03-run/pass-table/pass_table_{s}.parquet", columns=C).to_pandas() for s in (2022,2023)], ignore_index=True)
tag = p.tag.fillna("").astype(str)
k = p[p.reason.isna() & (p.segment_basis=="brake_onset") & ~tag.str.contains("yielding") & p.stint.notna()].copy()
k["free"] = k.clear_ahead.fillna(False).astype(bool) | (k.gap_s>=3)
k["near"] = (k.gap_s>=0.5)&(k.gap_s<1.0)&~k.free
k["gid"] = k.groupby(["race_id","driver","stint","compound","corner_id"]).ngroup()
f = k[k.free].groupby("gid").tyre_life.agg(n="size", mean="mean", ss=lambda x: ((x-x.mean())**2).sum(), spread=lambda x: x.max()-x.min())
nr = k[k.near].join(f, on="gid")
nr = nr[nr.n>=2]
nr["d"] = nr.tyre_life - nr["mean"]
sig = {"fast":0.060,"medium":0.063,"slow":0.064}
for rule, msk in (("n>=3", nr.n>=3), ("n>=3 & spread>=4", (nr.n>=3)&(nr.spread>=4)), ("n>=3 & spread>=8", (nr.n>=3)&(nr.spread>=8))):
    out=[]
    for c in ("fast","medium","slow"):
        x = nr[msk & (nr.corner_class==c)]
        sd = x.groupby("gid").agg(D=("d","sum"), ss=("ss","first"))
        se = sig[c]*np.sqrt((sd.D**2/sd.ss).sum())/len(x)
        out.append((c, len(x), sd.shape[0], round(float(x.d.mean()),2), round(float(se),4)))
    print(rule, out)
