-- dim_compounds_season.sql · reference · grain: one row per circuit × compound
-- × season
-- Lifts the compound_cliff_params seed into a typed dimension: fitted
-- Kaplan-Meier
-- cliff onset (p25/p50/p75 laps), wear gradient, and grip-peak parameters.
--
-- Provenance is per parameter. fit_source is the tier the cell's fit was
-- attempted at; onset_source / gradient_source / severity_source say where
-- each number came from (fitted, cross_season_fallback,
-- pooled_compound_fallback, class_default, carried_forward), because a tier that
-- ran can still leave one parameter on the compound-class default.
-- 'fitted' = estimated from this event's own history window (earlier seasons of
-- the same event slug; 2018 its own season). The fallbacks and carried_forward
-- are borrowed numbers, not this event's own fit.
-- is_measured is TRUE only when all three parameters are 'fitted'.
-- provenance_class names the cell: own_history_fitted (all three fitted), the
-- shared source when all three agree (cross_season_fallback,
-- pooled_compound_fallback, class_default, carried_forward), else mixed.
-- compound_grip_peak and the optimal-temperature window are never fitted: they
-- are compound-class constants in every row. A (venue, season, compound) with no
-- row here is 'missing' downstream (see fct_cliff_prediction_features).
{{ config(materialized='table') }}

SELECT
    CAST(circuit_key AS VARCHAR) AS circuit_key,
    CAST(compound_code AS VARCHAR) AS compound_code,
    CAST(season AS INTEGER) AS season,
    CAST(compound_grip_peak AS DOUBLE) AS compound_grip_peak,
    CAST(compound_wear_gradient AS DOUBLE) AS compound_wear_gradient,
    CAST(compound_optimal_temp_low AS DOUBLE) AS compound_optimal_temp_low,
    CAST(compound_optimal_temp_high AS DOUBLE) AS compound_optimal_temp_high,
    CAST(compound_cliff_onset_laps AS DOUBLE) AS compound_cliff_onset_laps,
    CAST(compound_cliff_severity AS DOUBLE) AS compound_cliff_severity,
    CAST(fit_date AS DATE) AS fit_date,
    CAST(data_window AS VARCHAR) AS data_window,
    CAST(fit_source AS VARCHAR) AS fit_source,
    CAST(onset_source AS VARCHAR) AS onset_source,
    CAST(gradient_source AS VARCHAR) AS gradient_source,
    CAST(severity_source AS VARCHAR) AS severity_source,
    CAST(notes AS VARCHAR) AS notes,
    -- TRUE only when every parameter is an own-history fit. Pooled, cross-season,
    -- carried-forward and class-default parameters are not measured for this cell.
    -- NULL source (not expected; not_null tested) yields FALSE, never TRUE.
    {{ compound_is_measured('onset_source', 'gradient_source', 'severity_source') }} AS is_measured,
    {{ compound_provenance_class('onset_source', 'gradient_source', 'severity_source') }} AS provenance_class
FROM {{ ref('compound_cliff_params') }}
