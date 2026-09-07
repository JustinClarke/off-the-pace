# Module 06 — Testing with pytest

> **Goal:** Write tests that catch real bugs — fixtures, parametrize, mocking, and the patterns the repo uses to gate every build.

---

## 1. Concept: Your first test

pytest discovers any function starting with `test_` in files starting with `test_`.

```python
# test_math.py
def test_addition():
    assert 1 + 1 == 2

def test_string_upper():
    assert "hello".upper() == "HELLO"
```

Run with: `pytest test_math.py -v`

```
test_math.py::test_addition PASSED
test_math.py::test_string_upper PASSED
```

---

## 2. Concept: Fixtures — reusable test setup

A fixture provides test data or resources. It runs before each test that requests it.

```python
import pytest
import pandas as pd

@pytest.fixture
def sample_laps():
    """60-row DataFrame that looks like real Bronze lap data."""
    return pd.DataFrame({
        "DriverNumber": [1, 2, 3] * 20,
        "LapNumber":    list(range(1, 61)),
        "LapTime":      [90.0 + i * 0.1 for i in range(60)],
        "Compound":     ["SOFT", "MEDIUM", "HARD"] * 20,
        "TyreLife":     list(range(1, 61)),
        "race_id":      ["2024_1"] * 60,
    })

def test_has_60_rows(sample_laps):
    assert len(sample_laps) == 60

def test_all_compounds_present(sample_laps):
    compounds = set(sample_laps["Compound"].unique())
    assert compounds == {"SOFT", "MEDIUM", "HARD"}
```

### Codebase connection

The ingestion tests use exactly this fixture pattern:

```python
# ingestion/tests/test_ingestion.py (lines 16-24)
@pytest.fixture
def mock_laps_df():
    return pd.DataFrame({
        "DriverNumber": [1, 2, 3] * 20,
        "LapNumber":    list(range(1, 61)),
        "LapTime":      [90.0 + i * 0.1 for i in range(60)],
        "Compound":     ["SOFT", "MEDIUM", "HARD"] * 20,
        "TyreLife":     list(range(1, 61)),
        "race_id":      ["2024_1"] * 60,
    })
```

The ML tests share fixtures via `conftest.py`:

```python
# ml/tests/conftest.py
@pytest.fixture(scope="session")
def load():
    """Cached feature loader — expensive, so session-scoped (runs once)."""
    cache = {}
    def _load(target):
        if target not in cache:
            cache[target] = F.load_features(target=target)
        return cache[target]
    return _load
```

`scope="session"` means the fixture runs once for the entire test session, not once per test. Loading features from DuckDB is slow — caching it prevents redundant 10-second loads.

---

## 3. Concept: `@pytest.mark.parametrize` — test many inputs

Instead of writing three separate tests, parametrize runs the same test with different inputs.

```python
@pytest.mark.parametrize("compound,expected_grip", [
    ("SOFT", 1.0),
    ("MEDIUM", 0.85),
    ("HARD", 0.70),
    ("INTERMEDIATE", 0.60),
])
def test_compound_grip(compound, expected_grip):
    grip_map = {"SOFT": 1.0, "MEDIUM": 0.85, "HARD": 0.70, "INTERMEDIATE": 0.60}
    assert grip_map[compound] == expected_grip
```

### Codebase connection

The ML tests parametrize across all three model families:

```python
# ml/tests/test_features.py (lines 21-25)
@pytest.mark.parametrize("target", ["degradation_regressor_p50", "stint_life_regressor", "cliff_classifier"])
def test_no_leaked_columns(load, target):
    X = load(target).X_train
    leaked = set(X.columns) & S.EXCLUDED_LEAKAGE_COLUMNS
    assert not leaked, f"leaked/identity columns in X for {target}: {sorted(leaked)}"
```

This runs the leakage check three times — once per model family. If a new feature accidentally includes `race_year`, all three will fail.

---

## 4. Concept: Mocking — replace real APIs with fake ones

```python
from unittest.mock import patch, MagicMock

# Replace requests.get with a fake
@patch("requests.get")
def test_api_returns_data(mock_get):
    # Configure the mock
    mock_get.return_value.status_code = 200
    mock_get.return_value.json.return_value = [{"lap": 1, "time": 91.2}]
    
    # Call the function under test
    import requests
    resp = requests.get("https://api.example.com/laps")
    data = resp.json()
    
    # Assert
    assert len(data) == 1
    assert data[0]["lap"] == 1
    mock_get.assert_called_once()
```

