"""Holdout season configuration.

WI-03 ruling (FD4, 2026-09-28): pin holdout_season instead of deriving
MAX(race_year)+1 dynamically. FD4 pinned 2026; HD17 (owner, 2026-11-16, TX-29)
supersedes it: the holdout is 2025 and models train strictly on 2018-2024
(race_year < HOLDOUT_SEASON). 2026 is neither training nor holdout data and is not
yet defined for use. 2025 was already consumed as a selection fold (02c gate,
2026-09-23), so it is a holdout from 2026-11-16 on, not a never-seen season.
Must match transform/dbt_project.yml var holdout_season (guard:
transform/tasks/coefficients/tests/test_holdout_guard.py).

holdout_populated is derived from warehouse state: false until holdout_season
has rows in fct_cliff_prediction_features.
"""

# Pinned holdout season. Change this to move the holdout to a different season.
# Must be a completed or in-progress season, not a future one.
HOLDOUT_SEASON = 2025
