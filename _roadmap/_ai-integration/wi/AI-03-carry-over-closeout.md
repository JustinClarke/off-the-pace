# AI-03 — Carry-over gate: numbers settled before launch

**Group:** D carry-over · **Depends on:** `CO-01`, `CO-02`, `CO-03`, `CO-04`, `CO-06` · **Blocker:** none of its own.

**Sources:** `_roadmap/_fixes/status/build-log.json`, `scripts/export_app_data.py`.

This item used to restate six fixes-board problems itself. Each now has one owner, and this item is the gate on them:

| Was | Now owned by |
| :-- | :-- |
| W4 ingestion review, one red test | CO-05 (not a gate: it moves no number the assistant quotes) |
| WI-02b F9 not wired | CO-03, ruling `CD1` |
| FD6 not built | CO-04 |
| W43 smoother across safety cars | CO-04 |
| W44 thin cells | CO-04 |
| v15 gates not run on the final label | CO-03 |

AI-08 (launch) waits on this item, so nothing ships quoting numbers that are about to move. AI-07's eval can be built and run before it, because the grader reads expected values from the card table at run time.

---

## Method

1. Confirm that the warehouse and the app data export are rebuilt from the tree with CO-01 to CO-04 and CO-06 in.
2. Correct the fixes-log entries the 2026-10-15 audit found contradicted by the tree (W43, W44, W59, WI-02b's F9 note, FD6/WI-09b), each with a link to the CO item that did the work. Append a history entry; do not delete the old text.
3. Freeze the card sources: record row counts and a checksum per card source table. AI-08's launch run uses this snapshot.

## Definition of done

Rebuild confirmed, fixes-log entries corrected, snapshot recorded, and `board.py --check` passes on all three boards.
