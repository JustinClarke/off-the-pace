#!/usr/bin/env python3
"""Render and validate the fixes build log.

    python3 _roadmap/_fixes/status/board.py                # the board
    python3 _roadmap/_fixes/status/board.py --check        # invariants only; exit 1 on failure
    python3 _roadmap/_fixes/status/board.py --order        # the ordered task list, to stdout
    python3 _roadmap/_fixes/status/board.py --write-order  # ...and into BUILD-ORDER.md
    python3 _roadmap/_fixes/status/board.py --watch        # the watch list in full
    python3 _roadmap/_fixes/status/board.py --ship         # exit 1 while a ship-blocker is open

build-log.json is the authoritative state. This script never writes to it -- it is a
reader, so a malformed edit surfaces as a failed check rather than as silent drift.

Adapted from _roadmap/_improvements/status/board.py. What differs, and why:
  * six stages, not eight: there is no statistical gate to pass, so GATED is gone and a
    dependency is met by LANDED/CLOSED only;
  * `blocked_by_decision` may be one id or a list (WI-01 waits on two rulings);
  * every item names its WI doc (`doc`) and the findings it fixes (`findings`), and
    --check confirms the doc exists -- an item with no doc is not runnable;
  * the task list puts work you can run now ahead of work waiting on a human ruling,
    otherwise "the pointer is the next thing to run" would be false the moment the first
    item in the table is decision-blocked;
  * `watch_rules` hold what is being kept an eye on but is not an item or a ruling:
    ship-blockers, uncommitted or unreviewed work, stale artifacts, standing hazards,
    unverified claims, gate gaps and known debt. Items and decisions say what to build and
    what to rule; the watch list is where an exception lives so it cannot fall off the
    board when the item that raised it lands. Like the task list, the watch list is
    computed: each rule's `trigger` is evaluated against the items, the decisions and the
    other rules (see generate_watch_list), and no status is stored. --check validates the
    rules and their references (an open ship-blocker is not a malformed log); --ship is the
    gate to run before publishing.
  * every watch rule that is not cleared names a `recommended_model` from
    `watch_model_vocabulary` (haiku / sonnet / opus): the smallest model that can work the
    rule, so a sweep does not spend opus on "is it committed?".
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).parent
FIXES = HERE.parent                      # _roadmap/_fixes -- item `doc` paths are relative to this
LOG = HERE / "build-log.json"
ORDER_DOC = HERE / "BUILD-ORDER.md"
BEGIN = "<!-- BEGIN GENERATED TASKS -- do not hand-edit; `board.py --write-order` -->"
END = "<!-- END GENERATED TASKS -->"
STALE = ("BUILD-ORDER.md's generated task list is stale -- "
         "run `board.py --write-order`")
TERMINAL = {"CLOSED", "LANDED"}
MARK = {"SPEC": "·", "BUILDING": "~", "MEASURED": "=",
        "LANDED": "x", "BLOCKED": "!", "CLOSED": "x"}
CMD = "python3 _roadmap/_fixes/status/board.py"


def decs(item: dict) -> list[str]:
    """`blocked_by_decision` normalised to a list (it may be absent, one id, or several)."""
    d = item.get("blocked_by_decision")
    if not d:
        return []
    return [d] if isinstance(d, str) else list(d)


def open_decs(item: dict, decisions: dict[str, dict]) -> list[str]:
    return [d for d in decs(item) if decisions.get(d, {}).get("status") == "OPEN"]


# --- The watch list: computed from `watch_rules`, like the task list from `items` ---------
#
# Each rule carries a `trigger`. `clear` (required) says when the rule stops being owed;
# `raise` (optional) keeps it off the list until it holds, so a follow-up can be registered
# before the item that owes it lands. Both are conditions in one small grammar:
#
#   "manual"                             the rule records `resolved` + `resolution`: a person
#                                        saw a fact the log cannot (a commit, a re-export, a
#                                        rebuild, a ruling given outside `decisions`)
#   {"item": "WI-08"}                    the item is LANDED or CLOSED
#   {"item": "WI-08", "stage": [...]}    the item is in one of the named stages
#   {"decision": "FD4"}                  the decision is RESOLVED
#   {"watch": "W8"}                      that watch rule is cleared
#   {"all": [...]} / {"any": [...]}      every / at least one listed condition holds
#
# A rule is CLEARED when `clear` holds, DORMANT while `raise` does not, and OPEN otherwise.

MANUAL = "manual"
WATCH_FIELDS = ("id", "raised", "kind", "title", "detail", "clears_when", "trigger")
WATCH_KEYS = set(WATCH_FIELDS) | {"item", "decision", "resolved", "resolution",
                                  "recommended_model"}
CONDITION_HELP = '"manual", {"item"}, {"decision"}, {"watch"}, {"all": [...]} or {"any": [...]}'


def trig(rule: dict) -> dict:
    """A rule's trigger, or {} when it is missing or malformed (--check names that)."""
    t = rule.get("trigger")
    return t if isinstance(t, dict) else {}


