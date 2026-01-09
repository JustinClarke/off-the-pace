-- Pirelli weekend tyre allocations: which compound codes map to
-- hard/medium/soft labels for a given race weekend.
-- SOURCE NOT YET INGESTED requires scraping or manual seed from
-- Pirelli allocation sheets. Expected columns per race_year × circuit_key:
--   compound_code (C1–C5), compound_label (hard/medium/soft),
--   allocated_sets_per_driver.
--
-- Until available, derive compound labels from the compound string in stg_laps.
-- FastF1 already returns HARD/MEDIUM/SOFT/INTERMEDIATE/WET directly in
-- the Compound column, so this model is low-priority for current seasons.
{{ config(materialized='view') }}

SELECT
    CAST(NULL AS INTEGER) AS race_year,
    CAST(NULL AS VARCHAR) AS circuit_key,
    CAST(NULL AS VARCHAR) AS compound_code,
    CAST(NULL AS VARCHAR) AS compound_label,
    CAST(NULL AS INTEGER) AS allocated_sets_per_driver
WHERE 1 = 0
