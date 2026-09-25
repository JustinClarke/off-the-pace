"""
Environment configuration for ingestion.

FastF1 needs no credentials, so config is deliberately small: a cache
directory, a bronze output root, a log level, and a request timeout, each
overridable by an environment variable (optionally via a `.env` file).
"""

import logging
import os
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

logger = logging.getLogger(__name__)


class EnvironmentConfig:
    """Load environment variables with sensible defaults."""

    def __init__(self, env_file: Optional[Path] = None):
        """
        Initialize configuration.

        Args:
            env_file: Path to .env file. If None, searches parent directories.
        """
        self._load_env_file(env_file)

    @staticmethod
    def _load_env_file(env_file: Optional[Path]) -> None:
        """Load .env file if present."""
        if env_file:
            if env_file.exists():
                load_dotenv(env_file)
                logger.debug(f"Loaded environment from {env_file}")
            return

        search_dirs = [
            Path.cwd(),
            Path(__file__).parent.parent,
            Path(__file__).parent.parent.parent,
        ]

        for search_dir in search_dirs:
            env_path = search_dir / ".env"
            if env_path.exists():
                load_dotenv(env_path)
                logger.debug(f"Loaded environment from {env_path}")
                return

    @property
    def fastf1_cache_dir(self) -> Path:
        """FastF1 cache directory. Default: data/cache"""
        default = Path(__file__).resolve().parent.parent.parent / "data" / "cache"
        val = os.getenv("FASTF1_CACHE_DIR", str(default))
        return Path(val)

    @property
    def bronze_dir(self) -> Path:
        """Bronze root that ingest.py writes under. Default: data/bronze.

        Point INGESTION_BRONZE_DIR (or ingest.py --bronze-dir) at a scratch
        directory for probes and tests, so they never write into data/bronze.
        """
        default = Path(__file__).resolve().parent.parent.parent / "data" / "bronze"
        return Path(os.getenv("INGESTION_BRONZE_DIR", str(default)))

    @property
    def log_level(self) -> str:
        """Logging level. Default: INFO"""
        return os.getenv("INGESTION_LOG_LEVEL", "INFO").upper()

    @property
    def timeout_seconds(self) -> float:
        """Per-request timeout in seconds. Default: 300"""
        try:
            return float(os.getenv("INGESTION_TIMEOUT_SECONDS", "300"))
        except ValueError:
            logger.warning("INGESTION_TIMEOUT_SECONDS is not a valid number; using 300")
            return 300.0


def get_config(env_file: Optional[Path] = None) -> EnvironmentConfig:
    """Get or create the global environment configuration."""
    return EnvironmentConfig(env_file)
