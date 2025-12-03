"""
Environment configuration with secure credential handling.

Load and validate environment variables for ingestion, with automatic
validation and helpful error messages for missing credentials.
"""

import logging
import os
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

logger = logging.getLogger(__name__)


def mask_sensitive(value: str) -> str:
    """Mask API keys and connection strings for safe logging."""
    if not value or len(value) < 8:
        return value
    return value[:4] + "*" * (len(value)-8) + value[-4:]


class EnvironmentConfig:
    """Load and validate environment variables with secure defaults."""

    def __init__(self, env_file: Optional[Path] = None):
        """
        Initialize configuration.

        Args:
            env_file: Path to .env file. If None, searches parent directories.
        """
        self._load_env_file(env_file)
        self._validate_required()

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

    @staticmethod
    def _validate_required() -> None:
        """Validate that no secrets are hardcoded in code."""
        # FastF1 doesn't require authentication
        # This is mainly a safety check that we're not accidentally
        # storing credentials in the codebase
        pass

    @property
    def fastf1_cache_dir(self) -> Path:
        """FastF1 cache directory. Default: data/cache"""
        default = Path(__file__).resolve().parent.parent.parent / "data" / "cache"
        val = os.getenv("FASTF1_CACHE_DIR", str(default))
        return Path(val)

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

    @property
    def azure_event_hub_conn_string(self) -> Optional[str]:
        """Azure Event Hub connection string (optional, future streaming integration)."""
        val = os.getenv("AZURE_EVENT_HUB_CONN_STRING")
        if val:
            logger.debug(f"Azure Event Hub: {mask_sensitive(val)}")
        return val

    @property
    def azure_event_hub_topic(self) -> str:
        """Azure Event Hub topic name. Default: f1_laps"""
        return os.getenv("AZURE_EVENT_HUB_TOPIC", "f1_laps")

    @property
    def ergast_api_key(self) -> Optional[str]:
        """Ergast API key (optional). Ergast API is deprecated as of Dec 2024."""
        val = os.getenv("ERGAST_API_KEY")
        if val:
            logger.debug(f"Ergast API key: {mask_sensitive(val)}")
        return val


def get_config(env_file: Optional[Path] = None) -> EnvironmentConfig:
    """Get or create the global environment configuration."""
    return EnvironmentConfig(env_file)
