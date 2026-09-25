-- T13 (WI-09, F14). A disqualified driver is never a classified finisher: every
-- stg_results row with status = 'Disqualified' has is_classified FALSE, is_dnf
-- TRUE and dnf_cause 'non_classified'.
--
-- The flags used to be read from ClassifiedPosition alone. Thirteen disqualified
-- drivers carry 'D' there and resolved correctly; three (HAM and LEC at 2023_18,
-- RUS at 2024_14) carry a numeric position in bronze and read as classified
-- finishers with is_dnf FALSE and no cause, which fct_ghost_race_finish then
-- published as an official finishing position. stg_results now decides status
-- first, so the rule holds whatever bronze leaves in ClassifiedPosition. This is
-- the guard on that routing: it fails the day a change to the flags stops
-- honouring it.
--
-- Severity is the default (error), not the audit's suggested warn: bronze can no
-- longer make this fail, only the transform can.

SELECT
    race_year,
    race_id,
    driver_id,
    status,
    classified_position,
    is_classified,
    is_dnf,
    dnf_cause
FROM {{ ref('stg_results') }}
WHERE
    status = 'Disqualified'
    AND (
        is_classified
        OR NOT is_dnf
        OR dnf_cause IS DISTINCT FROM 'non_classified'
    )
