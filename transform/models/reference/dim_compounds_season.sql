-- dim_compounds_season.sql · reference · grain: one row per circuit × compound × season
-- Lifts the compound_cliff_params seed into a typed dimension: fitted Kaplan-Meier
-- cliff onset (p25/p50/p75 laps), wear gradient, and grip-peak parameters.
{{ config(materialized='table') }}

SELECT
    CAST(circuit_key              AS VARCHAR) AS circuit_key,
    CAST(compound_code            AS VARCHAR) AS compound_code,
    CAST(season                   AS INTEGER) AS season,
    CAST(compound_grip_peak       AS DOUBLE)  AS compound_grip_peak,
    CAST(compound_wear_gradient   AS DOUBLE)  AS compound_wear_gradient,
    CAST(compound_optimal_temp_low  AS DOUBLE) AS compound_optimal_temp_low,
    CAST(compound_optimal_temp_high AS DOUBLE) AS compound_optimal_temp_high,
    CAST(compound_cliff_onset_laps  AS DOUBLE) AS compound_cliff_onset_laps,
    CAST(compound_cliff_severity    AS DOUBLE) AS compound_cliff_severity,
    CAST(fit_date                 AS DATE)    AS fit_date,
    CAST(data_window              AS VARCHAR) AS data_window,
    CAST(notes                    AS VARCHAR) AS notes
FROM {{ ref('compound_cliff_params') }}