### Codebase connection

```python
# ingestion/tests/test_ingestion.py (lines 76-82)
@patch("api_client.requests.get")
def test_get_live_lap(mock_get):
    client = F1ApiClient()
    mock_get.return_value.status_code = 200
    mock_get.return_value.json.return_value = [{"lap_number": 1, "driver_number": 1}]
    lap = client.get_live_lap(1, 1)
    assert lap["lap_number"] == 1
```

**Why mock?** The real OpenF1 API requires network access, is rate-limited, and returns different data over time. Mocking lets you test the *client logic* (retry, parsing) without depending on the API being up.

---

## 5. Concept: Testing for expected exceptions

```python
def test_schema_validation_raises():
    df = pd.DataFrame({"DriverNumber": [1], "LapNumber": [1]})
    # Missing required columns — should raise ValueError
    with pytest.raises(ValueError, match="Missing required columns"):
        DataQualityEngine.validate_bronze_schema(df)
```

`pytest.raises()` asserts that the code inside the `with` block raises the expected exception. The `match` parameter checks the error message with a regex.

### Codebase connection

```python
# ingestion/tests/test_ingestion.py (lines 47-49)
def test_validate_bronze_schema(mock_laps_df):
    assert DataQualityEngine.validate_bronze_schema(mock_laps_df) is True
    invalid_df = mock_laps_df.drop(columns=["LapTime"])
    with pytest.raises(ValueError, match="Missing required columns"):
        DataQualityEngine.validate_bronze_schema(invalid_df)
```

---

## 6. Concept: The `tokenize` trick — testing source code itself

The ML tests don't just test behavior — they test the *source code* to prevent hardcoded values:

```python
# ml/tests/test_features.py (lines 89-98)
def test_no_hardcoded_holdout():
    """No numeric literal 2024/2025 in ml/src code."""
    offenders = []
    for path in SRC_DIR.glob("*.py"):
        src = path.read_text()
        for tok in tokenize.generate_tokens(io.StringIO(src).readline):
            if tok.type == tokenize.NUMBER and tok.string in {"2024", "2025"}:
                offenders.append(f"{path.name}:{tok.start[0]} -> {tok.string}")
    assert not offenders, f"hardcoded holdout year(s) in code: {offenders}"
```

This uses Python's `tokenize` module to parse source code and find any numeric literal `2024` or `2025`. Why? Because the holdout season is **derived** from the data (`MAX(race_year) + 1`). Hardcoding it would break when a new season is added.

---

## 7. Guided exercises

### Exercise 1: Write a test suite for a slug function

```python
# slug.py
def make_slug(event_name: str) -> str:
    """Convert an event name to a filesystem-safe slug."""
    return event_name.lower().replace(" ", "_").replace("'", "")
```

```python
# test_slug.py
import pytest
from slug import make_slug

@pytest.mark.parametrize("input_name,expected", [
    ("Australian Grand Prix", "australian_grand_prix"),
    ("Monaco Grand Prix", "monaco_grand_prix"),
    ("São Paulo Grand Prix", "são_paulo_grand_prix"),
    ("Emilia Romagna Grand Prix", "emilia_romagna_grand_prix"),
    # Edge case: apostrophe
    ("70th Anniversary Grand Prix", "70th_anniversary_grand_prix"),
])
def test_slug_parametrized(input_name, expected):
    assert make_slug(input_name) == expected

def test_slug_empty_string():
    assert make_slug("") == ""

def test_slug_already_slugged():
    assert make_slug("bahrain_grand_prix") == "bahrain_grand_prix"
```

Run: `pytest test_slug.py -v`

### Exercise 2: Test with fixtures and exceptions

```python
# quality.py
class QualityChecker:
    REQUIRED = ["driver", "lap", "time"]
    
    @staticmethod
    def validate(df):
        missing = [c for c in QualityChecker.REQUIRED if c not in df.columns]
        if missing:
            raise ValueError(f"Missing: {missing}")
        if len(df) < 10:
            raise ValueError(f"Too few rows: {len(df)}")
        return True
```

