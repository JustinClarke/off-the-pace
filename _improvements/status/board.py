#!/usr/bin/env python3
"""Render and validate the build log.

    python3 _improvements/status/board.py                # the board
    python3 _improvements/status/board.py --check        # invariants only; exit 1 on failure
    python3 _improvements/status/board.py --order        # the ordered task list, to stdout
    python3 _improvements/status/board.py --write-order  # ...and into BUILD-ORDER.md

build-log.json is the authoritative state. This script never writes to it -- it is a
reader, so a malformed edit surfaces as a failed check rather than as silent drift.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

LOG = Path(__file__).parent / "build-log.json"
ORDER_DOC = Path(__file__).parent / "BUILD-ORDER.md"
BEGIN = "<!-- BEGIN GENERATED TASKS -- do not hand-edit; `board.py --write-order` -->"
END = "<!-- END GENERATED TASKS -->"
STALE = ("BUILD-ORDER.md's generated task list is stale -- "
         "run `board.py --write-order`")
TERMINAL = {"CLOSED", "LANDED"}
MARK = {"SPEC": "·", "PROBED": "?", "BUILDING": "~", "MEASURED": "=",
        "GATED": "+", "LANDED": "x", "BLOCKED": "!", "CLOSED": "x"}


def check(log: dict) -> list[str]:
    """Every invariant the checklist rules assert, as a list of failures."""
    items = {i["id"]: i for i in log["items"]}
    decisions = {d["id"] for d in log["decisions"]}
    groups = {g["id"] for g in log["groups"]}
    stages = set(log["stage_vocabulary"])
    models = set(log["model_vocabulary"])
    bad: list[str] = []

    ptr = log.get("pointer")
    if ptr not in items:
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
        if (d := i.get("blocked_by_decision")) and d not in decisions:
            bad.append(f"{iid}: blocked by {d}, which is not a recorded decision")
        if i["stage"] == "BLOCKED":
            unmet = [d for d in i["depends_on"]
                     if d in items and items[d]["stage"] not in TERMINAL | {"GATED"}]
            if not unmet and not i.get("blocked_by_decision"):
                bad.append(f"{iid}: BLOCKED with no unmet dependency and no open decision")
        if i["stage"] == "CLOSED" and not i.get("closed"):
            bad.append(f"{iid}: CLOSED without a date")
        if i["stage"] not in TERMINAL and not i.get("cost"):
            bad.append(f"{iid}: live item with no cost estimate")
        if i["stage"] not in TERMINAL:
            if not i.get("model"):
                bad.append(f"{iid}: live item with no model")
            elif i["model"] not in models:
                bad.append(f"{iid}: model {i['model']!r} not in the vocabulary")

    if ORDER_DOC.exists():
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
    """Live items in runnable order: dependencies first, then group order, then id.

    A topological sort, so the list can be read top-down as "do this, then this".
    Ties break on `order_hint` first, then the order groups are declared in the log.
    Group order is the programme's sequencing argument (rigour before publication);
    `order_hint` is the escape hatch for a cheap probe whose RESULT reorders the work
    behind it, so it earns its place at the front regardless of its group. Use it
    sparingly -- an order_hint on everything is just a second group order.

    `parallel` is recorded and displayed but does not sink a group; dependencies
    always win over both.
    """
    items = {i["id"]: i for i in log["items"]}
    gorder = {g["id"]: n for n, g in enumerate(log["groups"])}
    live = [i for i in log["items"] if i["stage"] not in TERMINAL]

    def key(i: dict) -> tuple:
        return (i.get("order_hint", 99), gorder[i["group"]], i["id"])

    ordered: list[dict] = []
    placed: set[str] = {i["id"] for i in log["items"] if i["stage"] in TERMINAL | {"GATED"}}
    pool = sorted(live, key=key)
    while pool:
        ready = [i for i in pool if all(d in placed for d in i["depends_on"])]
        if not ready:          # dependency cycle: emit the rest rather than hang
            ordered.extend(pool)
            break
        nxt = ready[0]
        ordered.append(nxt)
        placed.add(nxt["id"])
        pool.remove(nxt)
    return ordered


def render_order(log: dict) -> str:
    """The generated task list. Derived from the log; never hand-edited."""
    items = {i["id"]: i for i in log["items"]}
    groups = {g["id"]: g for g in log["groups"]}
    ptr = log.get("pointer")
    seq = plan(log)

    out: list[str] = [BEGIN, ""]
    out.append(f"_Generated from [`build-log.json`](build-log.json) at `updated: {log['updated']}`."
               f" Run `python3 _improvements/status/board.py --write-order` after any edit to the log._")
    out.append("")
    done = [i for i in log["items"] if i["stage"] in TERMINAL]
    blocked = sum(1 for i in seq if i["stage"] == "BLOCKED")
    out.append(f"**{len(seq)} live items** ({blocked} blocked). "
               f"The pointer is on **{ptr}** — that is the one to run next; the rest of the "
               f"order is what becomes runnable after it. "
               f"{len(done)} terminal items are finished and not listed here — "
               f"run `board.py` for the per-group view, or read their `closed` field in "
               f"[`build-log.json`](build-log.json) for why each one ended as it did.")
    out.append("")
    out.append("| # | Item | Group | Stage | Cost | Model | Task | Waiting on |")
    out.append("| ---: | :--- | :--- | :--- | :--- | :--- | :--- | :--- |")
    for n, i in enumerate(seq, 1):
        blockers = [d for d in i["depends_on"]
                    if items[d]["stage"] not in TERMINAL | {"GATED"}]
        if dec := i.get("blocked_by_decision"):
            blockers.append(f"**{dec}** (human call)")
        wait = ", ".join(blockers) if blockers else "—"
        mark = " ▶" if i["id"] == ptr else ""
        g = groups[i["group"]]
        gcell = f"[{g['id']}]({'../' + g['doc']})"
        out.append(f"| {n} | `{i['id']}`{mark} | {gcell} | {i['stage']} | {i.get('cost','—')} "
                   f"| `{i.get('model','—')}` | {i['title']} | {wait} |")
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
            out.append(f"- **{d['id']}** (blocks {blocks}) — {d['question']}")
        out.append("")

    # Terminal items are deliberately NOT listed here. This file answers "what do I
    # run next"; a finished item is not an answer to that. Their reasons live in
    # build-log.json's `closed` field, which is the authoritative copy, and
    # `board.py` (no args) shows them per group as `[x]` rows for progress.
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
    ptr = log.get("pointer")
    print(f"\n  {log['project']}    updated {log['updated']}    next: {ptr}\n")

    for g in log["groups"]:
        mine = [i for i in log["items"] if i["group"] == g["id"]]
        live = [i for i in mine if i["stage"] not in TERMINAL]
        tag = "  (parallel)" if g.get("parallel") else ""
        done = len(mine) - len(live)
        print(f"  {g['id']} {g['title']}{tag}   [{done}/{len(mine)} terminal]   {g['doc']}")
        for i in mine:
            arrow = "▶" if i["id"] == ptr else " "
            blockers = [d for d in i["depends_on"]
                        if items[d]["stage"] not in TERMINAL | {"GATED"}]
            if dec := i.get("blocked_by_decision"):
                blockers.append(dec)
            why = f"   <- {', '.join(blockers)}" if blockers else ""
            spend = " · ".join(x for x in (i.get("cost"), i.get("model")) if x)
            cost = f"  ({spend})" if spend else ""
            print(f"   {arrow} [{MARK[i['stage']]}] {i['id']:<4} {i['stage']:<9} {i['title']}{cost}{why}")
        print()

    if open_d := [d for d in log["decisions"] if d["status"] == "OPEN"]:
        print("  Open decisions (human call):")
        for d in open_d:
            blocks = f" blocks {', '.join(d['blocking'])}" if d["blocking"] else " blocks nothing"
            print(f"    {d['id']}{blocks} -- {d['question']}")
        print()

    last = log["history"][-1]
    print(f"  Last session {last['date']} -- {last['session']}")
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
    if "--write-order" in sys.argv:
        # Staleness is the failure this command repairs -- refusing on it would
        # deadlock. Any OTHER failure means the log is wrong, and generating a
        # task list from a wrong log would publish the error, so stop.
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
