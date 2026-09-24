"""Enumerate every window function in the mart lineage (compiled SQL from transform/target),
classify frame reach. Reuses ml.src.features' lineage + SQL loader."""
import sys, json, csv
sys.path.insert(0, "/Users/justin/github/off-the-pace")
from pathlib import Path
import sqlglot
from sqlglot import exp
from ml.src import features as F
man = json.loads(Path(F.MANIFEST_PATH).read_text())
nodes = man["nodes"]; tdir = Path(F.MANIFEST_PATH).parent
rows = []
for uid in sorted(F._mart_lineage(man), key=lambda u: nodes[u]["name"]):
    name = nodes[uid]["name"]
    sql = F._model_sql(nodes[uid], tdir)
    try:
        tree = sqlglot.parse_one(sql, dialect="duckdb")
    except Exception as e:
        rows.append(dict(model=name, alias="PARSE_FAIL", func=str(e)[:80])); continue
    # resolve named windows (WINDOW w AS (...))
    named = {}
    for sel in tree.find_all(exp.Select):
        for w in sel.args.get("windows") or []:
            named[w.alias_or_name if hasattr(w,'alias_or_name') else str(w.this)] = w
    for win in tree.find_all(exp.Window):
        func = win.this.sql(dialect="duckdb")[:70]
        # enclosing alias
        p = win; alias = ""
        while p is not None:
            if isinstance(p, exp.Alias): alias = p.alias; break
            p = p.parent
        spec = win.args.get("spec")
        part = [x.sql() for x in (win.args.get("partition_by") or [])]
        order = win.args.get("order").sql() if win.args.get("order") else ""
        ref = win.args.get("alias")
        frame = spec.sql(dialect="duckdb") if spec is not None else ""
        if ref is not None and not part and not order and not frame:
            frame = f"named window {ref.sql()}"
        is_lead = bool(list(win.find_all(exp.Lead)))
        is_follow = spec is not None and ("FOLLOWING" in (spec.args.get("start_side") or "") or "FOLLOWING" in (spec.args.get("end_side") or ""))
        whole = (not order) and (spec is None) and ref is None and func.split("(")[0].upper() not in ("ROW_NUMBER",)
        default_frame = bool(order) and spec is None
        rows.append(dict(model=name, alias=alias, func=func, partition=",".join(part), order=order,
                         frame=frame, lead=is_lead, following=is_follow, whole_partition=whole,
                         default_frame_range_to_current=default_frame))
out = Path(sys.argv[1])
with out.open("w", newline="") as fh:
    w = csv.DictWriter(fh, fieldnames=["model","alias","func","partition","order","frame","lead","following","whole_partition","default_frame_range_to_current"])
    w.writeheader(); [w.writerow(r) for r in rows]
print(len(rows), "windows")
for r in rows:
    if r.get("lead") or r.get("following") or r.get("whole_partition"):
        print(f"{r['model']:42s} {r['alias']:32s} lead={r['lead']!s:5} fol={r['following']!s:5} whole={r['whole_partition']!s:5} P[{r['partition']}] O[{r['order'][:40]}] F[{r['frame'][:60]}] :: {r['func'][:50]}")
