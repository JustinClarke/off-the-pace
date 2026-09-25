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
  * a `watch` list holds what is being kept an eye on but is not an item or a ruling:
    ship-blockers, uncommitted or unreviewed work, stale artifacts, standing hazards,
    unverified claims, gate gaps and known debt. Items and decisions say what to build and
    what to rule; the watch list is where an exception lives so it cannot fall off the
    board when the item that raised it lands. --check validates its shape only (an open
    ship-blocker is not a malformed log); --ship is the gate to run before publishing.
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


WATCH_FIELDS = ("id", "raised", "kind", "title", "detail", "clears_when", "status")


def open_watch(log: dict) -> list[dict]:
    """Open watch entries, most urgent kind first (vocabulary order), then in the order raised."""
    kinds = list(log.get("watch_vocabulary", {}))
    rank = {k: n for n, k in enumerate(kinds)}
    live = [w for w in log.get("watch", []) if w.get("status") == "OPEN"]
    return sorted(live, key=lambda w: (rank.get(w.get("kind"), 99), w.get("raised", ""),
                                       len(w.get("id", "")), w.get("id", "")))


def check_watch(log: dict, items: dict, decisions: dict) -> list[str]:
    """Shape of the watch list. An open entry is not a failure -- that is what it is for."""
    if "watch" not in log or "watch_vocabulary" not in log:
        return ["build-log.json has no `watch` list or `watch_vocabulary`"]
    kinds = set(log["watch_vocabulary"])
    bad: list[str] = []
    seen: set[str] = set()
    for w in log["watch"]:
        wid = w.get("id", "?")
        if wid in seen:
            bad.append(f"{wid}: duplicate watch id")
        seen.add(wid)
        for f in WATCH_FIELDS:
            if not w.get(f):
                bad.append(f"{wid}: watch entry has no {f!r}")
        if w.get("kind") and w["kind"] not in kinds:
            bad.append(f"{wid}: kind {w['kind']!r} not in watch_vocabulary")
        if w.get("status") not in ("OPEN", "RESOLVED"):
            bad.append(f"{wid}: status {w.get('status')!r} is not OPEN or RESOLVED")
        if w.get("status") == "RESOLVED" and not (w.get("resolved") and w.get("resolution")):
            bad.append(f"{wid}: RESOLVED without a date and a resolution")
        if w.get("item") and w["item"] not in items:
            bad.append(f"{wid}: names item {w['item']}, which does not exist")
        if w.get("decision") and w["decision"] not in decisions:
            bad.append(f"{wid}: names decision {w['decision']}, which does not exist")
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
        out.append(f"**{len(watch)} open** ({ships} ship-blocker{'s' if ships != 1 else ''}). "
                   f"Full detail: `{CMD} --watch`. `{CMD} --ship` exits 1 while a "
                   f"ship-blocker is open.")
        out.append("")
        out.append("| ID | Kind | Item | What | Clears when |")
        out.append("| :--- | :--- | :--- | :--- | :--- |")

        def cell(s: str) -> str:
            return s.replace("|", "/").replace("\n", " ")
        for w in watch:
            ref = ", ".join(x for x in (w.get("item"), w.get("decision")) if x) or "—"
            out.append(f"| {w['id']} | {w['kind']} | {ref} | {cell(w['title'])} "
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
    return f"wrote {len(plan(log))} live items into {ORDER_DOC.name}"


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
            print(f"    {flag} {w['id']:<4} {w['kind']:<15} {ref:<7} {w['title']}")
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
        for w in open_watch(log):
            ref = ", ".join(x for x in (w.get("item"), w.get("decision")) if x) or "no item"
            print(f"{w['id']}  [{w['kind']}]  {ref}  raised {w['raised']}\n  {w['title']}\n"
                  f"  why:   {w['detail']}\n  clears when: {w['clears_when']}\n")
        print(f"{len(open_watch(log))} open")
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
