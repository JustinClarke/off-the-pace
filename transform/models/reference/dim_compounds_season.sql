-- dim_compounds_season.sql · reference · grain: one row per circuit × compound
-- × season
-- Lifts the compound_cliff_params seed into a typed dimension: fitted
-- Kaplan-Meier
-- cliff onset (p25/p50/p75 laps), wear gradient, and grip-peak parameters.
--
-- Provenance is per parameter. fit_source is the tier the cell's fit was
-- attempted at; onset_source / gradient_source / severity_source say where
-- each number came from (fitted, cross_season_fallback, class_default,
-- carried_forward), because a tier that ran can still leave one parameter on
-- the compound-class default. compound_grip_peak and the optimal-temperature
-- window are never fitted: they are compound-class constants in every row.
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
    CAST(notes AS VARCHAR) AS notes
FROM {{ ref('compound_cliff_params') }}
