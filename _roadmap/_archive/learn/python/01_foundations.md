# Module 01 — Python Foundations & Project Structure

> **Goal:** Understand how a real Python project is organized, how virtual environments work, and how modules import each other.

---

## 1. Concept: Virtual environments

A virtual environment is an isolated Python installation. It keeps *this* project's packages separate from every other project on your machine.

```bash
# Create a venv (one time)
python3 -m venv .venv

# Activate it (every terminal session)
source .venv/bin/activate   # macOS/Linux
# .venv\Scripts\activate    # Windows

# Install packages into it
pip install pandas pyarrow
```

**Why it matters:** The Off The Pace repo has *three* `requirements.txt` files (root, ingestion, ml). Each layer needs specific versions. Without a venv, version conflicts would break everything.

### Codebase connection

Look at the `Makefile` targets:

```makefile
# From the repo Makefile
setup:
    python3 -m venv .venv
    ./.venv/bin/pip install -r requirements.txt

ml-setup:
    ./.venv/bin/pip install -r ml/requirements.txt
```

Notice: the Makefile always calls `./.venv/bin/pip` explicitly — it never assumes `pip` on `$PATH`. This prevents the classic mistake of installing into the wrong Python.

---

## 2. Concept: `pathlib.Path`

The `pathlib` module replaces the old `os.path.join()` pattern. It's the standard in modern Python.

```python
from pathlib import Path

# Build paths by joining with /
project_root = Path(__file__).resolve().parent.parent
data_dir = project_root / "data" / "bronze"
laps_file = data_dir / "laps" / "season=2024" / "race=bahrain" / "laps.parquet"

# Check existence
if laps_file.exists():
    print(f"File is {laps_file.stat().st_size} bytes")

# Read/write text
config = Path("config.json")
config.write_text('{"key": "value"}')
text = config.read_text()

# Glob for files
for parquet in data_dir.glob("**/*.parquet"):
    print(parquet.name)
```

### Codebase connection

In `ingestion/src/ingest.py` (lines 36–50):

```python
PROJECT_ROOT   = Path(__file__).resolve().parent.parent.parent
BRONZE_DIR     = PROJECT_ROOT / "data" / "bronze"
LAPS_DIR       = BRONZE_DIR / "laps"
WEATHER_DIR    = BRONZE_DIR / "weather"
TELEMETRY_DIR  = BRONZE_DIR / "telemetry"
```

This pattern — anchoring to `__file__` and walking up with `.parent` — is how *every* script in the repo finds the project root, regardless of where you `cd` to.

---

## 3. Concept: `__name__` and `if __name__ == "__main__"`

Every `.py` file has a `__name__` variable:
- If you *run* the file directly: `__name__` is `"__main__"`
- If you *import* the file: `__name__` is the module name (like `"ingest"`)

```python
# greet.py
def hello(name):
    return f"Hello, {name}!"

if __name__ == "__main__":
    # Only runs when you do: python greet.py
    print(hello("world"))
```

### Codebase connection

The ML layer uses a slightly more advanced pattern — `raise SystemExit(main())`:

```python
# ml/src/train.py (line 178-179)
if __name__ == "__main__":
    raise SystemExit(main())
```

Why `raise SystemExit(main())`?
- `main()` returns an integer exit code (0 = success, 1 = failure)
- `SystemExit` sets the process exit code, so CI can detect failures
- It's cleaner than `sys.exit()` because it's exception-based

---

## 4. Concept: Imports — relative, absolute, and local

```python
# Absolute import (preferred in this repo)
from ml.src import schema as S
from ml.src import features as F

# Relative import (used inside packages)
from . import schema as S    # same package
from .. import utils          # parent package

# Local import (inside a function — deferred loading)
def heavy_function():
    import shap  # only imported when this function is called
```

### Codebase connection

The ingestion layer uses *implicit* relative imports because each script runs from `ingestion/src/`:

```python
# ingestion/src/ingest.py (lines 30-32)
from data_quality import DataQualityEngine
from environment import get_config
from logging_config import setup_logging
```

The ML layer uses *absolute* imports because it's a proper package:

```python
# ml/src/train.py (lines 28-29)
from ml.src import features as F
from ml.src import schema as S
```

---

## 5. Guided exercises

