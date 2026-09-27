# WI-15a Acceptance Evidence — 2026-09-25

Built by claude-opus-5 agent during WI-15a MEASURED session.

## Files

- **`dev_fixed.duckdb`** — Warehouse with F43 and F48 fixes applied
- **`dev_unfixed.duckdb`** — Baseline warehouse (unfixed, matches live dev on every mart column within 1e-9)

## What they prove

Both acceptance criteria for WI-15a pass on a full rebuild:

### F43 (pit-lane cars not traffic)
- **Fixed column:** `int_lap_proximity.gap_ahead_min_s`
- **Movement:** 6,288 of 137,759 eligible rows move (median 0.90 s → 3.32 s; 2,896 cross 1 s line)
- **Label impact:** None
- **Comparison:** Result matches audit reference rebuild exactly on 13/14 columns; 14th differs by design (dwell time measured before pit filter)

### F48 (dirty air monotone on gap)
- **Fixed columns:** `int_lap_air_state.dirty_air_share_lap`, `s2_drs_active`, `s2_gap_median_s`
- **Movement:** 11,540 eligible rows move `dirty_air_share_lap` (0→1); none move 1→0
- **Label impact:** Reaches label through θ_air only (0.160673 → 0.264795)
- **Affected rows:** 78,583 rows move `next_5_lap_cumulative_jump_s` (mean 0.23 s), 2,638 move `laps_until_cliff_class`, 348 flip eligibility
- **Field pace:** Unchanged

## How to verify

Compare the two databases on key tables:
```sql
-- F43: gap_ahead_min_s movement
SELECT COUNT(*) as movedRows
FROM fixed.int_lap_proximity AS f
FULL OUTER JOIN unfixed.int_lap_proximity AS u ON f.lap_id = u.lap_id
WHERE f.gap_ahead_min_s != u.gap_ahead_min_s;

-- F48: dirty_air_share_lap movement
SELECT COUNT(*) as movedRows
FROM fixed.int_lap_air_state AS f
FULL OUTER JOIN unfixed.int_lap_air_state AS u ON f.lap_id = u.lap_id
WHERE f.dirty_air_share_lap != u.dirty_air_share_lap;
```

## Build details

- Both built from the same code base (2026-09-25 working tree)
- Fixed copy: F43 and F48 SQL changes applied
- Unfixed copy: Original code, validates as matching live dev
- Downstream marts rebuilt from both sources
- Tests: T33 (assert_proximity_excludes_pit_lane) and T38 (assert_dirty_air_share_monotone) pass on fixed, fail on unfixed

## Notes

- Tests T33/T38 error on `data/dev.duckdb` until rebuilt (require the new columns)
- Every season moves (corrected 2026-09-25 by the orchestrator re-run; an earlier note here said only 2025 moved, which was wrong). On HEAD-eligible rows, per season 2018-2025: `gap_ahead_min_s` 613 / 873 / 644 / 838 / 645 / 839 / 962 / 874 (6,288 in all); `dirty_air_share_lap` 677 / 964 / 1,057 / 1,370 / 1,524 / 2,234 / 1,691 / 2,023 (11,540); `next_5_lap_cumulative_jump_s` 78,583 in all. Eligibility: 348 lost and 466 gained (137,759 → 137,877)
- "Fail on unfixed": T33/T38 *error* on this copy (their columns do not exist at HEAD). The mutation checks (the defect put back into the fixed SQL) are what make them fail: T33 13,384 rows, T38 all ten sub-1 s bins
- Not covered: 139 lap-1 laps whose closest car ahead is a pit-lane race starter (not training-eligible, known debt)
- `dev_unfixed.duckdb` is HEAD for every model, the thermal subtree included. WI-15b's landing used it as its HEAD too
