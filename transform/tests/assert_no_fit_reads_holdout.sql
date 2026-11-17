-- TX-29 / HD17: no seed parameter is fitted on data from the holdout season
-- (var holdout_season, 2025) or later. compound_cliff_params is point-in-time:
-- a season-S row is fitted on seasons before S (data_window '2018_to_<S-1>'),
-- so the 2025 rows read 2018-2024 and pass; a row whose window ends in 2025 or
-- 2026 fails. Returns the offending rows.
SELECT
    circuit_key,
    compound_code,
    season,
    data_window
FROM {{ ref('compound_cliff_params') }}
WHERE
    CAST(REGEXP_EXTRACT(data_window, '^\d{4}_to_(\d{4})', 1) AS INTEGER)
    >= {{ var('holdout_season') }}
    OR REGEXP_EXTRACT(data_window, '^\d{4}_to_(\d{4})', 1) = ''
