"""REVIEW-2 independent structural recount, 2022-23 only. Reads ONLY structural columns of the pass table
and sidecar (no time/speed/delta/reference/coast/throttle column). Nothing fitted."""
import sys
import numpy as np, pandas as pd, pyarrow.parquet as pq
sys.path.insert(0, "/Users/justin/github/off-the-pace/transform")
from tasks.wake_calibration import estimator as E, build_pass_table as bpt

R = "/Users/justin/github/off-the-pace/_roadmap/_wake-calibration/_artifacts"
COLS = ["season", "race_id", "race", "driver", "lap", "stint", "compound", "tyre_life", "corner_id", "corner_number",
        "corner_class", "segment_basis", "leader", "leader_lap", "gap_s", "clear_ahead", "behind_1s", "tag", "reason"]
SC = ["season", "race_id", "driver", "lap", "corner_id", "prev_lap_gap_s", "prev_lap_clear_ahead", "prev_lap_reason"]
p = pd.concat([pq.read_table(f"{R}/WC-03-run/pass-table/pass_table_{s}.parquet", columns=COLS).to_pandas() for s in (2022, 2023)],
              ignore_index=True)
s = pd.concat([pq.read_table(f"{R}/WC-10/sidecar/sidecar_{y}.parquet", columns=SC).to_pandas() for y in (2022, 2023)],
              ignore_index=True)
print("rows", len(p))
p["racecraft"] = E.racecraft(p).to_numpy()
tag = p["tag"].fillna("").astype(str)
E_ = (p["reason"].isna() & (p["segment_basis"] == "brake_onset") & ~tag.str.contains("yielding") & p["stint"].notna())
print("eligible (no compound filter)", int(E_.sum()), " compound null among them", int((E_ & p["compound"].isna()).sum()))
k = p[E_].copy()
k = k.merge(s, on=["season", "race_id", "driver", "lap", "corner_id"], how="left", validate="1:1")
g = k["gap_s"].to_numpy(float)
k["free"] = (k["clear_ahead"].fillna(False).astype(bool) | (g >= 3)).to_numpy()
k["follow"] = (g >= 0) & (g < 3) & ~k["free"]
k["close"] = (g >= 0) & (g < 1) & ~k["free"]
k["near"] = (g >= 0.5) & (g < 1.0) & ~k["free"]
k["far"] = (g >= 2.0) & (g < 3.0) & ~k["free"]
print("free", int(k.free.sum()), "follow", int(k.follow.sum()), "neg", int((g < 0).sum()),
      "follow&free overlap", int(((g >= 0) & (g < 3) & k.free).sum()))
GK = ["race_id", "driver", "stint", "compound", "corner_id"]
k["gid"] = k.groupby(GK, dropna=False).ngroup()
nf = k.groupby("gid")["free"].sum()
k["n_free"] = k["gid"].map(nf).to_numpy()
k["sup"] = k.follow & (k.n_free >= 2)
cc = ["fast", "medium", "slow"]
def bycls(mask, name):
    v = k[mask].groupby("corner_class").size().reindex(cc).fillna(0).astype(int).tolist()
    print(f"{name}: {v} total {sum(v)}")
