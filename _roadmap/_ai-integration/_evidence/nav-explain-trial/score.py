#!/usr/bin/env python3
"""Score raw-run.json against expected.json. Usage: python3 score.py"""
import json, os, re, collections
D = os.path.dirname(os.path.abspath(__file__))
exp = {e["id"]: e for e in json.load(open(f"{D}/expected.json"))}
run = json.load(open(f"{D}/raw-run.json"))["records"]
SLUG = {"/tyre-strategy/survival": "tyre-cliff-survival", "/constructors/structural": "constructor-structural-pace", "/ml/blind-test": "blind-test-scoreboard"}
rows = []
for r in run:
    qid = r["id"].split(".")[0]
    e = exp[qid]; g = e["group"]; t = r["tools"]
    row = {"id": r["id"], "group": g, "q": r["question"], "tools": [f'{x["name"]}:{x["status"]}' for x in t]}
    if g == "navigate":
        nav = [x for x in t if x["name"] == "navigate"]
        row["called_nav"] = bool(nav)
        row["shipped_ok"] = any(x["status"] == "ok" for x in nav)
        row["route_correct"] = any(x["status"] == "ok" and x["arguments"].get("route") == e["expected_route"] for x in nav)
        row["link"] = r["links"]
    elif g == "explain":
        ex = [x for x in t if x["name"] == "explain_page" and x["status"] == "ok"]
        want = {e["expected_route"], SLUG[e["expected_route"]]}
        row["called_explain"] = bool(ex)
        row["right_page"] = any(x["arguments"].get("page") in want for x in ex)
        row["nums_in_answer"] = re.findall(r"\d+(?:\.\d+)?", r["answer"])
    else:
        row["checker_ok"] = r["checker"]["ok"]
        row["ungrounded_final"] = r["grounding"]["ungrounded"]
        row["repaired"] = r["repaired"]
        row["first_draft_ungrounded"] = (r["first_draft"] or {}).get("ungrounded", [])
        row["cards_cited"] = r["cards_cited"]
        row["called_cards"] = any(x["name"] == "get_fact_cards" and x["status"] == "ok" for x in t)
    row["status"] = r["status"]
    rows.append(row)
json.dump(rows, open(f"{D}/scored.json", "w"), indent=1)
c = collections.defaultdict(lambda: collections.Counter())
for x in rows:
    g = x["group"]; c[g]["n"] += 1
    for k in ("called_nav", "shipped_ok", "route_correct", "called_explain", "right_page", "checker_ok", "called_cards"):
        if x.get(k): c[g][k] += 1
    if g == "combine":
        if x["ungrounded_final"]: c[g]["ungrounded_final"] += 1
        if x["first_draft_ungrounded"]: c[g]["first_draft_ungrounded"] += 1
        if x["repaired"]: c[g]["repaired"] += 1
        if x["checker_ok"] and not x["ungrounded_final"]: c[g]["clean"] += 1
for g, v in c.items(): print(g, dict(v))
