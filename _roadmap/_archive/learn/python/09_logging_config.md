# Module 09 — Logging, Config & Environment

> **Goal:** Use Python's logging module properly, load environment variables, and follow 12-factor app config principles.

---

## 1. Concept: `logging` vs `print`

`print()` goes to stdout and can't be filtered. `logging` gives you levels, formatting, and file output.

```python
import logging

logger = logging.getLogger(__name__)

logger.debug("Detailed trace — hidden in production")
logger.info("Normal operation — shown by default")
logger.warning("Something unexpected — investigate later")
logger.error("Something failed — needs attention")
```

Levels: `DEBUG < INFO < WARNING < ERROR < CRITICAL`. Setting the level filters out everything below it.

```python
logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(name)s | %(levelname)s | %(message)s")
logger.info("This shows")
logger.debug("This is hidden (below INFO level)")
```

### Codebase connection

Every module in the repo creates a module-level logger:

```python
# ingestion/src/ingest.py (line 34)
logger = logging.getLogger(__name__)
```

The `__name__` convention names the logger after the module (`ingestion.src.ingest`), so log messages tell you exactly which file they came from.

---

## 2. Concept: Centralized logging setup

```python
# logging_config.py
import logging

def setup_logging(level: str = "INFO") -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
```

### Codebase connection

```python
# ingestion/src/logging_config.py
import logging

def setup_logging(log_level: str = "INFO") -> None:
    logging.basicConfig(
        level=getattr(logging, log_level.upper(), logging.INFO),
        format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
    )
```

Called once at startup:

```python
# ingestion/src/ingest.py (line 681)
setup_logging(args.log_level)
```

---

## 3. Concept: Environment variables & `python-dotenv`

Environment variables keep secrets out of code.

```python
import os

# Read an env var (returns None if missing)
api_key = os.environ.get("API_KEY")

# With a default
cache_dir = os.environ.get("CACHE_DIR", "data/cache")

# Required (raises KeyError if missing)
db_url = os.environ["DATABASE_URL"]
```

`python-dotenv` loads variables from a `.env` file:

```bash
# .env (never commit this!)
FASTF1_CACHE_DIR=data/cache
BRONZE_DIR=data/bronze
```

```python
from dotenv import load_dotenv
load_dotenv()  # reads .env into os.environ

cache = os.environ.get("FASTF1_CACHE_DIR", "data/cache")
```

### Codebase connection

```python
# ingestion/src/environment.py
from dotenv import load_dotenv
import os
from pathlib import Path

def get_config():
    load_dotenv()
    return Config(
        fastf1_cache_dir=Path(os.environ.get("FASTF1_CACHE_DIR", "data/cache")),
    )
```

The `.env.example` file documents expected variables without exposing secrets:

```bash
# ingestion/.env.example
FASTF1_CACHE_DIR=data/cache
OPENF1_API_URL=https://api.openf1.org/v1
```

---

## 4. Concept: `os.environ` vs `os.getenv` vs `dotenv`

```python
# os.environ["KEY"]      — KeyError if missing
# os.environ.get("KEY")  — None if missing
# os.getenv("KEY")       — same as .get() but less explicit
# os.environ.get("KEY", "default")  — default if missing
```

### Codebase connection

The ML schema uses `os.environ.get` with a default for the database path:

```python
# ml/src/schema.py (line 24)
DUCKDB_PATH = os.environ.get("DUCKDB_PATH", "data/dev.duckdb")
```

This lets CI override the path (`DUCKDB_PATH=data/ci.duckdb`) without changing code.

---

## 5. Concept: When to use `logger.warning` vs `logger.error`

- **`warning`** — something unexpected happened but the program can continue. "This lap has no telemetry — skipping."
- **`error`** — something failed and the operation couldn't complete. "Schedule fetch failed for 2024."

The repo follows this convention carefully:

```python
# Warning: skippable issue
logger.warning(f"  Weather failed for {slug}: {exc}")

# Warning: quality concern but not fatal
logger.warning(f"  DQ SCHEMA FAIL [{label}]: {exc}")

# Error: operation completely failed
logger.error(f"Schedule fetch failed for {year}: {exc}")
```

---

## 6. Concept: f-strings in log messages

```python
# GOOD — f-string (evaluated immediately, clean syntax)
logger.info(f"Loaded {len(df):,} rows from {path}")

# OLD STYLE — %-formatting (lazy evaluation, but harder to read)
logger.info("Loaded %d rows from %s", len(df), path)

# The %-style is slightly better for performance (string not built if level is filtered)
# but the repo uses f-strings everywhere for readability
```

