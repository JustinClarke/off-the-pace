-- int_lap_physical_ahead: lapped share of known samples above 30% in a race. Guards the 2018-2019 placeholder
-- defect: every car's first ~30 pos samples are X = Y = 0, and anchoring the unwrapped progress on one of them put
-- about half the cars exactly one lap off (Singapore 2018 / 2019, Monaco 2018 / 2019: 25-42% lapped; healthy
-- races 2.7-24%). Fixed 2026-11-21 in physical_ahead_core (P is unwrapped over real samples only), after which
-- those races read 2.7-11%. A warning now means a NEW cause, or a race that really is that lapped: check the
-- per-driver P offset (median P / L - (lap - 1) should be the same for every car) before dismissing it.
{{ config(severity='warn') }}
SELECT
    race_id,
    SUM(n_lapped_samples)::DOUBLE / NULLIF(SUM(n_samples - n_unknown_samples), 0) AS lapped_share
FROM {{ ref('int_lap_physical_ahead') }}
GROUP BY race_id
HAVING SUM(n_lapped_samples)::DOUBLE / NULLIF(SUM(n_samples - n_unknown_samples), 0) > 0.30
