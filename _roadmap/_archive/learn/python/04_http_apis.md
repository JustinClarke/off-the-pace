# Module 04 — HTTP Clients & API Patterns

> **Goal:** Build robust HTTP clients with rate limiting, retry logic, pagination, and error handling — the patterns behind the repo's data ingestion.

---

## 1. Concept: The `requests` library

```python
import requests

# Simple GET
response = requests.get("https://api.jolpi.ca/ergast/f1/2024/driverStandings.json", timeout=10)
response.raise_for_status()  # raises HTTPError if status code >= 400
data = response.json()       # parse JSON body
```

Key rules:
- **Always set `timeout`** — without it, a hung server blocks your script forever
- **Always call `raise_for_status()`** — otherwise a 500 error silently returns bad data
- **Use `response.json()`** not `json.loads(response.text)` — it handles encoding

### Codebase connection

`api_client.py` wraps two APIs:

```python
# ingestion/src/api_client.py (lines 72-79)
url = f"https://api.openf1.org/v1/laps?driver_number={driver_number}&lap_number={lap_number}"
response = requests.get(url, timeout=10)
response.raise_for_status()
data = response.json()
return data[0] if data else None
```

---

## 2. Concept: Exponential backoff retry

When an API fails (network glitch, rate limit, server overload), you retry — but not immediately. Exponential backoff waits longer after each failure: 1s → 2s → 4s → 8s.

```python
import time

def with_retry(fn, max_attempts=4, base_delay=1.0):
    """Call fn(), retrying with exponential backoff on failure."""
    last_exc = None
    for attempt in range(max_attempts):
        try:
            return fn()
        except Exception as exc:
            last_exc = exc
            if attempt < max_attempts - 1:
                delay = base_delay * (2 ** attempt)  # 1, 2, 4, 8...
                print(f"Attempt {attempt + 1}/{max_attempts} failed: {exc} — retrying in {delay:.0f}s")
                time.sleep(delay)
    raise last_exc  # all attempts failed
```

### Codebase connection

The ingestion layer uses this exact pattern:

```python
# ingestion/src/ingest.py (lines 114-132)
def _with_retry(fn, max_attempts: int = 4, base_delay: float = 1.0):
    last_exc = None
    for attempt in range(max_attempts):
        try:
            return fn()
        except Exception as exc:
            last_exc = exc
            if attempt < max_attempts - 1:
                delay = base_delay * (2 ** attempt)
                logger.warning(f"Attempt {attempt+1}/{max_attempts} failed: {exc} — retrying in {delay:.0f}s")
                time.sleep(delay)
    raise last_exc
```

And it's used with a lambda to wrap the FastF1 session load:

```python
# ingestion/src/ingest.py (line 421)
session = _with_retry(lambda: _load_race_session(year, round_num))
```

---

## 3. Concept: Rate limiting (politeness)

APIs have limits. Hitting them too fast gets you blocked. Rate limiting spaces out requests.

```python
import time

class RateLimitedClient:
    def __init__(self, min_interval_s: float = 0.30):
        self.min_interval_s = min_interval_s
        self._last_request_at = 0.0
    
    def _throttle(self):
        elapsed = time.monotonic() - self._last_request_at
        if elapsed < self.min_interval_s:
            time.sleep(self.min_interval_s - elapsed)
        self._last_request_at = time.monotonic()
    
    def get(self, url):
        self._throttle()
        response = requests.get(url, timeout=15)
        response.raise_for_status()
        return response.json()
```

**`time.monotonic()`** is better than `time.time()` for measuring intervals because it can't jump backward (e.g., when the system clock is adjusted).

### Codebase connection

The `JolpicaClient` uses exactly this pattern:

```python
# ingestion/src/jolpica_client.py (lines 49-53)
def _throttle(self) -> None:
    elapsed = time.monotonic() - self._last_request_at
    if elapsed < self.min_interval_s:
        time.sleep(self.min_interval_s - elapsed)
    self._last_request_at = time.monotonic()
```

---