### Codebase connection

The repo consistently uses f-strings with formatting:

```python
# ingestion/src/ingest.py (line 251)
logger.info(f"  Telemetry: {len(df):,} samples")

# ml/src/train.py (line 145)
print(f"[{target}] {headline_name}_cv={headline:.4f}  rows={len(X)}  {fit_seconds}s  -> {bst_path.name}")
```

---

## 7. Guided exercises

### Exercise 1: Set up a logging pipeline

```python
import logging
from pathlib import Path

def setup_logging(level: str = "INFO", log_file: str | None = None):
    """Configure logging with console and optional file output."""
    fmt = "%(asctime)s | %(name)s | %(levelname)s | %(message)s"
    handlers = [logging.StreamHandler()]
    
    if log_file:
        Path(log_file).parent.mkdir(parents=True, exist_ok=True)
        handlers.append(logging.FileHandler(log_file))
    
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format=fmt,
        handlers=handlers,
    )


# Use it
setup_logging("DEBUG", log_file="logs/test.log")
logger = logging.getLogger("my_tool")
logger.debug("Debug details")
logger.info("Processing started")
logger.warning("Missing data for race 5")
logger.error("Failed to connect to API")

print(f"\nLog file contents:")
print(Path("logs/test.log").read_text())
```

### Exercise 2: Config class with dotenv

```python
import os
from dataclasses import dataclass
from pathlib import Path

@dataclass
class Config:
    bronze_dir: Path
    cache_dir: Path
    db_path: Path
    log_level: str
    
    @classmethod
    def from_env(cls) -> "Config":
        """Load config from environment variables with sensible defaults."""
        return cls(
            bronze_dir=Path(os.environ.get("BRONZE_DIR", "data/bronze")),
            cache_dir=Path(os.environ.get("CACHE_DIR", "data/cache")),
            db_path=Path(os.environ.get("DUCKDB_PATH", "data/dev.duckdb")),
            log_level=os.environ.get("LOG_LEVEL", "INFO"),
        )


# Test without any env vars (uses defaults)
config = Config.from_env()
print(f"Bronze: {config.bronze_dir}")
print(f"DB:     {config.db_path}")
print(f"Log:    {config.log_level}")

# Test with overrides
os.environ["DUCKDB_PATH"] = "data/ci.duckdb"
os.environ["LOG_LEVEL"] = "DEBUG"
config2 = Config.from_env()
print(f"\nOverridden DB: {config2.db_path}")
print(f"Overridden log: {config2.log_level}")
```

---

## 8. Interview drills

**Q1:** Why use `logging` instead of `print`?

> **A:** Logging provides: (1) **Levels** — filter by severity (debug vs error). (2) **Formatting** — timestamps, module names, automatic. (3) **Routing** — write to files, send to monitoring systems, without changing code. (4) **Performance** — filtered messages don't build the string. `print` goes to stdout with no structure.

**Q2:** What's 12-factor app config?

> **A:** Configuration (database URLs, API keys, feature flags) should come from environment variables, not hardcoded values or config files in the repo. This lets the same code run in dev (`DUCKDB_PATH=data/dev.duckdb`), CI (`data/ci.duckdb`), and production without code changes. The repo follows this for `DUCKDB_PATH`, `FASTF1_CACHE_DIR`, and `VITE_DATA_BASE`.

**Q3:** Why does the repo use `.env.example` instead of committing `.env`?

> **A:** `.env` may contain secrets (API keys, credentials). `.env.example` documents the *shape* of the config without exposing values. The `.gitignore` includes `.env` but not `.env.example`. New contributors copy `.env.example` to `.env` and fill in their own values.

**Q4:** When should you use `logger.warning()` vs `raise`?

> **A:** Use `warning` when the error is recoverable and the pipeline should continue — "No telemetry for this race, skipping." Use `raise` when the error is fatal — "Missing required columns in schema." The ingestion layer warns on missing optional data but raises on corrupted required data.

---

## 9. Checkpoint

You should now be able to:

- [ ] Set up Python logging with levels and formatting
- [ ] Create a module-level logger with `getLogger(__name__)`
- [ ] Load config from environment variables with defaults
- [ ] Use `python-dotenv` for local development
- [ ] Distinguish `warning` from `error` in practice
- [ ] Explain 12-factor config principles
