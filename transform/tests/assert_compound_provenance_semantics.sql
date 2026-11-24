-- Compound parameter provenance: is_measured is TRUE only for an own-history fit.
-- Passes when it returns zero rows.
--
-- Part 1 runs the shared macros over fixture cells (no warehouse needed): an own-history
-- cell, pooled, cross-season, class default, carried forward, mixed (fitted onset +
-- default gradient), and a missing cell (no dim row: the mart's LEFT JOIN yields NULL
-- sources, which must never read as measured).
-- Part 2 re-derives the flag independently on the real dim and the mart.

WITH fixture AS (
    SELECT * FROM (VALUES
        ('own_history', 'fitted', 'fitted', 'fitted', 'own_history_fitted'),
        ('pooled', 'pooled_compound_fallback', 'pooled_compound_fallback', 'pooled_compound_fallback', 'pooled_compound_fallback'),
        ('cross_season', 'cross_season_fallback', 'cross_season_fallback', 'cross_season_fallback', 'cross_season_fallback'),
        ('class_default', 'class_default', 'class_default', 'class_default', 'class_default'),
        ('carried_forward', 'carried_forward', 'carried_forward', 'carried_forward', 'carried_forward'),
        ('mixed_fitted_onset_default_gradient', 'fitted', 'class_default', 'fitted', 'mixed'),
        ('mixed_cross_season_default_onset', 'class_default', 'cross_season_fallback', 'cross_season_fallback', 'mixed'),
        ('missing_cell', CAST(NULL AS VARCHAR), CAST(NULL AS VARCHAR), CAST(NULL AS VARCHAR), 'missing')
    ) AS t(case_name, onset_source, gradient_source, severity_source, expected_class)
),

expected AS (
    SELECT
        case_name,
        onset_source,
        gradient_source,
        severity_source,
        expected_class,
        case_name = 'own_history' AS expected_measured
    FROM fixture
),

fixture_failures AS (
    SELECT
        'fixture:' || case_name AS failure,
        {{ compound_is_measured('onset_source', 'gradient_source', 'severity_source') }} AS got_measured,
        {{ compound_provenance_class('onset_source', 'gradient_source', 'severity_source') }} AS got_class
    FROM expected
    WHERE {{ compound_is_measured('onset_source', 'gradient_source', 'severity_source') }} <> expected_measured
       OR (
            case_name <> 'missing_cell'
            AND {{ compound_provenance_class('onset_source', 'gradient_source', 'severity_source') }} <> expected_class
       )
       -- distinct per-parameter sources in a mixed cell must stay distinct (not collapsed)
       OR (case_name LIKE 'mixed%' AND onset_source = gradient_source AND gradient_source = severity_source)
),

dim_failures AS (
    SELECT
        'dim:' || circuit_key || '/' || compound_code || '/' || CAST(season AS VARCHAR) AS failure,
        is_measured AS got_measured,
        provenance_class AS got_class
    FROM {{ ref('dim_compounds_season') }}
    WHERE is_measured IS DISTINCT FROM (
            onset_source = 'fitted' AND gradient_source = 'fitted' AND severity_source = 'fitted')
       OR (is_measured AND provenance_class <> 'own_history_fitted')
       OR (NOT is_measured AND provenance_class = 'own_history_fitted')
       OR (provenance_class IN ('cross_season_fallback', 'pooled_compound_fallback', 'class_default', 'carried_forward')
           AND is_measured)
),

-- The mart carries the dim's classification and calls an unmatched lap 'missing', never measured.
mart_failures AS (
    SELECT
        'mart:' || m.compound_params_provenance_class AS failure,
        m.compound_params_is_measured AS got_measured,
        m.compound_params_provenance_class AS got_class
    FROM {{ ref('fct_cliff_prediction_features') }} AS m
    LEFT JOIN {{ ref('race_to_track') }} AS rt ON m.race_id = rt.race_id
    LEFT JOIN {{ ref('dim_compounds_season') }} AS d
        ON rt.track_id = d.circuit_key AND m.compound = d.compound_code AND m.race_year = d.season
    WHERE m.compound_params_is_measured IS DISTINCT FROM COALESCE(d.is_measured, FALSE)
       OR m.compound_params_provenance_class IS DISTINCT FROM COALESCE(d.provenance_class, 'missing')
       OR (d.circuit_key IS NULL AND m.compound_params_is_measured)
    LIMIT 20
)

SELECT * FROM fixture_failures
UNION ALL SELECT * FROM dim_failures
UNION ALL SELECT * FROM mart_failures