bycls(k.sup, "supported following")
bycls(k.sup & k.close, "supported close")
# brackets
fr = k[k.free][["gid", "lap"]].drop_duplicates().sort_values(["gid", "lap"])
enc = fr.gid.to_numpy(np.int64) * 1000 + fr.lap.to_numpy(np.int64)
q = k.gid.to_numpy(np.int64) * 1000 + k.lap.to_numpy(np.int64)
i0 = np.searchsorted(enc, q, "left") - 1
i1 = np.searchsorted(enc, q, "right")
prevlap = np.where((i0 >= 0) & (enc[np.clip(i0, 0, len(enc) - 1)] // 1000 == k.gid.to_numpy()), enc[np.clip(i0, 0, len(enc) - 1)] % 1000, -999)
nextlap = np.where((i1 < len(enc)) & (enc[np.clip(i1, 0, len(enc) - 1)] // 1000 == k.gid.to_numpy()), enc[np.clip(i1, 0, len(enc) - 1)] % 1000, 99999)
k["db"] = k.lap.to_numpy() - prevlap
k["da"] = nextlap - k.lap.to_numpy()
k["brk_unl"] = (prevlap > -999) & (nextlap < 99999)
bycls(k.sup & k.close & k.brk_unl, "close bracketed unlimited")
for W in (5, 6, 8, 10):
    b = (k.db <= W) & (k.da <= W)
    k[f"b{W}"] = b
    bycls(k.sup & b, f"local W={W} supported following bracketed")
    bycls(k.sup & k.near & b, f"local W={W} near bracketed")
    bycls(k.sup & k.near & b & ~k.racecraft, f"local W={W} near bracketed, racecraft out")
bycls(k.sup & k.near, "near supported")
bycls(k.sup & k.near & ~k.racecraft, "near supported racecraft out")
bycls(k.sup & k.far & k.b5, "far bracketed W5")
# phi windows (distinct other drivers)
fd = k[k.free][["race_id", "corner_id", "lap", "driver"]].drop_duplicates()
ex = pd.concat([fd.assign(lap=fd.lap + sh, ds=abs(sh)) for sh in range(-2, 3)])
t = k[k.sup][["race_id", "corner_id", "lap", "driver", "corner_class", "close"]].reset_index()
m = t.merge(ex.rename(columns={"driver": "od"}), on=["race_id", "corner_id", "lap"], how="left")
m = m[m.od.notna() & (m.od != m.driver)]
nW = {}
for W in (0, 1, 2):
    nW[W] = m[m.ds <= W].groupby("index")["od"].nunique().reindex(t["index"]).fillna(0).to_numpy()
t["W"] = np.select([nW[0] >= 3, nW[1] >= 3, nW[2] >= 3], [0, 1, 2], -1)
print("phi windows supported following W0/W1/W2/unsup:", [int((t.W == w).sum()) for w in (0, 1, 2, -1)])
print("phi unsupported close:", int(((t.W == -1) & t.close).sum()), "of", int(t.close.sum()))
k.loc[t["index"], "W"] = t["W"].to_numpy()
# per race concentration of phi drops
pr = k[k.sup].groupby("race_id").agg(n=("W", "size"), unsup=("W", lambda x: int((x == -1).sum())))
pr["share"] = pr.unsup / pr.n
pr = pr.sort_values("share", ascending=False)
print("phi-unsupported share by race: top 8\n", pr.head(8).to_string())
print("median share", round(pr.share.median(), 4), "races with share > 0.20:", int((pr.share > 0.2).sum()),
      " top-5 races hold", round(pr.unsup.nlargest(5).sum() / pr.unsup.sum(), 3), "of drops")
cal = bpt.race_calendar()
k["circuit"] = [cal[(int(a), b)][0] for a, b in zip(k.season, k.race)]
pc = k[k.sup].groupby("circuit").agg(n=("W", "size"), unsup=("W", lambda x: int((x == -1).sum())))
pc["share"] = pc.unsup / pc.n
print("phi-unsupported share by circuit top 6\n", pc.sort_values("share", ascending=False).head(6).to_string())
# near bracketed after racecraft AND phi
bycls(k.sup & k.near & k.b5 & ~k.racecraft & (k.W >= 0), "near W5 bracketed, racecraft out, phi ok")
bycls(k.sup & k.near & ~k.b5 & ~k.racecraft & (k.W >= 0), "near one-sided, racecraft out, phi ok")
# distinct groups / baseline pairs among bracketed near (medium, slow, fast)
bb = k[k.sup & k.near & k.b5 & ~k.racecraft & (k.W >= 0)]
print("bracketed near distinct groups by class", bb.groupby("corner_class").gid.nunique().reindex(cc).tolist(),
      " distinct (group, prev, next) baselines", bb.assign(pl=bb.lap - bb.db, nl=bb.lap + bb.da)
      .groupby("corner_class")[["gid", "pl", "nl"]].apply(lambda x: len(x.drop_duplicates())).reindex(cc).tolist())
bb = bb.assign(asym=(bb.db - bb.da).abs())
print("bracketed near |db-da| distribution (share 0,1,2,3,4):", [round(float((bb.asym == a).mean()), 3) for a in range(5)])
# gap-change composition bracketed vs one-sided near
def gc(df):
    d = df.gap_s - df.prev_lap_gap_s
    pf = df.prev_lap_clear_ahead.fillna(False).astype(bool) | (df.prev_lap_gap_s >= 3)
    unk = df.prev_lap_reason.notna() | (df.prev_lap_gap_s.isna() & ~pf)
    lab = np.select([unk, pf, d < -0.1, d > 0.1], ["unknown", "from_free", "shrink", "grow"], "steady")
    return pd.Series(lab).value_counts(normalize=True).round(3).to_dict()
base = k.sup & k.near & ~k.racecraft & (k.W >= 0)
for c in cc:
    print(c, "bracketed", gc(k[base & k.b5 & (k.corner_class == c)]), "\n   one-sided", gc(k[base & ~k.b5 & (k.corner_class == c)]))
# stuck tier composition bracketed vs one-sided near
st = k.groupby(["race_id", "driver", "stint", "compound"], dropna=False)["close"].transform("mean")
k["tier"] = pd.cut(st, [-1, 0.2, 0.5, 0.8, 2], right=False, labels=["<20", "20-50", "50-80", ">=80"])
for nm, msk in (("bracketed", base & k.b5), ("one-sided", base & ~k.b5)):
    print("tier", nm, k[msk].tier.value_counts(normalize=True).round(3).sort_index().to_dict())
# free-pass leverage
gf = k.groupby("gid").agg(nf=("free", "sum"), nsup=("sup", "sum"))
k["g_has_sup"] = k.gid.map(gf.nsup > 0)
print("free passes in groups with supported following:", int((k.free & k.g_has_sup).sum()), "of", int(k.free.sum()))
# S3 population: groups >=3 free and >=1 supported near
gn = k.groupby("gid").agg(nf=("free", "sum"), nnear=("near", lambda x: 0))
nnear = k[k.sup & k.near].groupby("gid").size()
k["g_nnear"] = k.gid.map(nnear).fillna(0)
print("supported near passes in groups with >=3 free:", int((k.sup & k.near & (k.n_free >= 3)).sum()), "of", int((k.sup & k.near).sum()))
spread = k[k.free].groupby("gid")["tyre_life"].agg(lambda x: x.max() - x.min())
k["g_spread"] = k.gid.map(spread)
print("supported near in groups >=3 free and free tyre-age spread >=4:", int((k.sup & k.near & (k.n_free >= 3) & (k.g_spread >= 4)).sum()))
# mean signed distance near passes to group's free mean tyre_life
mt = k[k.free].groupby("gid")["tyre_life"].mean()
dd = (k.tyre_life - k.gid.map(mt))[k.sup & k.near]
print("near d-bar by class", k[k.sup & k.near].assign(d=dd).groupby("corner_class").d.mean().round(2).reindex(cc).tolist(),
      " far", k[k.sup & k.far].assign(d=(k.tyre_life - k.gid.map(mt))).groupby("corner_class").d.mean().round(2).reindex(cc).tolist())
# thin cells
tc = k[k.free].groupby(["race_id", "compound", "corner_class"]).driver.nunique()
print("cells", len(tc), "lt3", int((tc < 3).sum()), "eq1", int((tc == 1).sum()))
# corners per race-class
ncor = k.groupby(["race_id", "corner_class"]).corner_id.nunique()
print("race-class cells with exactly one braking corner:", ncor[ncor == 1].groupby(level=1).size().to_dict(), " of races per class",
      ncor.groupby(level=1).size().to_dict())
# cross-fit class availability for supported close, non-racecraft passes
SK = ["race_id", "driver", "stint", "compound"]
gs = k.groupby(SK + ["corner_class", "corner_id"], dropna=False)["free"].sum().rename("nfc").reset_index()
tot = gs.groupby(SK + ["corner_class"], dropna=False)["nfc"].sum().rename("T").reset_index()
gs = gs.merge(tot, on=SK + ["corner_class"])
gs["N_other"] = gs["T"] - gs["nfc"]
cl = k[k.sup & k.close & ~k.racecraft].copy()
cl = cl.merge(gs[SK + ["corner_id", "N_other"]], on=SK + ["corner_id"], how="left").rename(columns={"N_other": "N_F"})
ld = k[["race_id", "driver", "lap", "corner_id", "stint", "compound", "W"]].rename(
    columns={"driver": "leader", "lap": "leader_lap", "stint": "L_stint", "compound": "L_comp", "W": "L_W"})
cl = cl.merge(ld, on=["race_id", "leader", "leader_lap", "corner_id"], how="left")
cl = cl.merge(gs[SK + ["corner_id", "N_other"]].rename(columns={"driver": "leader", "stint": "L_stint", "compound": "L_comp",
                                                                 "N_other": "N_L"}),
              on=["race_id", "leader", "L_stint", "L_comp", "corner_id"], how="left")
# leader phi support (other drivers than the leader) at leader's lap
lw = m.copy()
n_lead = []
fdx = fd.copy()
ok_L = cl.L_stint.notna()
known = (cl.N_F >= 2) & (cl.N_L >= 2) & ok_L & (cl.W >= 0)
print("cross-fit class known (N_F>=2, N_L>=2, leader eligible, own phi ok) by class:",
      cl[known].groupby("corner_class").size().reindex(cc).tolist(), "of", cl.groupby("corner_class").size().reindex(cc).tolist())
print("  components: N_F>=2", int((cl.N_F >= 2).sum()), " leader eligible", int(ok_L.sum()), " N_L>=2", int((cl.N_L >= 2).sum()))
# old rule for comparison: leader group at c with >=2 free
cl = cl.merge(gs[SK + ["corner_id", "nfc"]].rename(columns={"driver": "leader", "stint": "L_stint", "compound": "L_comp", "nfc": "L_nfc"}),
              on=["race_id", "leader", "L_stint", "L_comp", "corner_id"], how="left")
print("  old rule (leader group at c >=2 free) among these:", int((cl.L_nfc >= 2).sum()), "of", len(cl))
# train tag among supported close
lg = k[["race_id", "driver", "lap", "corner_id", "gap_s"]].rename(columns={"driver": "leader", "lap": "leader_lap", "gap_s": "L_gap"})
pall = p[["race_id", "driver", "lap", "corner_id", "gap_s"]].rename(columns={"driver": "leader", "lap": "leader_lap", "gap_s": "L_gap"})
tr = k[k.sup & k.close & ~k.racecraft].merge(pall, on=["race_id", "leader", "leader_lap", "corner_id"], how="left")
print("train (leader's own gap <1.0, any row) among supported close non-racecraft:", int(((tr.L_gap >= 0) & (tr.L_gap < 1)).sum()), "of", len(tr))
# lap arm counts
nb = p[p.segment_basis == "brake_onset"].groupby("race_id").corner_id.nunique()
allp = p[p.segment_basis == "brake_onset"].copy()
allp["elig"] = E_[allp.index].to_numpy() & ~allp.racecraft.to_numpy()
allp["gfill"] = np.where(allp.clear_ahead.fillna(False).astype(bool) | (allp.gap_s >= 3), 3.0, allp.gap_s)
allp["isfree"] = allp.clear_ahead.fillna(False).astype(bool) | (allp.gap_s >= 3)
lp = allp.groupby(["race_id", "driver", "lap"]).agg(n=("elig", "size"), ne=("elig", "sum"), nfree=("isfree", "sum"),
                                                     med=("gfill", "median"), stint=("stint", "first"), comp=("compound", "first"))
lp = lp.reset_index()
lp["nb"] = lp.race_id.map(nb)
sc = lp[(lp.n == lp.nb) & (lp.ne == lp.nb)].copy()
sc["free"] = sc.nfree == sc.nb
sc["fol"] = (sc.med >= 0) & (sc.med < 3) & ~sc.free
sc["near"] = (sc.med >= 0.5) & (sc.med < 1.0) & ~sc.free
sc["sid"] = sc.groupby(["race_id", "driver", "stint", "comp"], dropna=False).ngroup()
fl = sc[sc.free].groupby("sid").size()
sc["nfl"] = sc.sid.map(fl).fillna(0)
sc["sup"] = sc.fol & (sc.nfl >= 3)
f2 = sc[sc.free][["sid", "lap"]].sort_values(["sid", "lap"])
e2 = f2.sid.to_numpy(np.int64) * 1000 + f2.lap.to_numpy(np.int64)
q2 = sc.sid.to_numpy(np.int64) * 1000 + sc.lap.to_numpy(np.int64)
a0 = np.searchsorted(e2, q2, "left") - 1; a1 = np.searchsorted(e2, q2, "right")
pv = np.where((a0 >= 0) & (e2[np.clip(a0, 0, len(e2) - 1)] // 1000 == sc.sid.to_numpy()), e2[np.clip(a0, 0, len(e2) - 1)] % 1000, -999)
nx = np.where((a1 < len(e2)) & (e2[np.clip(a1, 0, len(e2) - 1)] // 1000 == sc.sid.to_numpy()), e2[np.clip(a1, 0, len(e2) - 1)] % 1000, 99999)
print("lap arm: scored laps (structure only, LapTime not checked)", len(sc), "free", int(sc.free.sum()), "following", int(sc.fol.sum()),
      "supported following", int(sc.sup.sum()), "supported near", int((sc.sup & sc.near).sum()))
for W in (5, 8):
    b = (sc.lap - pv <= W) & (nx - sc.lap <= W)
    print(f"  lap arm near bracketed W={W}:", int((sc.sup & sc.near & b).sum()), " all following bracketed:", int((sc.sup & b).sum()))
print("races", k.race_id.nunique(), "circuits", k.circuit.nunique())
