# Module 05 — Classes, Dataclasses & OOP

> **Goal:** Understand when to use classes vs dataclasses vs plain functions, and how the repo uses each pattern.

---

## 1. Concept: Plain classes

A class bundles data and behavior together. Use a class when you have **state that changes** and **methods that operate on that state**.

```python
class LapTimer:
    def __init__(self, driver_id: str):
        self.driver_id = driver_id
        self.laps: list[float] = []
    
    def record_lap(self, time_s: float) -> None:
        self.laps.append(time_s)
    
    def best_lap(self) -> float:
        return min(self.laps) if self.laps else float("inf")
    
    def average(self) -> float:
        return sum(self.laps) / len(self.laps) if self.laps else 0.0

timer = LapTimer("VER")
timer.record_lap(91.2)
timer.record_lap(90.8)
print(f"Best: {timer.best_lap():.1f}s")  # Best: 90.8s
```

### Codebase connection: `DataQualityEngine`

The `DataQualityEngine` in `data_quality.py` uses a class with **all static methods** — it's essentially a namespace for related functions:

```python
# ingestion/src/data_quality.py (lines 16-28)
class DataQualityEngine:
    REQUIRED_COLUMNS = ['DriverNumber', 'LapNumber', 'LapTime', 'Compound', 'TyreLife', 'race_id']

    @staticmethod
    def validate_bronze_schema(df: pd.DataFrame) -> bool:
        missing = [c for c in DataQualityEngine.REQUIRED_COLUMNS if c not in df.columns]
        if missing:
            raise ValueError(f"Missing required columns: {missing}")
        return True
```

**Why a class with static methods?** It groups all quality-check functions under one name (`DataQualityEngine.validate_bronze_schema()`), and the class-level constant `REQUIRED_COLUMNS` is shared by all methods. You could also do this with a module and module-level constants, but the class makes the grouping explicit.

---

## 2. Concept: `@staticmethod` vs `@classmethod` vs regular methods

```python
class Example:
    shared_value = 42  # class variable
    
    def regular(self):
        """Has access to the instance (self)."""
        return self.shared_value
    
    @staticmethod
    def static_method(x):
        """No access to instance or class. Just a function in the namespace."""
        return x * 2
    
    @classmethod
    def class_method(cls):
        """Has access to the class (cls) but not a specific instance."""
        return cls.shared_value
```

**When to use which:**
- `@staticmethod` — the method doesn't need `self` or `cls`. It's a pure function that logically belongs to the class. **All methods in `DataQualityEngine` are static.**
- `@classmethod` — needs access to class-level data but not a specific instance. Rare in this repo.
- Regular method — needs access to instance data (`self`). Used in `JolpicaClient` where each instance tracks its own rate-limit state.

---

## 3. Concept: `@dataclass` — data containers without boilerplate

A `@dataclass` auto-generates `__init__`, `__repr__`, `__eq__`, and more from field annotations.

```python
from dataclasses import dataclass

# Without dataclass — lots of boilerplate
class LapResultOld:
    def __init__(self, driver_id, lap_number, time_s, compound):
        self.driver_id = driver_id
        self.lap_number = lap_number
        self.time_s = time_s
        self.compound = compound
    
    def __repr__(self):
        return f"LapResult({self.driver_id}, lap={self.lap_number}, {self.time_s}s)"
    
    def __eq__(self, other):
        return (self.driver_id == other.driver_id and 
                self.lap_number == other.lap_number and ...)

# With dataclass — clean and correct
@dataclass
class LapResult:
    driver_id: str
    lap_number: int
    time_s: float
    compound: str

lap = LapResult("VER", 1, 91.2, "SOFT")
print(lap)  # LapResult(driver_id='VER', lap_number=1, time_s=91.2, compound='SOFT')
```

---

## 4. Concept: `frozen=True` — immutable dataclasses

`@dataclass(frozen=True)` prevents modification after creation. Frozen dataclasses are hashable (can be used as dict keys or in sets).

```python
@dataclass(frozen=True)
class TargetSpec:
    name: str
    family: str
    kind: str          # "quantile" | "classification" | "regression"
    objective: str
    quantile_alpha: float | None = None

spec = TargetSpec("degradation_regressor_p50", "degradation_regressor", "quantile", "reg:quantileerror", 0.50)
# spec.name = "new"  # ERROR: FrozenInstanceError — can't modify!
```

### Codebase connection

The ML schema uses frozen dataclasses for model specifications:

```python
# ml/src/schema.py (lines 135-143)
@dataclass(frozen=True)
class TargetSpec:
    name: str
    family: str
    source_column: str
    kind: str
    objective: str
    quantile_alpha: float | None = None
    num_class: int | None = None
```