## 4. Concept: Pagination

Many APIs return data in pages. You request page 1, check if there's more, request page 2, etc.

```python
def get_all_pages(base_url, page_size=100):
    """Fetch all pages from a paginated API."""
    all_items = []
    offset = 0
    
    while True:
        response = requests.get(
            base_url,
            params={"limit": page_size, "offset": offset},
            timeout=15,
        )
        response.raise_for_status()
        data = response.json()
        
        items = data.get("items", [])
        all_items.extend(items)
        
        total = data.get("total", 0)
        offset += page_size
        if offset >= total:
            break
    
    return all_items
```

### Codebase connection

```python
# ingestion/src/jolpica_client.py (lines 93-110)
def _get_paginated(self, path: str) -> list[dict[str, Any]]:
    first = self._get(path)
    total = int(first.get("total", 0))
    envelopes = [first]
    offset = PAGE_LIMIT
    while offset < total:
        # ... fetch next page
        offset += PAGE_LIMIT
    return envelopes
```

---

## 5. Concept: Handling 429 (Too Many Requests)

When you hit a rate limit, the API returns HTTP 429 with an optional `Retry-After` header telling you how long to wait.

```python
except requests.HTTPError as exc:
    status = exc.response.status_code if exc.response is not None else None
    if status == 429:
        retry_after = float(exc.response.headers.get("Retry-After", 2))
        time.sleep(retry_after)
        continue  # retry the request
```

### Codebase connection

```python
# ingestion/src/jolpica_client.py (lines 76-84)
except requests.HTTPError as exc:
    status = exc.response.status_code if exc.response is not None else None
    if status == 429 and attempt < max_attempts - 1:
        retry_after = float(exc.response.headers.get("Retry-After", 2 ** attempt))
        logger.warning(f"  429 from Jolpica — backing off {retry_after:.0f}s")
        time.sleep(retry_after)
        continue
```

---

## 6. Concept: Flattening nested JSON

Real APIs return deeply nested JSON. You need to flatten it into tabular data.

```python
# API returns nested structure:
# {"MRData": {"StandingsTable": {"StandingsLists": [{"DriverStandings": [...]}]}}}

def flatten_standings(nested_json):
    """Extract flat rows from Ergast-style nested standings."""
    lists = nested_json.get("StandingsTable", {}).get("StandingsLists", [])
    if not lists:
        return []
    
    rows = []
    for standing in lists[0].get("DriverStandings", []):
        driver = standing.get("Driver", {})
        rows.append({
            "position": int(standing.get("position", 0)),
            "points": float(standing.get("points", 0)),
            "driver_id": driver.get("driverId"),
            "driver_code": driver.get("code"),
        })
    return rows
```

### Codebase connection

This is exactly what `jolpica_client.py` does with `_flatten_standings()` and `_flatten_pit_stops()`. Notice the safe `.get()` calls with defaults — API data is never guaranteed to have every field.

---

## 7. Guided exercises

### Exercise 1: Build a retry wrapper

```python
import time
import random

# Simulate a flaky API
call_count = 0
def flaky_api():
    global call_count
    call_count += 1
    if random.random() < 0.7:  # 70% failure rate
        raise ConnectionError(f"Connection refused (attempt {call_count})")
    return {"status": "ok", "data": [1, 2, 3]}


def with_retry(fn, max_attempts=5, base_delay=0.1):
    """YOUR IMPLEMENTATION HERE"""
    # Hint: loop over attempts, try fn(), catch exceptions, sleep with exponential backoff
    pass


# Test it
random.seed(42)
call_count = 0
result = with_retry(flaky_api)
print(f"Got result after {call_count} attempts: {result}")
```

**Expected behavior:** Retries up to 5 times with delays of 0.1s, 0.2s, 0.4s, 0.8s.

### Exercise 2: Build a rate-limited client