```python
# test_quality.py
import pytest
import pandas as pd
from quality import QualityChecker

@pytest.fixture
def valid_df():
    return pd.DataFrame({
        "driver": [f"D{i}" for i in range(20)],
        "lap":    list(range(1, 21)),
        "time":   [90 + i * 0.1 for i in range(20)],
    })

@pytest.fixture
def small_df():
    return pd.DataFrame({"driver": ["VER"], "lap": [1], "time": [91.0]})

def test_valid_passes(valid_df):
    assert QualityChecker.validate(valid_df) is True

def test_missing_column_raises(valid_df):
    bad = valid_df.drop(columns=["time"])
    with pytest.raises(ValueError, match="Missing"):
        QualityChecker.validate(bad)

def test_too_few_rows_raises(small_df):
    with pytest.raises(ValueError, match="Too few rows"):
        QualityChecker.validate(small_df)
```

### Exercise 3: Mock an HTTP call

```python
# client.py
import requests

def fetch_standings(season: int):
    resp = requests.get(f"https://api.example.com/{season}/standings", timeout=10)
    resp.raise_for_status()
    return resp.json()
```

```python
# test_client.py
from unittest.mock import patch
from client import fetch_standings

@patch("client.requests.get")
def test_fetch_standings_success(mock_get):
    mock_get.return_value.status_code = 200
    mock_get.return_value.json.return_value = {"standings": [{"driver": "VER", "points": 575}]}
    
    result = fetch_standings(2024)
    
    assert result["standings"][0]["driver"] == "VER"
    mock_get.assert_called_once_with(
        "https://api.example.com/2024/standings", timeout=10
    )

@patch("client.requests.get")
def test_fetch_standings_error(mock_get):
    mock_get.return_value.raise_for_status.side_effect = Exception("500 Server Error")
    
    try:
        fetch_standings(2024)
        assert False, "Should have raised"
    except Exception as e:
        assert "500" in str(e)
```

---

## 8. Interview drills

**Q1:** What's the difference between `scope="function"` and `scope="session"` for a fixture?

> **A:** `function` (default) runs the fixture before *every* test that uses it — each test gets a fresh copy. `session` runs it once for the entire test run and reuses the result. The ML tests use `scope="session"` for the feature loader because loading features from DuckDB takes ~10 seconds — loading once and sharing is much faster than loading 8 times.

**Q2:** Why mock external APIs in tests?

> **A:** Three reasons: (1) **Speed** — no network round-trip. (2) **Reliability** — tests pass even when the API is down. (3) **Determinism** — the API returns different data over time; mocks return the same data every run. Without mocking, a CI build could fail because the Jolpica API was temporarily unavailable.

**Q3:** How does `pytest.raises()` differ from a try/except in tests?

> **A:** `pytest.raises()` is both an assertion and a context manager. If the exception is *not* raised, the test **fails** — it asserts the exception is expected. A try/except would silently pass if the exception weren't raised, hiding a bug. The `match` parameter also verifies the error message.

**Q4:** What does the `test_no_hardcoded_holdout` test protect against?

> **A:** It prevents anyone from writing `if year == 2025` in the ML code. The holdout season must be *derived* from the data (`MAX(race_year) + 1`), so when 2025 data is ingested, the holdout automatically becomes 2026. A hardcoded value would require a code change every season. The test uses `tokenize` to scan source code for literal numbers.

**Q5:** How would you test a function that writes files?

> **A:** Use `tmp_path` (a built-in pytest fixture that provides a temporary directory). Write the file there, then assert its contents. The directory is cleaned up automatically after the test. Example: `my_function(output_dir=tmp_path)`, then `assert (tmp_path / "output.parquet").exists()`.

---

## 9. Checkpoint

You should now be able to:

- [ ] Write pytest tests with descriptive names
- [ ] Create fixtures for test data
- [ ] Use `@pytest.mark.parametrize` to test multiple inputs
- [ ] Mock HTTP calls with `@patch` and `MagicMock`
- [ ] Assert expected exceptions with `pytest.raises`
- [ ] Explain fixture scopes (`function`, `session`, `module`)
- [ ] Understand source-code-level tests (the `tokenize` pattern)