**Why frozen?** The `TargetSpec` defines a contract — the name, family, and objective of each model. If someone accidentally modified a spec during a training run, it would silently corrupt the pipeline. `frozen=True` turns that into a hard error.

---

## 5. Concept: `field(default_factory=...)` for mutable defaults

Python's famous gotcha: mutable default arguments are shared between instances.

```python
# WRONG — all instances share the same list!
@dataclass
class BadBundle:
    items: list = []  # This is a bug

# CORRECT — each instance gets its own list
from dataclasses import dataclass, field

@dataclass
class FeatureBundle:
    training_seasons: list[int] = field(default_factory=list)
```

### Codebase connection

```python
# ml/src/features.py (line 48)
@dataclass
class FeatureBundle:
    target_name: str | None
    X_train: pd.DataFrame
    y_train: pd.Series | None
    X_holdout: pd.DataFrame
    y_holdout: pd.Series | None
    groups_train: pd.Series
    meta_train: pd.DataFrame
    meta_holdout: pd.DataFrame
    encoders: dict[str, dict[str, int]]
    fingerprint: str
    feature_columns: list[str]
    holdout_season: int
    training_seasons: list[int] = field(default_factory=list)
```

`FeatureBundle` is a **data container** — it holds the entire train/holdout split plus metadata. Every downstream function (`train.py`, `evaluate.py`, `predict.py`) receives a `FeatureBundle` and extracts what it needs. This is the "bundle pattern" — one structured object instead of 12 separate function parameters.

---

## 6. Concept: `frozenset` — immutable sets for constants

A `frozenset` is a set you can't modify. It's hashable and can be a module-level constant.

```python
# Regular set — mutable (risky as a constant)
BAD_CONSTANTS = {"a", "b", "c"}
BAD_CONSTANTS.add("d")  # Oops, someone changed the "constant"

# frozenset — immutable (safe as a constant)
GOOD_CONSTANTS: frozenset[str] = frozenset({"a", "b", "c"})
# GOOD_CONSTANTS.add("d")  # AttributeError — can't modify!
```

### Codebase connection

The ML schema uses `frozenset` for the leakage exclusion set:

```python
# ml/src/schema.py (lines 34-54)
EXCLUDED_LEAKAGE_COLUMNS: frozenset[str] = frozenset({
    "driver_skill_residual_s", "driver_skill_proxy_s",
    "lap_id", "stint_id", "race_id", "race_year", "driver_id",
    "is_training_eligible",
    "next_lap_degradation_jump_s",
    "laps_until_cliff_class",
    "remaining_stint_life_laps",
    # ... more
})
```

**Why frozenset?** If someone accidentally added a feature column to the exclusion set during a run, it would silently drop a real feature. `frozenset` makes the exclusion list a hard, immutable contract.

---

## 7. Concept: `tuple[str, ...]` — immutable sequences for ordered constants

```python
# Tuple — immutable, ordered
FEATURE_COLUMNS: tuple[str, ...] = ("lap_number", "compound", "fuel_mass_kg")

# List — mutable, ordered (risky for constants)
feature_list = ["lap_number", "compound", "fuel_mass_kg"]
feature_list.append("oops")  # Constants shouldn't change!
```

### Codebase connection

The ML schema stores feature column order as a tuple:

```python
# ml/src/schema.py (lines 109-111)
FEATURE_COLUMNS: tuple[str, ...] = tuple(
    col for group in FEATURE_GROUPS.values() for col in group
)
```

**Why tuple?** The ONNX model expects features in **exactly this order**. If the order changed, the browser would pass "lap_number" to the slot that expects "compound". A tuple can't be reordered.

---

## 8. Guided exercises

### Exercise 1: Build a DataQualityChecker class

