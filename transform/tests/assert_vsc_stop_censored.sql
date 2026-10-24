{{ config(severity='error', tags=['simulation', 'strategy']) }}
-- CO-09, D6 amendment (owner ruling 2026-10-24). A stint that ended under a
-- virtual safety car (end_cause vsc_pit) is censored for stint life, same as
-- a safety-car stop, and counts as did-not-reach-the-flag (reached_flag
-- FALSE). Fails on any vsc_pit stint that is not censored or reached the
-- flag, so the ruling cannot drift back to an uncensored reading.
SELECT
    stint_id,
    stint_end_cause,
    is_stint_life_censored,
    reached_flag
FROM {{ ref('int_stint_end_regime') }}
WHERE
    stint_end_cause = 'vsc_pit'
    AND (
        is_stint_life_censored IS NOT TRUE
        OR reached_flag IS NOT FALSE
    )