def stages_of(cond: dict) -> list[str]:
    s = cond.get("stage", sorted(TERMINAL))
    return [s] if isinstance(s, str) else s if isinstance(s, list) else []


def leaves(cond):
    """The non-combinator conditions inside `cond`."""
    if isinstance(cond, dict) and ("all" in cond or "any" in cond):
        for op in ("all", "any"):
            if isinstance(cond.get(op), list):
                for sub in cond[op]:
                    yield from leaves(sub)
    elif cond is not None:
        yield cond


class WatchRules:
    """Evaluates watch-rule triggers against one log. Never modifies the log."""

    def __init__(self, log: dict):
        self.items = {i["id"]: i for i in log["items"]}
        self.decisions = {d["id"]: d for d in log["decisions"]}
        self.rules = {r.get("id"): r for r in log.get("watch_rules", [])}
        self._cleared: dict[str, bool] = {}
        self._visiting: set[str] = set()

    def holds(self, cond, rule: dict) -> bool:
        """Whether `cond` holds. Anything malformed is False, so a bad rule stays OPEN."""
        if cond == MANUAL:
            return bool(rule.get("resolved") and rule.get("resolution"))
        if not isinstance(cond, dict):
            return False
        if "all" in cond:
            return isinstance(cond["all"], list) and all(self.holds(c, rule) for c in cond["all"])
        if "any" in cond:
            return isinstance(cond["any"], list) and any(self.holds(c, rule) for c in cond["any"])
        if "item" in cond:
            return self.items.get(cond["item"], {}).get("stage") in stages_of(cond)
        if "decision" in cond:
            return self.decisions.get(cond["decision"], {}).get("status") == "RESOLVED"
        if "watch" in cond:
            return self.cleared(cond["watch"])
        return False

    def cleared(self, wid: str) -> bool:
        if wid not in self._cleared:
            if wid in self._visiting or wid not in self.rules:
                return False                   # a cycle or a dead reference; --check names it
            self._visiting.add(wid)
            rule = self.rules[wid]
            self._cleared[wid] = self.holds(trig(rule).get("clear"), rule)
            self._visiting.discard(wid)
        return self._cleared[wid]

    def status(self, rule: dict) -> str:
        if self.cleared(rule.get("id")):
            return "CLEARED"
        t = trig(rule)
        if "raise" in t and not self.holds(t["raise"], rule):
            return "DORMANT"
        return "OPEN"

    def describe(self, cond, rule: dict) -> str:
        """`cond` in words, each leaf marked with whether it holds now."""
        def mark(c) -> str:
            return "✓" if self.holds(c, rule) else "✗"
        if cond == MANUAL:
            return f"resolved by hand {mark(cond)}"
        if not isinstance(cond, dict):
            return f"<not a condition: {cond!r}>"
        for op, word in (("all", "all of"), ("any", "any of")):
            if isinstance(cond.get(op), list):
                return f"{word} (" + "; ".join(self.describe(c, rule) for c in cond[op]) + ")"
        if "item" in cond:
            now = self.items.get(cond["item"], {}).get("stage", "missing")
            return f"{cond['item']} {'/'.join(stages_of(cond))} (now {now}) {mark(cond)}"
        if "decision" in cond:
            now = self.decisions.get(cond["decision"], {}).get("status", "missing")
            return f"{cond['decision']} RESOLVED (now {now}) {mark(cond)}"
        if "watch" in cond:
            return f"{cond['watch']} cleared {mark(cond)}"
        return f"<not a condition: {cond!r}>"


