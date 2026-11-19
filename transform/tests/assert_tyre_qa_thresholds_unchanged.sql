-- The stint-QA thresholds are pinned: boundary window 3 laps, race unexplained-boundaries
-- minimum 5, race unmatched-pit share minimum 0.3. Loosening any of them to make a race pass
-- (for example Miami 2025) must change this test on purpose. Returns a row if any differs.

SELECT
    'tyre_qa_thresholds' AS key,
    'boundary_window=' || CAST({{ var('tyre_qa_boundary_window_laps') }} AS VARCHAR)
        || ' unexplained_min=' || CAST({{ var('tyre_qa_race_unexplained_boundaries_min') }} AS VARCHAR)
        || ' unmatched_share_min=' || CAST({{ var('tyre_qa_race_unmatched_pit_share_min') }} AS VARCHAR)
        || ' (expected 3 / 5 / 0.3)' AS reason
FROM (SELECT 1) AS one
WHERE NOT (
    {{ var('tyre_qa_boundary_window_laps') }} = 3
    AND {{ var('tyre_qa_race_unexplained_boundaries_min') }} = 5
    AND {{ var('tyre_qa_race_unmatched_pit_share_min') }} = 0.3
)
