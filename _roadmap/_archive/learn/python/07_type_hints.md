# Module 07 — Type Hints & Static Analysis

> **Goal:** Add type annotations to Python code and use tools like mypy to catch bugs before runtime.

---

## 1. Concept: Basic type hints

Type hints tell other developers (and tools) what types a function expects and returns.

```python
def add(a: int, b: int) -> int:
    return a + b

def greet(name: str) -> str:
    return f"Hello, {name}!"

def process_laps(laps: list[float]) -> float:
    return sum(laps) / len(laps)
```

Type hints are **not enforced at runtime**. Python won't stop you from passing a string to `add()`. The value is in **documentation** and **static analysis** (mypy catches type errors before you run the code).

---

## 2. Concept: Common types

```python
from typing import Optional, Any

# Basic types
x: int = 42
y: float = 3.14
name: str = "VER"
flag: bool = True

# Collections (Python 3.9+ — no need to import from typing)
drivers: list[str] = ["VER", "HAM", "NOR"]
points: dict[str, int] = {"VER": 575, "HAM": 211}
pairs: tuple[str, int] = ("VER", 575)          # fixed length
columns: tuple[str, ...] = ("a", "b", "c")     # variable length

# Optional = can be None
def find_driver(code: str) -> Optional[str]:    # str | None in 3.10+
    return None

# Union (Python 3.10+ syntax)
def parse_value(v: str | int | None) -> float:
    return float(v) if v is not None else 0.0
```

### Codebase connection

The ML schema uses `|` union syntax (Python 3.10+):

```python
# ml/src/schema.py (line 142)
quantile_alpha: float | None = None
num_class: int | None = None
```

The ingestion layer uses `Optional` from `typing` (older style):

```python
# ingestion/src/jolpica_client.py (line 22)
from typing import Any, Optional

def _to_int(v: Any) -> Optional[int]:
    try:
        return int(v) if v is not None and v != "" else None
    except (ValueError, TypeError):
        return None
```

---

## 3. Concept: Function signatures from the repo

```python
# Simple: all arguments and return typed
def _slug(event_name: str) -> str:
    return event_name.lower().replace(" ", "_")

# Complex: tuple return, default arguments
def ingest_race(
    year: int,
    round_num: int,
    slug: str,
    force: bool,
    skip_telemetry: bool,
    run_id: str = "",
) -> tuple[str, dict]:
    ...

# Keyword-only arguments (after *)
def load_features(
    duckdb_path: str = "data/dev.duckdb",
    target: str | None = None,
    *,                              # everything after * is keyword-only
    persist_encoders: bool = False,
) -> FeatureBundle:
    ...
```

The `*` in `load_features` means `persist_encoders` can only be passed as `persist_encoders=True`, never positionally. This prevents calling `load_features("path", "p50", True)` where it's unclear what `True` means.

---

## 4. Concept: mypy — the static type checker

mypy reads your type hints and finds bugs without running the code.

```bash
pip install mypy
mypy my_file.py
```

```python
# bug.py
def add(a: int, b: int) -> int:
    return a + b

result = add("hello", 42)  # mypy catches this: Argument 1 has incompatible type "str"
```

### Codebase connection

The ingestion layer has its own mypy config:

```ini
# ingestion/mypy.ini
[mypy]
python_version = 3.11
warn_return_any = True
warn_unused_configs = True
disallow_untyped_defs = False

[mypy-fastf1.*]
ignore_missing_imports = True
```

`ignore_missing_imports = True` for FastF1 means mypy won't complain about FastF1's lack of type stubs. Third-party libraries often don't have type annotations.

---

## 5. Concept: `from __future__ import annotations`

```python
from __future__ import annotations

# Without this import (Python < 3.10):
def process(items: list[str]) -> dict[str, int]:  # SyntaxError in Python 3.8!
    ...

# With this import: all annotations are strings (deferred evaluation)
# Works even in Python 3.8
```

### Codebase connection

Every ML module starts with this:

```python
# ml/src/features.py (line 15)
from __future__ import annotations
```