def generate_watch_list(log: dict) -> list[dict]:
    """Every watch rule with its computed `status` -- OPEN, CLEARED or DORMANT -- and, when
    cleared, `cleared_by`: "hand" if a resolution is recorded, else "trigger" (the log itself
    shows the condition met). Returns copies; the rules in the log are not touched."""
    ev = WatchRules(log)
    out: list[dict] = []
    for rule in log.get("watch_rules", []):
        w = dict(rule, status=ev.status(rule))
        if w["status"] == "CLEARED":
            w["cleared_by"] = "hand" if rule.get("resolution") else "trigger"
        out.append(w)
    return out


def open_watch(log: dict) -> list[dict]:
    """Open watch entries, most urgent kind first (vocabulary order), then in the order raised."""
    kinds = list(log.get("watch_vocabulary", {}))
    rank = {k: n for n, k in enumerate(kinds)}
    live = [w for w in generate_watch_list(log) if w["status"] == "OPEN"]
    return sorted(live, key=lambda w: (rank.get(w.get("kind"), 99), w.get("raised", ""),
                                       len(w.get("id", "")), w.get("id", "")))


def condition_errors(cond, where: str, ev: WatchRules, stages: set[str]) -> list[str]:
    """Why `cond` is not a valid condition (empty when it is)."""
    if cond == MANUAL:
        return []
    if not isinstance(cond, dict) or not cond:
        return [f"{where}: {cond!r} is not a condition -- use {CONDITION_HELP}"]
    keys = set(cond)
    if keys in ({"all"}, {"any"}):
        subs = cond[next(iter(keys))]
        if not isinstance(subs, list) or not subs:
            return [f"{where}: {next(iter(keys))!r} needs a non-empty list"]
        return [e for c in subs for e in condition_errors(c, where, ev, stages)]
    if "item" in keys and keys <= {"item", "stage"}:
        if cond["item"] not in ev.items:
            return [f"{where}: names item {cond['item']}, which does not exist"]
        if not stages_of(cond):
            return [f"{where}: stage must be a stage name or a non-empty list of them"]
        return [f"{where}: stage {s!r} not in stage_vocabulary"
                for s in stages_of(cond) if s not in stages]
    if keys == {"decision"}:
        return ([] if cond["decision"] in ev.decisions else
                [f"{where}: names decision {cond['decision']}, which does not exist"])
    if keys == {"watch"}:
        return ([] if cond["watch"] in ev.rules else
                [f"{where}: names watch rule {cond['watch']}, which does not exist"])
    return [f"{where}: {cond!r} is not a condition -- use {CONDITION_HELP}"]


