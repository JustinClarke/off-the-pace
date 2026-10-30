import sys, re, unicodedata
sys.path.insert(0, "/Users/justin/github/off-the-pace/transform")
from tasks.wake_calibration import build_pass_table as bpt
import pyarrow.parquet as pq, pandas as pd
R = "/Users/justin/github/off-the-pace/_roadmap/_wake-calibration/_artifacts"
p = pd.concat([pq.read_table(f"{R}/WC-03-run/pass-table/pass_table_{s}.parquet", columns=["season","race_id","race","segment_basis","reason","tag","stint","compound"]).to_pandas() for s in (2022,2023)])
tag = p.tag.fillna("").astype(str)
k = p[p.reason.isna() & (p.segment_basis=="brake_onset") & ~tag.str.contains("yielding") & p.stint.notna() & p.compound.notna()]
cal = bpt.race_calendar()
m = {}
for (s, r, rid) in k[["season","race","race_id"]].drop_duplicates().itertuples(index=False):
    key = cal[(int(s), r)][0]
    assert unicodedata.is_normalized("NFC", key), key
    m.setdefault(key, []).append(rid)
got = [(c, sorted(v, key=lambda x: x.encode())) for c, v in sorted(m.items(), key=lambda x: x[0].encode())]
txt = open("/Users/justin/github/off-the-pace/_roadmap/_wake-calibration/wi/WC-10-discovery-preregistration-DRAFT.md", encoding="utf-8").read()
app = txt.split("## Appendix A")[1]
rows = re.findall(r"^\| (\d+) \| ([^|]+?) \| ([^|]+?) \|$", app, re.M)
want = [(unicodedata.normalize("NFC", c.strip()), [x.strip() for x in r.split(",")]) for _, c, r in rows]
print("appendix rows", len(want), "computed", len(got), "EQUAL:", want == got)
print("appendix text NFC:", unicodedata.is_normalized("NFC", app))
# all 2022-23 calendar events vs races present
allev = sorted([(s, r) for (s, r) in cal if s in (2022, 2023)])
present = set(map(tuple, k[["season","race"]].drop_duplicates().astype({"season":int}).itertuples(index=False)))
print("calendar 2022-23 events not in kept passes:", [e for e in allev if e not in present])
print("races present in pass table rows (any reason) but no kept braking pass:",
      sorted(set(p.race_id) - set(k.race_id)))