This enables `list[str]` and `dict[str, int]` syntax without importing `List` and `Dict` from `typing`, and allows forward references (using a class name before it's defined).

---

## 6. Concept: Type hints for Pandas

Pandas doesn't have great built-in type support. The pragmatic approach:

```python
import pandas as pd
import numpy as np

def process(df: pd.DataFrame) -> pd.DataFrame:
    """Process a DataFrame. Column expectations documented in docstring."""
    return df

def get_target(df: pd.DataFrame, target: str) -> pd.Series:
    return df[target]

def compute_metric(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    return float(np.mean((y_true - y_pred) ** 2))
```

### Codebase connection

The evaluate module types numpy arrays explicitly:

```python
# ml/src/evaluate.py (lines 83-86)
def _score(spec: S.TargetSpec, y_true: np.ndarray, pred: np.ndarray) -> float:
    _, value = T._headline(spec, y_true, pred)
    return value
```

---

## 7. Guided exercises

### Exercise 1: Add type hints to untyped functions

```python
# Add type hints to all functions below

def make_race_id(year, round_num):
    return f"{year}_{round_num}"

def filter_season(df, year):
    return df[df["season"] == year]

def compute_null_rates(df, threshold):
    rates = df.isnull().mean().to_dict()
    return {k: v for k, v in rates.items() if v > threshold}

def load_config(path):
    import json
    from pathlib import Path
    text = Path(path).read_text()
    return json.loads(text)
```

**Solution:**

```python
import pandas as pd
from pathlib import Path

def make_race_id(year: int, round_num: int) -> str:
    return f"{year}_{round_num}"

def filter_season(df: pd.DataFrame, year: int) -> pd.DataFrame:
    return df[df["season"] == year]

def compute_null_rates(df: pd.DataFrame, threshold: float) -> dict[str, float]:
    rates = df.isnull().mean().to_dict()
    return {k: v for k, v in rates.items() if v > threshold}

def load_config(path: str | Path) -> dict:
    import json
    text = Path(path).read_text()
    return json.loads(text)
```

### Exercise 2: Spot the type errors

```python
# Which lines would mypy flag?

def process_lap(driver: str, lap_num: int, time_s: float) -> dict[str, str | float]:
    return {"driver": driver, "lap": lap_num, "time": time_s}  # Line A

result = process_lap("VER", 1, 91.2)
print(result["driver"].upper())   # Line B — is this safe?

speeds: list[int] = [200, 210, "fast", 220]  # Line C

def get_best(times: list[float]) -> float:
    return min(times) if times else None  # Line D — return type mismatch!
```

**Answers:**
- **Line A:** OK — `lap_num` is `int` which is compatible with the return type `str | float`... wait, actually `int` is not `str | float`. mypy would flag this! The return type should be `dict[str, str | int | float]`.
- **Line B:** Risky — `result["driver"]` is typed as `str | float`. Calling `.upper()` on a float would crash. mypy would flag this.
- **Line C:** mypy flags `"fast"` — `list[int]` can't contain a `str`.
- **Line D:** Return type says `float` but the function can return `None`. Should be `float | None` or `Optional[float]`.

---

## 8. Interview drills

**Q1:** Are Python type hints enforced at runtime?

> **A:** No. They're metadata only. Python's interpreter ignores them. They serve two purposes: documentation (humans read them) and static analysis (mypy, pyright, IDE autocompletion). You can still pass a string where an int is expected — Python won't stop you. The value is catching bugs *before* runtime.

**Q2:** What's the difference between `list[str]` and `tuple[str, ...]`?

> **A:** `list[str]` is a mutable, variable-length sequence of strings. `tuple[str, ...]` is immutable and variable-length. `tuple[str, int]` is immutable and *fixed-length* — exactly one string and one int. The repo uses `tuple[str, ...]` for constants like `FEATURE_COLUMNS` because tuples can't be accidentally modified.

**Q3:** When would you use `from __future__ import annotations`?

> **A:** Two cases: (1) To use `list[str]` syntax in Python 3.8/3.9 (which otherwise require `List[str]` from typing). (2) To enable forward references — using a class name in a type hint before the class is defined. All ML modules in this repo use it.

**Q4:** Why does the ingestion `mypy.ini` set `ignore_missing_imports = True` for FastF1?

> **A:** FastF1 doesn't ship type stubs (`.pyi` files). Without this setting, mypy would error on every `import fastf1` line with "Cannot find implementation or library stub." The trade-off: mypy won't catch type errors in FastF1 API calls, but the alternative (not running mypy at all) is worse.

---

## 9. Checkpoint

You should now be able to:

- [ ] Add type hints to function signatures
- [ ] Use `str | None` and `Optional[str]`
- [ ] Understand `tuple[str, ...]` vs `list[str]`
- [ ] Run mypy and interpret its error messages
- [ ] Explain `from __future__ import annotations`
- [ ] Configure mypy to ignore untyped libraries