def check_watch(log: dict, items: dict, decisions: dict) -> list[str]:
    """The watch rules parse and every reference resolves. An open rule is not a failure --
    that is what the list is for."""
    if "watch" in log:
        return ["build-log.json still has a `watch` list: it is `watch_rules` now, one "
                "`trigger` per entry and no stored `status` (see BUILD-ORDER.md)"]
    if "watch_rules" not in log or "watch_vocabulary" not in log:
        return ["build-log.json has no `watch_rules` or `watch_vocabulary`"]
    ev = WatchRules(log)
    kinds = set(log["watch_vocabulary"])
    stages = set(log["stage_vocabulary"])
    wmodels = set(log.get("watch_model_vocabulary", {}))
    bad: list[str] = []
    seen: set[str] = set()
    for r in log["watch_rules"]:
        wid = r.get("id", "?")
        if wid in seen:
            bad.append(f"{wid}: duplicate watch id")
        seen.add(wid)
        if rm := r.get("recommended_model"):
            if rm not in wmodels:
                bad.append(f"{wid}: recommended_model {rm!r} not in watch_model_vocabulary")
        elif wid in ev.rules and not ev.cleared(wid):
            bad.append(f"{wid}: live watch rule has no recommended_model")
        for f in WATCH_FIELDS:
            if not r.get(f):
                bad.append(f"{wid}: watch rule has no {f!r}")
        if "status" in r:
            bad.append(f"{wid}: has a stored `status` -- status is computed from `trigger`; "
                       f"to clear a manual rule, record `resolved` and `resolution`")
        elif extra := sorted(set(r) - WATCH_KEYS):
            bad.append(f"{wid}: unknown key(s) {', '.join(extra)}")
        if r.get("kind") and r["kind"] not in kinds:
            bad.append(f"{wid}: kind {r['kind']!r} not in watch_vocabulary")
        if r.get("item") and r["item"] not in items:
            bad.append(f"{wid}: names item {r['item']}, which does not exist")
        if r.get("decision") and r["decision"] not in decisions:
            bad.append(f"{wid}: names decision {r['decision']}, which does not exist")

        t = r.get("trigger")
        if t is not None and (not isinstance(t, dict) or "clear" not in t
                              or set(t) - {"clear", "raise"}):
            bad.append(f"{wid}: trigger must be {{\"clear\": <condition>}}, "
                       f"optionally with \"raise\": <condition>")
            continue
        t = t or {}
        for part in ("clear", "raise"):
            if part in t:
                bad += condition_errors(t[part], f"{wid} trigger.{part}", ev, stages)
        if MANUAL in leaves(t.get("raise")):
            bad.append(f"{wid}: trigger.raise uses \"manual\" -- a rule is raised by the log, "
                       f"not by its own resolution")
        if bool(r.get("resolved")) != bool(r.get("resolution")):
            bad.append(f"{wid}: `resolved` and `resolution` must be recorded together")
        elif r.get("resolution") and "clear" in t:
            if MANUAL not in leaves(t["clear"]):
                bad.append(f"{wid}: records a resolution, but its trigger has no \"manual\" "
                           f"to read it")
            elif not ev.cleared(wid):
                bad.append(f"{wid}: resolved by hand, but the rest of its trigger is not met: "
                           f"{ev.describe(t['clear'], r)}")

    # A rule that waits on itself through {"watch": ...} can never clear.
    graph = {r.get("id"): {c["watch"] for part in ("clear", "raise")
                           for c in leaves(trig(r).get(part))
                           if isinstance(c, dict) and "watch" in c}
             for r in log["watch_rules"]}
    for start, refs in graph.items():
        stack, visited = list(refs), set()
        while stack:
            n = stack.pop()
            if n == start:
                bad.append(f"{start}: its trigger waits on itself through watch references")
                break
            if n not in visited and n in graph:
                visited.add(n)
                stack.extend(graph[n])
    return bad


