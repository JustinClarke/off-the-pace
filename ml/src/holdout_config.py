"""Holdout season configuration.

WI-03 ruling (FD4, 2026-09-28): pin holdout_season = 2026 instead of deriving
MAX(race_year)+1 dynamically. This allows the holdout to actually hold rows as
2026 data is ingested incrementally.

holdout_populated is derived from warehouse state: false until holdout_season
has rows in fct_cliff_prediction_features.
"""

# Pinned holdout season. Change this to move the holdout to a different season.
# Must be a completed or in-progress season, not a future one.
HOLDOUT_SEASON = 2026