```python
from dataclasses import dataclass
import pandas as pd

@dataclass(frozen=True)
class QualityRule:
    """A single quality check definition."""
    name: str
    column: str
    check_type: str    # "not_null" | "min_value" | "unique"
    threshold: float   # for not_null: max null rate; for min_value: minimum

class QualityChecker:
    """Runs quality rules against a DataFrame."""
    
    def __init__(self, rules: list[QualityRule]):
        self.rules = rules
    
    def check(self, df: pd.DataFrame) -> list[dict]:
        """Run all rules. Return list of {rule, passed, detail} dicts."""
        results = []
        for rule in self.rules:
            if rule.check_type == "not_null":
                null_rate = df[rule.column].isnull().mean()
                passed = null_rate <= rule.threshold
                detail = f"null_rate={null_rate:.4f} (max={rule.threshold})"
            elif rule.check_type == "min_value":
                min_val = df[rule.column].min()
                passed = min_val >= rule.threshold
                detail = f"min={min_val} (expected >={rule.threshold})"
            elif rule.check_type == "unique":
                n_dupes = df[rule.column].duplicated().sum()
                passed = n_dupes == 0
                detail = f"duplicates={n_dupes}"
            else:
                passed = False
                detail = f"unknown check_type: {rule.check_type}"
            
            results.append({"rule": rule.name, "passed": passed, "detail": detail})
        return results


# Test it
rules = [
    QualityRule("driver_not_null", "driver", "not_null", 0.0),
    QualityRule("lap_positive", "lap", "min_value", 1.0),
    QualityRule("driver_lap_unique", "driver", "unique", 0.0),
]

df = pd.DataFrame({"driver": ["VER", "HAM", "VER", None], "lap": [1, 1, 2, 0]})
checker = QualityChecker(rules)
for r in checker.check(df):
    status = "✓" if r["passed"] else "✗"
    print(f"  {status} {r['rule']}: {r['detail']}")
```

### Exercise 2: Create a FeatureSpec dataclass

```python
from dataclasses import dataclass, field

@dataclass(frozen=True)
class FeatureSpec:
    """Specification for one ML feature."""
    name: str
    group: str          # e.g., "stint_position", "compound", "thermal"
    dtype: str          # "float32", "ordinal", "boolean"
    description: str
    nullable: bool = True

# Define a mini feature set
FEATURES = (
    FeatureSpec("lap_number", "stint_position", "float32", "Current lap number"),
    FeatureSpec("compound", "compound", "ordinal", "Tyre compound name"),
    FeatureSpec("fuel_mass_kg", "stint_position", "float32", "Estimated fuel load"),
    FeatureSpec("is_rain_lap", "weather_air", "boolean", "Whether rain was falling"),
)

# Build a lookup by name
FEATURE_BY_NAME = {f.name: f for f in FEATURES}

# Filter by group
thermal_features = [f for f in FEATURES if f.group == "stint_position"]
print(f"Stint position features: {[f.name for f in thermal_features]}")

# Can't modify (frozen)
try:
    FEATURES[0].name = "oops"
except Exception as e:
    print(f"Correctly prevented: {e}")
```

---

## 9. Interview drills

**Q1:** When would you use a `@dataclass` vs a plain class vs a named tuple?

> **A:** Use a **dataclass** when you need a structured data container with auto-generated `__init__`, `__repr__`, and `__eq__` — like `FeatureBundle` or `TargetSpec`. Use a **plain class** when you have mutable state with methods that modify it — like `JolpicaClient` with its rate-limit timer. Use a **NamedTuple** when you want a lightweight immutable record — it's similar to `frozen=True` but with tuple semantics (positional access, iteration).

**Q2:** What does `@dataclass(frozen=True)` give you?

> **A:** It makes instances immutable (can't change fields after creation) and hashable (can use as dict keys or in sets). Attempting to set an attribute raises `FrozenInstanceError`. In the repo, `TargetSpec` is frozen because model specifications are contracts that must never change during a run.

**Q3:** Why use `frozenset` instead of `set` for `EXCLUDED_LEAKAGE_COLUMNS`?

> **A:** `frozenset` is immutable — no one can accidentally `.add()` or `.remove()` a column during runtime. It's a compile-time guarantee that the leakage exclusion list can't be corrupted. It's also hashable, so it can be used as a dict key or stored in another set.

**Q4:** What's the "mutable default argument" bug and how do dataclasses prevent it?

> **A:** If you write `def __init__(self, items=[])`, all instances share the same list object. Modifying one instance's list affects all others. Dataclasses enforce `field(default_factory=list)`, which creates a **new** list for each instance. The `FeatureBundle` uses this for `training_seasons: list[int] = field(default_factory=list)`.

**Q5:** When is `@staticmethod` the right choice?

> **A:** When a method logically belongs to a class (for namespace organization) but doesn't need access to `self` or `cls`. All methods on `DataQualityEngine` are static — they operate on the DataFrame passed as an argument, not on any instance state. The class just groups related quality-check functions together.

---

## 10. Checkpoint

You should now be able to:

- [ ] Write classes with `__init__`, instance methods, and class variables
- [ ] Use `@staticmethod` for namespace-grouped functions
- [ ] Create `@dataclass` containers with type annotations
- [ ] Use `frozen=True` for immutable data contracts
- [ ] Avoid the mutable default argument bug with `field(default_factory=...)`
- [ ] Choose `frozenset` and `tuple` for immutable constants