def check(log: dict) -> list[str]:
    """Every invariant the rules assert, as a list of failures."""
    items = {i["id"]: i for i in log["items"]}
    decisions = {d["id"]: d for d in log["decisions"]}
    groups = {g["id"] for g in log["groups"]}
    stages = set(log["stage_vocabulary"])
    models = set(log["model_vocabulary"])
    bad: list[str] = []

    if len(items) != len(log["items"]):
        bad.append("duplicate item ids")

    ptr = log.get("pointer")
    if ptr is None:
        pass                                  # all work is terminal; no active item
    elif ptr not in items:
        bad.append(f"pointer {ptr!r} names no item")
    elif items[ptr]["stage"] in TERMINAL:
        bad.append(f"pointer {ptr} sits on a terminal item ({items[ptr]['stage']})")

    for i in log["items"]:
        iid = i["id"]
        if i["stage"] not in stages:
            bad.append(f"{iid}: stage {i['stage']!r} not in the vocabulary")
        if i["group"] not in groups:
            bad.append(f"{iid}: group {i['group']!r} does not exist")
        for dep in i["depends_on"]:
            if dep not in items:
                bad.append(f"{iid}: depends on {dep}, which does not exist")
        for d in decs(i):
            if d not in decisions:
                bad.append(f"{iid}: blocked by {d}, which is not a recorded decision")
            elif decisions[d]["status"] == "OPEN" and iid not in decisions[d]["blocking"]:
                bad.append(f"{iid}: waits on {d} but {d}.blocking does not list it")
        if i["stage"] == "BLOCKED":
            unmet = [d for d in i["depends_on"]
                     if d in items and items[d]["stage"] not in TERMINAL]
            if not unmet and not open_decs(i, decisions):
                bad.append(f"{iid}: BLOCKED with no unmet dependency and no open decision")
        if i["stage"] == "CLOSED" and not i.get("closed"):
            bad.append(f"{iid}: CLOSED without a date")
        if i["stage"] not in TERMINAL:
            if not i.get("cost"):
                bad.append(f"{iid}: live item with no cost estimate")
            if not i.get("model"):
                bad.append(f"{iid}: live item with no model")
            elif i["model"] not in models:
                bad.append(f"{iid}: model {i['model']!r} not in the vocabulary")
            if not i.get("findings"):
                bad.append(f"{iid}: live item names no findings")
            if not i.get("doc") or not (FIXES / i["doc"]).exists():
                bad.append(f"{iid}: doc {i.get('doc')!r} does not exist -- item is not runnable")

    for d in log["decisions"]:
        if d["status"] == "RESOLVED" and not (d.get("resolved") and d.get("resolution")):
            bad.append(f"{d['id']}: RESOLVED without a date and a resolution")
        for b in d["blocking"]:
            if b not in items:
                bad.append(f"{d['id']}: blocks {b}, which does not exist")

    bad += check_watch(log, items, decisions)

    # Staleness is only meaningful for a valid log: render_order assumes one, and a
    # malformed log has already been reported above.
    if not bad and ORDER_DOC.exists():
        doc = ORDER_DOC.read_text()
        if BEGIN in doc and END in doc:
            cur = BEGIN + doc.split(BEGIN, 1)[1].split(END, 1)[0] + END
            if cur.strip() != render_order(log).strip():
                bad.append(STALE)

    if not log["history"]:
        bad.append("history is empty -- every session appends one entry")
    else:
        last = log["history"][-1]
        for field in ("date", "landed", "verified", "assumed", "gates_run", "next_command"):
            if not last.get(field):
                bad.append(f"latest history entry is missing {field!r} (handoff protocol)")
    return bad


