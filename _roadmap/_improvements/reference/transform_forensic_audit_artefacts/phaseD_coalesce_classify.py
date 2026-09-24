"""Classify every COALESCE / IFNULL / NULLIF in transform/models/**.sql by fallback kind;
flag mart-lineage membership. Balanced-paren extraction over the raw file (line numbers preserved)."""
import re, csv, sys, json
from pathlib import Path
sys.path.insert(0, "/Users/justin/github/off-the-pace")
from ml.src import features as F
man = json.loads(Path(F.MANIFEST_PATH).read_text())
lineage = {man["nodes"][u]["name"] for u in F._mart_lineage(man)}
root = Path("/Users/justin/github/off-the-pace/transform/models")
def strip_comments(text):
    return re.sub(r"--[^\n]*", lambda m: " " * len(m.group(0)), text)
def split_top(s):
    out, depth, cur = [], 0, ""
    for ch in s:
        if ch == "(": depth += 1
        if ch == ")": depth -= 1
        if ch == "," and depth == 0: out.append(cur.strip()); cur = ""
        else: cur += ch
    out.append(cur.strip()); return out
def kind(fn, args):
    if fn == "NULLIF": return "nullif_guard" if re.fullmatch(r"0(\.0+)?", args[-1]) else "nullif_other"
    last = args[-1].strip()
    if re.fullmatch(r"-?0(\.0+)?", last): return "numeric_zero"
    if re.fullmatch(r"-?\d+(\.\d+)?", last): return f"numeric_sentinel:{last}"
    if last.upper() in ("FALSE", "TRUE"): return f"bool:{last.upper()}"
    if re.fullmatch(r"'[^']*'", last): return f"string:{last}"
    if last.upper() == "NULL": return "null"
    return "column_or_expr_fallback"
rows = []
for f in sorted(root.rglob("*.sql")):
    raw = f.read_text(); text = strip_comments(raw)
    for m in re.finditer(r"\b(COALESCE|IFNULL|NULLIF)\s*\(", text, re.I):
        i = m.end(); depth = 1; j = i
        while j < len(text) and depth:
            depth += {"(": 1, ")": -1}.get(text[j], 0); j += 1
        inner = text[i:j-1]; args = split_top(inner)
        line = raw.count("\n", 0, m.start()) + 1
        model = f.stem
        rows.append(dict(model=model, line=line, fn=m.group(1).upper(), kind=kind(m.group(1).upper(), args),
                         in_ml_lineage=model in lineage, first_arg=re.sub(r"\s+", " ", args[0])[:70],
                         fallback=re.sub(r"\s+", " ", args[-1])[:50]))
w = csv.DictWriter(open(sys.argv[1], "w", newline=""), fieldnames=list(rows[0]))
w.writeheader(); w.writerows(rows)
from collections import Counter
print("total", len(rows), "in ML lineage", sum(r["in_ml_lineage"] for r in rows))
print(Counter(r["kind"].split(":")[0] for r in rows))
print("lineage:", Counter(r["kind"].split(":")[0] for r in rows if r["in_ml_lineage"]))
for r in rows:
    if r["in_ml_lineage"] and r["kind"].split(":")[0] in ("numeric_zero","numeric_sentinel","string","bool"):
        print(f"{r['model']}:{r['line']} {r['kind']:28s} {r['first_arg']}")
