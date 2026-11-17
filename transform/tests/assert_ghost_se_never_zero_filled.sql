-- TX-18: no SE in the ghost marts is 0 where its estimate is missing. A NULL
-- finish_pos_se has a reason; a present one has none; an SE ingredient is NULL
-- (not 0) exactly when its cell is flagged as having no estimate. Returns
-- offending rows.
SELECT 'finish_pos_se_null_without_reason' AS failure, ghost_race_id AS row_id
FROM {{ ref('fct_ghost_race_finish') }}
WHERE finish_pos_se IS NULL AND finish_pos_se_unavailable_reason IS NULL

UNION ALL

SELECT 'finish_pos_se_present_with_reason', ghost_race_id
FROM {{ ref('fct_ghost_race_finish') }}
WHERE finish_pos_se IS NOT NULL AND finish_pos_se_unavailable_reason IS NOT NULL

UNION ALL

SELECT 'host_deg_sd_filled_for_prior_cell', ghost_id
FROM {{ ref('fct_ghost_car_pace') }}
WHERE host_deg_slope_is_prior AND host_deg_slope_sd_s_per_lap IS NOT NULL

UNION ALL

SELECT 'ego_deg_sd_filled_for_prior_cell', ghost_id
FROM {{ ref('fct_ghost_car_pace') }}
WHERE ego_deg_slope_is_prior AND ego_deg_slope_sd_s_per_lap IS NOT NULL

UNION ALL

SELECT 'host_pace_se_filled_for_prior_cell', ghost_id
FROM {{ ref('fct_ghost_car_pace') }}
WHERE host_constructor_pace_is_prior AND host_constructor_pace_se_s IS NOT NULL