def plan(log: dict) -> list[dict]:
    """Live items in runnable order: dependencies first, then runnable-now before
    waiting-on-a-human, then group order, then id.

    A topological sort, so the list can be read top-down as "do this, then this".
    Ties break on `order_hint` first (the escape hatch for a cheap item whose timing
    matters more than its group -- use sparingly), then whether the item is waiting on one
    of your rulings -- directly or through something it depends on -- then the order groups
    are declared in the log. Dependencies always win over all three.
    """
    items = {i["id"]: i for i in log["items"]}
    decisions = {d["id"]: d for d in log["decisions"]}
    gorder = {g["id"]: n for n, g in enumerate(log["groups"])}
    live = [i for i in log["items"] if i["stage"] not in TERMINAL]

    def human_gated(i: dict) -> bool:
        return bool(open_decs(i, decisions)) or any(
            human_gated(items[d]) for d in i["depends_on"]
            if d in items and items[d]["stage"] not in TERMINAL)

    def key(i: dict) -> tuple:
        return (i.get("order_hint", 99), 1 if human_gated(i) else 0,
                gorder.get(i["group"], 99), i["id"])

    ordered: list[dict] = []
    placed: set[str] = {i["id"] for i in log["items"] if i["stage"] in TERMINAL}
    pool = sorted(live, key=key)
    while pool:
        ready = [i for i in pool if all(d in placed for d in i["depends_on"])]
        if not ready:                          # dependency cycle: emit the rest rather than hang
            ordered.extend(pool)
            break
        nxt = ready[0]
        ordered.append(nxt)
        placed.add(nxt["id"])
        pool.remove(nxt)
    return ordered


def waiting_on(i: dict, items: dict, decisions: dict) -> list[str]:
    out = [d for d in i["depends_on"] if items.get(d, {}).get("stage") not in TERMINAL]
    out += [f"**{d}** (human call)" for d in open_decs(i, decisions)]
    return out


def render_order(log: dict) -> str:
    """The generated task list. Derived from the log; never hand-edited."""
    items = {i["id"]: i for i in log["items"]}
    decisions = {d["id"]: d for d in log["decisions"]}
    ptr = log.get("pointer")
    seq = plan(log)

    out: list[str] = [BEGIN, ""]
    out.append(f"_Generated from [`build-log.json`](build-log.json) at `updated: {log['updated']}`."
               f" Run `{CMD} --write-order` after any edit to the log._")
    out.append("")
    done = [i for i in log["items"] if i["stage"] in TERMINAL]
    blocked = sum(1 for i in seq if i["stage"] == "BLOCKED")
    out.append(f"**{len(seq)} live items** ({blocked} blocked). "
               f"The pointer is on **{ptr}** — that is the one to run next; the rest of the "
               f"order is what becomes runnable after it, with anything waiting on one of your "
               f"rulings sorted behind the work that isn't. "
               f"{len(done)} terminal items are finished and not listed here — "
               f"run `board.py` for the per-group view, or read their `closed` field in "
               f"[`build-log.json`](build-log.json).")
    out.append("")
    out.append("| # | Item | Group | Stage | Cost | Model | Fixes | Task | Waiting on |")
    out.append("| ---: | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |")
    for n, i in enumerate(seq, 1):
        wait = ", ".join(waiting_on(i, items, decisions)) or "—"
        mark = " ▶" if i["id"] == ptr else ""
        cell = f"[{i['id']}](../{i['doc']}){mark}"
        out.append(f"| {n} | {cell} | {i['group']} | {i['stage']} | {i.get('cost','—')} "
                   f"| `{i.get('model','—')}` | {', '.join(i['findings'])} | {i['title']} | {wait} |")
    out.append("")

    out.append("### Which model to run it on")
    out.append("")
    out.append("Recorded per item in the log, not chosen at the keyboard, so the choice is "
               "reviewable and moves with the item rather than with whoever picks it up.")
    out.append("")
    for name, why in log["model_vocabulary"].items():
        out.append(f"- **`{name}`** — {why}")
    out.append("")

    if open_d := [d for d in log["decisions"] if d["status"] == "OPEN"]:
        out.append("### Open decisions — these are yours, not tasks")
        out.append("")
        for d in open_d:
            blocks = ", ".join(f"`{b}`" for b in d["blocking"]) if d["blocking"] else "nothing"
            rec = f" _Recommended: {d['recommendation']}_" if d.get("recommendation") else ""
            out.append(f"- **{d['id']}** (blocks {blocks}) — {d['question']}{rec}")
        out.append("")

    if watch := open_watch(log):
        ships = sum(1 for w in watch if w["kind"] == "ship-blocker")
        out.append("### Watch list — kept an eye on, not tasks and not rulings")
        out.append("")
        out.append("_Generated from the watch rules in [`build-log.json`](build-log.json) "
                   "(`watch_rules`); watch entries update automatically as items land or "
                   "decisions resolve. A rule whose trigger needs something the log cannot see "
                   "(a commit, a re-export, a rebuild, your ruling) stays open until its "
                   "`resolved` and `resolution` are recorded._")
        out.append("")
        out.append(f"**{len(watch)} open** ({ships} ship-blocker{'s' if ships != 1 else ''}). "
                   f"Full detail: `{CMD} --watch`. `{CMD} --ship` exits 1 while a "
                   f"ship-blocker is open.")
        out.append("")
        wm = log.get("watch_model_vocabulary", {})
        tally = ", ".join(f"{sum(1 for w in watch if w.get('recommended_model') == m)} {m}"
                          for m in wm)
        out.append("Each watch rule is tagged with the recommended model (haiku/sonnet/opus) "
                   f"for token efficiency ({tally}). The tag is the smallest model that can work "
                   "the rule to its `clears_when`; step up a tier the moment the rule turns out "
                   "to leave a choice open that the tag assumed was made.")
        out.append("")
        for name, why in wm.items():
            out.append(f"- **`{name}`** — {why}")
        out.append("")
        out.append("| ID | Kind | Item | Model | What | Clears when |")
        out.append("| :--- | :--- | :--- | :--- | :--- | :--- |")

        def cell(s: str) -> str:
            return s.replace("|", "/").replace("\n", " ")
        for w in watch:
            ref = ", ".join(x for x in (w.get("item"), w.get("decision")) if x) or "—"
            model = f"`{w['recommended_model']}`" if w.get("recommended_model") else "—"
            out.append(f"| {w['id']} | {w['kind']} | {ref} | {model} | {cell(w['title'])} "
                       f"| {cell(w['clears_when'])} |")
        out.append("")

    # Terminal items are deliberately NOT listed: this file answers "what do I run next".
    # Their reasons live in build-log.json's `closed` field; `board.py` shows them as [x].
    out.append(END)
    return "\n".join(out)


