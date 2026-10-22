# AI-03 — Data freeze: numbers settled before launch

**Group:** 1 data settled · **Depends on:** `CO-01`, `CO-02`, `CO-04`, `CO-06`, `CO-14`, `CO-17`, `CO-18`, `CO-19` · **Blocker:** `CD10` (which model version serves at launch). The snapshot is taken once, after that ruling, and must not move afterwards (watch W2).

**Ruled 2026-10-22 (`CD13`):** the freeze waits for the promotion ruling (`CD10`), the stint-life clean test (`CO-14`) and the retrain (`CO-18`). There is no launch on v14 ahead of that ruling. The mixed-version probe (`CO-19`) also gates the freeze, because `CD10`'s option A may serve stint life on v14 beside four new models.

**Sources:** `_roadmap/_fixes/status/build-log.json`, `scripts/export_app_data.py`.

This item used to restate six fixes-board problems itself. Each now has one owner, and this item is the gate on them:

| Was | Now owned by |
| :-- | :-- |
| W4 ingestion review, one red test | CO-05 (not a gate: it moves no number the assistant quotes) |
| WI-02b F9 not wired | ruled `CD1`; the clean-up rides CO-17 |
| FD6 not built | CO-04 |
| W43 smoother across safety cars | CO-04 |
| W44 thin cells | CO-04 |
| v15 gates not run on the final label | CO-18 (CO-03 closed as superseded 2026-10-22) |

AI-12 (launch run and switch-on) waits on this item, so nothing ships quoting numbers that are about to move. AI-07's eval can be built and run before it, because the grader reads expected values from the card table at run time.

---

## Method

1. Confirm that the warehouse is CO-17's trusted build (CO-01, CO-02, CO-04, CO-06, CO-09, CO-15, CO-16 in) and that the app data export is rebuilt from it. Record the model version `CD10` chose.
2. Correct the fixes-log entries the 2026-10-15 audit found contradicted by the tree (W43, W44, W59, WI-02b's F9 note, FD6/WI-09b), each with a link to the CO item that did the work. Append a history entry; do not delete the old text.
3. Freeze the card sources: record row counts and a checksum per card source table, and the served model version. AI-12's launch run uses this snapshot.

## Definition of done

Rebuild confirmed, fixes-log entries corrected, snapshot recorded, and `board.py --check` passes on all three boards.