### Exercise 1: Build a mini project skeleton

Create this structure on your machine:

```
my_f1_project/
├── requirements.txt
├── src/
│   ├── __init__.py
│   ├── config.py
│   └── main.py
└── tests/
    └── test_config.py
```

**Step 1:** Create the directory and venv

```bash
mkdir -p my_f1_project/src my_f1_project/tests
cd my_f1_project
python3 -m venv .venv
source .venv/bin/activate
```

**Step 2:** Write `requirements.txt`

```
pandas>=2,<3
pyarrow
pytest
```

**Step 3:** Write `src/config.py`

```python
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
BRONZE_DIR = DATA_DIR / "bronze"

SEASONS = list(range(2018, 2025))  # 2018 through 2024

def get_season_dir(season: int) -> Path:
    """Return the bronze directory for a given season."""
    return BRONZE_DIR / f"season={season}"
```

**Step 4:** Write `src/main.py`

```python
from pathlib import Path
from src.config import PROJECT_ROOT, SEASONS, get_season_dir


def show_project_layout():
    print(f"Project root: {PROJECT_ROOT}")
    print(f"Seasons: {SEASONS[0]}–{SEASONS[-1]}")
    for season in SEASONS[:3]:
        path = get_season_dir(season)
        exists = "✓" if path.exists() else "✗"
        print(f"  {exists} {path}")


if __name__ == "__main__":
    show_project_layout()
```

**Step 5:** Run it

```bash
pip install -r requirements.txt
python -m src.main
```

Expected output:

```
Project root: /path/to/my_f1_project
Seasons: 2018–2024
  ✗ /path/to/my_f1_project/data/bronze/season=2018
  ✗ /path/to/my_f1_project/data/bronze/season=2019
  ✗ /path/to/my_f1_project/data/bronze/season=2020
```

### Exercise 2: Explore the real repo structure

Open a Python REPL inside the repo's venv:

```bash
cd /path/to/off-the-pace
source .venv/bin/activate
python3
```

```python
from pathlib import Path

root = Path(".")
# Count Python files by layer
for layer in ["ingestion", "ml", "scripts"]:
    py_files = list((root / layer).rglob("*.py"))
    print(f"{layer}: {len(py_files)} Python files")

# Find the heaviest Python file
all_py = list(root.rglob("*.py"))
biggest = max(all_py, key=lambda p: p.stat().st_size)
print(f"\nBiggest: {biggest} ({biggest.stat().st_size:,} bytes)")
```

---

## 6. Interview drills

**Q1:** What happens if you install a package globally instead of in a virtual environment?

> **A:** It can conflict with other projects that need different versions of the same package. A venv isolates dependencies per project. In this repo, the root `requirements.txt` pins `duckdb==1.5.3` because the transform layer's hash-based regression tests depend on that exact version producing the same floating-point output.

**Q2:** What does `Path(__file__).resolve().parent.parent` do?

> **A:** `__file__` is the path to the current script. `.resolve()` makes it absolute (follows symlinks). Each `.parent` moves up one directory. So if the file is at `/project/src/lib/utils.py`, `.parent.parent` gives `/project/src`. This is how scripts in the repo find the project root regardless of the working directory.

**Q3:** Why does the ML code use `raise SystemExit(main())` instead of just calling `main()`?

> **A:** `main()` returns an integer (0 for success, 1 for failure). `SystemExit` turns that into the process exit code. CI pipelines check exit codes to decide if a step passed. A bare `main()` call would always exit 0, hiding failures.

**Q4:** When would you use a local import (inside a function) instead of a top-level import?

> **A:** When the dependency is heavy or optional. In `evaluate.py`, `import shap` is inside the `dual_importance()` function because SHAP takes seconds to import and isn't needed for every evaluation. The ingestion layer doesn't need SHAP at all, so a top-level import would slow down every ingestion run unnecessarily.

---

## 7. Checkpoint

You should now be able to:

- [ ] Create a virtual environment and explain why it exists
- [ ] Use `pathlib.Path` to build file paths (no more `os.path.join`)
- [ ] Explain the `if __name__ == "__main__"` guard
- [ ] Distinguish absolute vs relative imports
- [ ] Navigate the Off The Pace repo structure and find files by layer