def write_order(log: dict) -> str:
    """Splice the generated block into BUILD-ORDER.md between its markers."""
    doc = ORDER_DOC.read_text()
    block = render_order(log)
    if BEGIN in doc and END in doc:
        head, rest = doc.split(BEGIN, 1)
        _, tail = rest.split(END, 1)
        doc = head + block + tail
    else:
        doc = doc.rstrip() + "\n\n" + block + "\n"
    ORDER_DOC.write_text(doc)
    return (f"wrote {len(plan(log))} live items and {len(open_watch(log))} open watch entries "
            f"into {ORDER_DOC.name}")


def board(log: dict) -> None:
    items = {i["id"]: i for i in log["items"]}
    decisions = {d["id"]: d for d in log["decisions"]}
    ptr = log.get("pointer")
    watch = open_watch(log)
    ships = sum(1 for w in watch if w["kind"] == "ship-blocker")
    print(f"\n  {log['project']}    updated {log['updated']}    next: {ptr}"
          f"    watch: {len(watch)} open ({ships} ship-blocker{'s' if ships != 1 else ''})\n")

    for g in log["groups"]:
        mine = [i for i in log["items"] if i["group"] == g["id"]]
        if not mine:
            continue
        live = [i for i in mine if i["stage"] not in TERMINAL]
        tag = "  (parallel)" if g.get("parallel") else ""
        print(f"  {g['id']} {g['title']}{tag}   [{len(mine) - len(live)}/{len(mine)} terminal]")
        for i in mine:
            arrow = "▶" if i["id"] == ptr else " "
            why = waiting_on(i, items, decisions)
            why = f"   <- {', '.join(w.replace('**', '') for w in why)}" if why else ""
            spend = " · ".join(x for x in (i.get("cost"), i.get("model")) if x)
            cost = f"  ({spend})" if spend else ""
            fx = f"  [{', '.join(i['findings'])}]"
            print(f"   {arrow} [{MARK.get(i['stage'], '?')}] {i['id']:<7} {i['stage']:<9} {i['title']}{cost}{fx}{why}")
        print()

    if open_d := [d for d in log["decisions"] if d["status"] == "OPEN"]:
        print("  Open decisions (human call):")
        for d in open_d:
            blocks = f" blocks {', '.join(d['blocking'])}" if d["blocking"] else " blocks nothing"
            print(f"    {d['id']}{blocks} -- {d['question']}")
        print()

    if watch:
        print("  Watch list (kept an eye on; `--watch` for detail):")
        for w in watch:
            ref = w.get("item") or w.get("decision") or ""
            flag = "!!" if w["kind"] == "ship-blocker" else "  "
            model = w.get("recommended_model", "?")
            print(f"    {flag} {w['id']:<4} {w['kind']:<15} {ref:<7} {model:<7} {w['title']}")
        print()

    last = log["history"][-1]
    session = last.get("session") or (f"landed {last['landed']}" if last.get("landed") else "")
    print(f"  Last session {last['date']} -- {session}")
    print(f"  Next: {last.get('next_action', '')}")
    print(f"  $ {last['next_command']}\n")


