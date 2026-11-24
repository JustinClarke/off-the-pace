{{ config(tags=['intermediate'], severity='error') }}
-- Task 2A. A lap with no compound parameter cell has an UNKNOWN compound cost:
-- compound_cliff_wear_s must return NULL, never 0.
--
-- The macro used to COALESCE the gradient and severity to 0.0, so a lap whose
-- (circuit, compound, season) had no dim_compounds_season cell was priced as
-- "never wears, never cliffs" and entered int_field_pace_curve as a free 0 s tyre.
--
-- Self-contained: this evaluates the macro itself over synthetic rows, so it
-- bites even when the warehouse has no cell-less lap with a known tyre age. It
-- fails on (1) a missing cell priced as a number, (2) a FITTED cell whose value
-- moved from the pre-fix expression (the old expression is reproduced below;
-- for non-NULL inputs the fix must be a no-op), (3) a class_default / fallback
-- cell that stopped pricing. Cell provenance is not the macro's concern: a
-- default cell has numeric parameters and prices like any other.
WITH cells AS (
    SELECT * FROM (VALUES
        -- case,               gradient, severity, age,  laps_past_cliff
        ('missing_cell',        CAST(NULL AS DOUBLE), CAST(NULL AS DOUBLE), 12.0, 0.0),
        ('missing_cell_past',   CAST(NULL AS DOUBLE), CAST(NULL AS DOUBLE), 30.0, 4.0),
        ('fitted_pre_onset',    0.10, 1.20, 10.0, 0.0),
        ('fitted_in_ramp',      0.10, 1.20, 21.0, 1.0),
        ('fitted_held',         0.10, 1.20, 40.0, 15.0),
        ('fitted_capped',       5.00, 9.00, 40.0, 15.0),
        ('class_default_cell',  0.05, 0.50, 18.0, 0.0)
    ) AS t (case_name, wear_gradient, severity, age, laps_past_cliff)
),

priced AS (
    SELECT
        case_name,
        wear_gradient,
        {{ compound_cliff_wear_s('wear_gradient', 'severity', 'age', 'laps_past_cliff') }}
            AS new_wear_s,
        -- the expression as it stood before Task 2A (COALESCE of the gradient)
        CASE
            WHEN age IS NULL OR laps_past_cliff IS NULL THEN NULL
            ELSE LEAST(
                COALESCE(wear_gradient, 0.0)
                * (age - GREATEST(
                    laps_past_cliff - {{ var('compound_wear_hold_after_onset_laps') }},
                    0.0))
                + {{ cliff_severity_term('severity', 'wear_gradient', 'laps_past_cliff') }},
                {{ var('compound_wear_max_s_per_lap', 10.0) }}
            )
        END AS old_wear_s
    FROM cells
)

SELECT
    case_name,
    new_wear_s,
    old_wear_s
FROM priced
WHERE
    -- missing cell: must be NULL
    (wear_gradient IS NULL AND new_wear_s IS NOT NULL)
    -- every cell that exists: priced, and identical to the pre-fix value
    OR (
        wear_gradient IS NOT NULL
        AND (new_wear_s IS NULL OR ABS(new_wear_s - old_wear_s) > 1e-12)
    )