```python
import time

class SimpleClient:
    """HTTP client that enforces a minimum interval between requests."""
    
    def __init__(self, min_interval_s=0.5):
        self.min_interval_s = min_interval_s
        self._last_request_at = 0.0
    
    def _throttle(self):
        """YOUR IMPLEMENTATION: sleep if needed to respect min_interval_s"""
        pass
    
    def get(self, url):
        self._throttle()
        print(f"[{time.monotonic():.2f}] GET {url}")
        # In real code: return requests.get(url, timeout=10).json()
        return {"url": url, "time": time.monotonic()}


# Test: 5 requests should take at least 2 seconds (5 × 0.5s intervals)
client = SimpleClient(min_interval_s=0.5)
t0 = time.monotonic()
for i in range(5):
    client.get(f"https://example.com/page/{i}")
elapsed = time.monotonic() - t0
print(f"\n5 requests took {elapsed:.1f}s (min expected: 2.0s)")
```

### Exercise 3: Flatten nested JSON

```python
# Simulate Ergast-style nested pit stop data
raw = {
    "RaceTable": {
        "Races": [{
            "raceName": "Bahrain Grand Prix",
            "PitStops": [
                {"driverId": "max_verstappen", "stop": "1", "lap": "15", "duration": "23.5"},
                {"driverId": "max_verstappen", "stop": "2", "lap": "35", "duration": "22.1"},
                {"driverId": "lewis_hamilton", "stop": "1", "lap": "18", "duration": "24.0"},
            ]
        }]
    }
}

def flatten_pit_stops(mrdata: dict) -> list[dict]:
    """Extract flat pit stop records from nested Ergast JSON.
    
    Return list of dicts with: driver_id, stop (int), lap (int), duration_s (float).
    Handle missing/invalid values gracefully.
    """
    # YOUR IMPLEMENTATION HERE
    pass


stops = flatten_pit_stops(raw)
for stop in stops:
    print(stop)
# Expected:
# {'driver_id': 'max_verstappen', 'stop': 1, 'lap': 15, 'duration_s': 23.5}
# {'driver_id': 'max_verstappen', 'stop': 2, 'lap': 35, 'duration_s': 22.1}
# {'driver_id': 'lewis_hamilton', 'stop': 1, 'lap': 18, 'duration_s': 24.0}
```

---

## 8. Interview drills

**Q1:** Why use exponential backoff instead of fixed-interval retries?

> **A:** If the server is overloaded, fixed-interval retries (e.g., every 1 second) make the problem worse — many clients all retrying at the same rate pile up requests. Exponential backoff (1s, 2s, 4s, 8s) naturally spreads out retry traffic. Some implementations add **jitter** (random variation) to prevent thundering herd — many clients backing off to the same power-of-two delay and all retrying simultaneously.

**Q2:** What's the difference between `time.time()` and `time.monotonic()`?

> **A:** `time.time()` returns wall-clock time and can jump backward (NTP sync, DST, manual clock change). `time.monotonic()` always increases, making it correct for measuring intervals. For rate limiting, a backwards clock jump could cause the throttle to think no time has passed and sleep unnecessarily long.

**Q3:** Why set a `timeout` on every HTTP request?

> **A:** Without a timeout, a request to a non-responding server blocks the process **forever**. During a 7-season ingestion (30–45 minutes), one hung request would stall the entire pipeline. The repo uses `timeout=10` for OpenF1 and `timeout=15` for Jolpica.

**Q4:** How would you add a circuit breaker to this client?

> **A:** A circuit breaker tracks recent failures. After N consecutive failures, it "opens" (stops trying) for a cooldown period, then "half-opens" (allows one test request). If the test succeeds, it "closes" (normal operation). This prevents a cascade of doomed requests when an API is completely down. Python libraries like `pybreaker` implement this, but you can build it with a counter and timestamp.

---

## 9. Checkpoint

You should now be able to:

- [ ] Make HTTP requests with `requests`, handling errors and timeouts
- [ ] Implement exponential backoff retry logic
- [ ] Build a rate-limited client with `time.monotonic()`
- [ ] Paginate through API results
- [ ] Handle 429 rate limit responses
- [ ] Flatten nested JSON into flat records