def main() -> int:
    log = json.loads(LOG.read_text())
    failures = check(log)
    if "--check" in sys.argv:
        for f in failures:
            print(f"FAIL  {f}")
        print("build-log.json OK" if not failures else f"{len(failures)} failure(s)")
        return 1 if failures else 0
    if "--order" in sys.argv:
        print(render_order(log))
        return 0
    if "--watch" in sys.argv:
        ev = WatchRules(log)
        rows = generate_watch_list(log)
        live = open_watch(log)
        for w in live:
            ref = ", ".join(x for x in (w.get("item"), w.get("decision")) if x) or "no item"
            model = w.get("recommended_model", "untagged")
            print(f"{w['id']}  [{w['kind']}]  {ref}  raised {w['raised']}  model {model}\n"
                  f"  {w['title']}\n"
                  f"  why:   {w['detail']}\n  clears when: {w['clears_when']}\n"
                  f"  trigger: {ev.describe(trig(w).get('clear'), w)}\n")
        auto = [w for w in rows if w.get("cleared_by") == "trigger"]
        if auto:
            print("Cleared by trigger -- no resolution was written; the log shows the condition met:")
            for w in auto:
                print(f"  {w['id']}  {w['title']}\n"
                      f"    trigger: {ev.describe(trig(w).get('clear'), w)}")
            print()
        by_hand = sum(1 for w in rows if w.get("cleared_by") == "hand")
        dormant = sum(1 for w in rows if w["status"] == "DORMANT")
        print(f"{len(live)} open · {by_hand} cleared by hand · {len(auto)} cleared by trigger"
              f" · {dormant} not yet raised  ({len(rows)} rules)")
        return 0
    if "--ship" in sys.argv:
        blockers = [w for w in open_watch(log) if w["kind"] == "ship-blocker"]
        for w in blockers:
            print(f"SHIP-BLOCKER {w['id']}  {w['title']}\n  clears when: {w['clears_when']}")
        print("no open ship-blockers" if not blockers else f"{len(blockers)} open ship-blocker(s)")
        return 1 if blockers else 0
    if "--write-order" in sys.argv:
        # Staleness is the failure this command repairs -- refusing on it would deadlock.
        # Any OTHER failure means the log is wrong, and generating a task list from a
        # wrong log would publish the error, so stop.
        blocking = [f for f in failures if f != STALE]
        if blocking:
            for f in blocking:
                print(f"FAIL  {f}")
            print("refusing to write from an invalid log")
            return 1
        print(write_order(log))
        return 0
    board(log)
    if failures:
        print("  ! validation failures -- run with --check\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
