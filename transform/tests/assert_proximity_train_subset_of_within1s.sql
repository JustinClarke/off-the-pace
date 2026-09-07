-- share_lap_in_train is a strictly stronger condition than share_lap_within_1s
-- and can never exceed it.
--
-- A "train" bin requires gap_ahead_s < 1 AND the car ahead's own gap < 1. The
-- first conjunct is exactly the condition share_lap_within_1s counts, so the
-- train share is a subset share by construction. This test exists because the
-- two are computed as independent AVG(CASE...) expressions over the same
-- rows: nothing in the SQL structurally prevents them drifting apart if the
-- ahead_own_gap_s definition, the self-match guard, or the neutralised-lap
-- zeroing is changed on one and not the other. That is the same shape of
-- defect Phase 8 found in the cliff bound (two applications of one rule, only
-- one of them maintained).
--
-- Exact, not toleranced: both are averages of 0/1 over the identical bin set,
-- so any violation is a logic error, not float drift.
SELECT
    lap_id,
    share_lap_within_1s,
    share_lap_in_train
FROM {{ ref('int_lap_proximity') }}
WHERE share_lap_in_train > share_lap_within_1s
