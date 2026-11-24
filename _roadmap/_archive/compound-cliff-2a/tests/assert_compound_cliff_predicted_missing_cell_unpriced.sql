{{ config(tags=['intermediate'], severity='error') }}
-- Task 2A, model half. In int_compound_cliff_predicted a valid lap with a known
-- compound and tyre age but NO dim_compounds_season cell must carry a NULL
-- compound cost (compound_wear_s and expected_compound_pace_s), and a lap WITH a
-- cell -- fitted or class_default / fallback -- must carry a numeric one.
--
-- Cell presence is read from dim_compounds_season itself (re-joined here on
-- track/compound/season) and its existing provenance column is_measured, so no
-- new status column is needed: is_measured TRUE = fitted/data-sourced cell,
-- FALSE = class_default cell, no row = missing cell. The three states stay
-- distinguishable and only the last is unpriced.
WITH laps AS (
    SELECT
        p.lap_id,
        p.race_year,
        p.compound,
        p.age_in_stint,
        p.compound_wear_s,
        p.expected_compound_pace_s,
        rt.track_id
    FROM {{ ref('int_compound_cliff_predicted') }} AS p
    INNER JOIN {{ ref('race_to_track') }} AS rt ON p.race_id = rt.race_id
    WHERE p.compound IS NOT NULL AND p.age_in_stint IS NOT NULL
)

SELECT
    l.lap_id,
    l.track_id,
    l.compound,
    l.race_year,
    d.is_measured,
    l.compound_wear_s,
    l.expected_compound_pace_s
FROM laps AS l
LEFT JOIN {{ ref('dim_compounds_season') }} AS d
    ON
        l.track_id = d.circuit_key
        AND l.race_year = d.season
        AND l.compound = d.compound_code
WHERE
    -- missing cell priced as a number
    (d.circuit_key IS NULL
        AND (l.compound_wear_s IS NOT NULL OR l.expected_compound_pace_s IS NOT NULL))
    -- existing cell (measured or default) left unpriced
    OR (d.circuit_key IS NOT NULL
        AND (l.compound_wear_s IS NULL OR l.expected_compound_pace_s IS NULL))
