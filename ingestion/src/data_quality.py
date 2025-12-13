"""
DataQualityEngine   schema validation and quality checks for Bronze-layer data.
"""

import pandas as pd
import logging
from typing import Dict, Any, List

logger = logging.getLogger(__name__)

# Columns that uniquely identify a lap. Duplicates here indicate corrupted or
# double-ingested data   the most common real corruption pattern in lap files.
LAP_KEY_COLUMNS: List[str] = ["race_id", "DriverNumber", "LapNumber"]


class DataQualityEngine:
    """Schema validation and quality checks for F1 Bronze layer data."""

    # Columns that must be present in every valid Bronze laps file.
    # These come from FastF1 session.laps and are essential for downstream analysis.
    REQUIRED_COLUMNS = [
        'DriverNumber',  # FIA driver number
        'LapNumber',     # 1-indexed lap number within the session
        'LapTime',       # Lap duration (nanoseconds in parquet; converted to seconds in dbt)
        'Compound',      # Pirelli compound: SOFT, MEDIUM, HARD, INTERMEDIATE, WET
        'TyreLife',      # Laps completed on the current tyre set
        'race_id',       # Added by ingestion: format YYYY_RoundNumber
    ]

    @staticmethod
    def validate_bronze_schema(df: pd.DataFrame) -> bool:
        """
        Check that all required columns exist.

        Raises:
            ValueError: if any required column is absent
        """
        missing = [c for c in DataQualityEngine.REQUIRED_COLUMNS if c not in df.columns]
        if missing:
            raise ValueError(f"Missing required columns: {missing}")
        return True

    @staticmethod
    def check_null_rates(df: pd.DataFrame, threshold: float = 0.05) -> Dict[str, float]:
        """
        Calculate null rates per column and log any above threshold.

        High null rates in a laps file typically indicate:
       -Race ended early (red flag, safety car incident)
       -Partial session load
       -FastF1 data gap for a specific driver/lap

        Args:
            threshold: Acceptable null rate   default 5%

        Returns:
            Dict mapping column name → null rate (0.0–1.0)
        """
        null_rates = df.isnull().mean().to_dict()
        high = {k: v for k, v in null_rates.items() if v > threshold}
        if high:
            logger.warning(f"Columns above {threshold*100:.0f}% null threshold: {high}")
        return null_rates

    @staticmethod
    def assert_row_count(df: pd.DataFrame, min_rows: int = 50) -> bool:
        """
        Ensure the DataFrame meets a minimum row count.

        Catches truncated files and abandoned-race sessions (e.g. red-flagged after lap 2).

        Raises:
            ValueError: if row count is below min_rows
        """
        if len(df) < min_rows:
            raise ValueError(f"Insufficient rows: {len(df)} < {min_rows}")
        return True

    @staticmethod
    def check_lap_key_duplicates(df: pd.DataFrame) -> int:
        """
        Check for duplicate (race_id, DriverNumber, LapNumber) combinations.

        Duplicates indicate double-ingestion or FastF1 returning overlapping lap records,
        which would silently corrupt aggregations downstream.

        Returns:
            Count of duplicate rows (0 = clean). Logs a warning if any found.
        """
        key_cols = [c for c in LAP_KEY_COLUMNS if c in df.columns]
        if len(key_cols) < len(LAP_KEY_COLUMNS):
            missing = set(LAP_KEY_COLUMNS)-set(key_cols)
            logger.warning(f"Duplicate-key check skipped   missing columns: {missing}")
            return 0

        dupe_mask = df.duplicated(subset=key_cols, keep=False)
        dupe_count = int(dupe_mask.sum())
        if dupe_count:
            sample = df[dupe_mask][key_cols].head(5).to_dict("records")
            logger.warning(
                f"Duplicate lap keys detected: {dupe_count} rows affected. Sample: {sample}"
            )
        return dupe_count

    @staticmethod
    def generate_quality_report(df: pd.DataFrame) -> Dict[str, Any]:
        """
        Generate a summary quality report for a single parquet file.

        Returns:
            Dict with row_count, column_count, columns, null_rates, dtypes, valid_schema,
            duplicate_lap_keys
        """
        return {
            "row_count":          len(df),
            "column_count":       len(df.columns),
            "columns":            list(df.columns),
            "null_rates":         DataQualityEngine.check_null_rates(df),
            "dtypes":             df.dtypes.astype(str).to_dict(),
            "valid_schema":       DataQualityEngine.validate_bronze_schema(df),
            "duplicate_lap_keys": DataQualityEngine.check_lap_key_duplicates(df),
        }
