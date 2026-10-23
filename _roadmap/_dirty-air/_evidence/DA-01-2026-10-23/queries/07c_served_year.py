"""DA-01 step 7c. The MultiViewer circuit API falls back to another year when
the requested year has no layout: the payload's own `year` field says which
year was served. For each 2018-2020 race, record served year and marshal
sector count. Usage: python -I 07c_served_year.py <scratch_dir>"""
import csv, json, os, sys
S = sys.argv[1]
rows = list(csv.DictReader(open(os.path.join(S, "out", "07_marshal_sectors_by_race_2018_2020.csv"))))
out = []
for r in rows:
    k, y = r["circuit_key"], r["race_year"]
    p = os.path.join(S, "dl", f"c{k}_{y}.json")
    d = json.load(open(p)) if k and os.path.exists(p) else {}
    out.append({**r, "served_year": d.get("year"), "served_meeting": d.get("meetingName"),
                "same_year": str(d.get("year")) == str(y)})
with open(os.path.join(S, "out", "07c_served_year_by_race_2018_2020.csv"), "w", newline="") as fh:
    w = csv.DictWriter(fh, fieldnames=list(out[0].keys())); w.writeheader(); w.writerows(out)
from collections import Counter
print(Counter((o["race_year"], o["same_year"], int(o["marshal_sectors"] or 0) > 0) for o in out))
for o in out:
    if not o["same_year"]: print(o["race_year"], o["race_slug"], "served", o["served_year"], o["marshal_sectors"])
