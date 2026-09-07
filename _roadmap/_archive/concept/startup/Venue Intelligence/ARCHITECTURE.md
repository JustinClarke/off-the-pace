# Technical Architecture — Live Venue Capacity Intelligence

> How the system works, end to end. Written for engineers, not investors.

---

## Architecture Overview

The system evolves through three phases, each adding data sources and
infrastructure complexity. **Phase 1 is deliberately simple** — batch ingestion
of historical event data. Streaming infrastructure is introduced in Phase 2
only when real-time data sources are available.

```
Phase 1 (Event Manager — batch)
================================
CSV/API exports ──► Python ingestion ──► DuckDB ──► Analytics + Report

Phase 2 (Venue Partnership — streaming)
========================================
Ticket scans ──┐
Wi-Fi probes ──┼──► Redpanda ──► Flink/Materialize ──► PostgreSQL ──► Dashboard
POS events ────┘                                    └──► DuckDB (historical)

Phase 3 (Municipal — enriched streaming)
=========================================
Phase 2 streams ──┐
Dubai Pulse data ─┼──► Enriched Flink pipeline ──► Multi-venue analytics
RTA transit ──────┘
```

---

## Phase 1: Batch Analytics on Historical Event Data

**This is where you start.** No streaming, no Kafka, no Flink. Just Python,
DuckDB, and real data from your event management contact.

### Data Ingestion

```python
# ingestion/load_event_data.py
"""
Ingest ticket scan CSVs + POS exports from event management platforms.
Normalize into a unified event schema.
"""

import duckdb
import pandas as pd
from pathlib import Path
from datetime import datetime

UNIFIED_SCHEMA = {
    "event_id": "VARCHAR",
    "timestamp": "TIMESTAMP",
    "venue_id": "VARCHAR",
    "zone_id": "VARCHAR",          # gate / bar / stage area
    "source_type": "VARCHAR",      # TICKET_SCAN | POS | MANUAL_COUNT
    "direction": "VARCHAR",        # IN | OUT | TRANSACTION
    "count": "INTEGER",            # +1 for entry, -1 for exit, 1 for txn
    "metadata": "JSON",            # source-specific payload
}

def load_ticket_scans(csv_path: Path, event_id: str, venue_id: str) -> pd.DataFrame:
    """
    Expected CSV columns (from Eventbrite/Platinumlist):
    - scan_time: ISO timestamp
    - gate: gate identifier
    - direction: in/out
    - ticket_type: GA, VIP, etc.
    """
    df = pd.read_csv(csv_path, parse_dates=["scan_time"])
    return pd.DataFrame({
        "event_id": event_id,
        "timestamp": df["scan_time"],
        "venue_id": venue_id,
        "zone_id": df["gate"],
        "source_type": "TICKET_SCAN",
        "direction": df["direction"].str.upper(),
        "count": df["direction"].map({"in": 1, "out": -1}).fillna(0).astype(int),
        "metadata": df.get("ticket_type", "GENERAL").apply(
            lambda t: f'{{"ticket_type": "{t}"}}'
        ),
    })

def load_pos_transactions(csv_path: Path, event_id: str, venue_id: str) -> pd.DataFrame:
    """
    Expected CSV columns:
    - transaction_time: ISO timestamp
    - terminal_id: POS terminal identifier
    - amount: transaction amount (AED)
    - items: item count
    """
    df = pd.read_csv(csv_path, parse_dates=["transaction_time"])
    return pd.DataFrame({
        "event_id": event_id,
        "timestamp": df["transaction_time"],
        "venue_id": venue_id,
        "zone_id": df["terminal_id"],
        "source_type": "POS",
        "direction": "TRANSACTION",
        "count": 1,
        "metadata": df.apply(
            lambda r: f'{{"amount": {r["amount"]}, "items": {r["items"]}}}', axis=1
        ),
    })
```

### Analytical Models (DuckDB)

```sql
-- models/occupancy_curve.sql
-- Running occupancy count over time (cumulative IN minus OUT)
SELECT
    event_id,
    timestamp,
    zone_id,
    SUM(count) OVER (
        PARTITION BY event_id, zone_id
        ORDER BY timestamp
        ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
    ) AS running_occupancy,
    source_type
FROM unified_events
WHERE source_type = 'TICKET_SCAN'
ORDER BY timestamp;

-- models/peak_detection.sql
-- Find the top-5 busiest 15-minute windows per zone
WITH windowed AS (
    SELECT
        event_id,
        zone_id,
        time_bucket(INTERVAL '15 minutes', timestamp) AS window_start,
        SUM(CASE WHEN direction = 'IN' THEN count ELSE 0 END) AS arrivals,
        SUM(CASE WHEN direction = 'OUT' THEN ABS(count) ELSE 0 END) AS departures
    FROM unified_events
    WHERE source_type = 'TICKET_SCAN'
    GROUP BY event_id, zone_id, window_start
)
SELECT *,
    arrivals - departures AS net_flow,
    RANK() OVER (PARTITION BY event_id, zone_id ORDER BY arrivals DESC) AS peak_rank
FROM windowed
QUALIFY peak_rank <= 5;

-- models/staffing_mismatch.sql
-- Cross-reference occupancy with staff schedule to find gaps
SELECT
    o.event_id,
    o.window_start,
    o.zone_id,
    o.running_occupancy,
    s.staff_count,
    o.running_occupancy / NULLIF(s.staff_count, 0) AS attendees_per_staff,
    CASE
        WHEN o.running_occupancy / NULLIF(s.staff_count, 0) > 150 THEN 'CRITICALLY_UNDERSTAFFED'
        WHEN o.running_occupancy / NULLIF(s.staff_count, 0) > 100 THEN 'UNDERSTAFFED'
        WHEN o.running_occupancy / NULLIF(s.staff_count, 0) < 20  THEN 'OVERSTAFFED'
        ELSE 'ADEQUATE'
    END AS staffing_status
FROM occupancy_by_window o
LEFT JOIN staff_schedule s
    ON o.event_id = s.event_id
    AND o.zone_id = s.zone_id
    AND o.window_start BETWEEN s.shift_start AND s.shift_end;

-- models/spend_velocity.sql
-- Revenue per attendee per 15-minute window
SELECT
    p.event_id,
    p.window_start,
    p.zone_id,
    p.total_revenue,
    o.running_occupancy,
    p.total_revenue / NULLIF(o.running_occupancy, 0) AS revenue_per_head,
    p.transaction_count
FROM (
    SELECT
        event_id,
        zone_id,
        time_bucket(INTERVAL '15 minutes', timestamp) AS window_start,
        SUM(CAST(json_extract(metadata, '$.amount') AS DOUBLE)) AS total_revenue,
        COUNT(*) AS transaction_count
    FROM unified_events
    WHERE source_type = 'POS'
    GROUP BY event_id, zone_id, window_start
) p
JOIN occupancy_by_window o
    ON p.event_id = o.event_id
    AND p.zone_id = o.zone_id
    AND p.window_start = o.window_start;
```

### Output: Post-Event Ops Report

The Phase 1 deliverable is a generated PDF/HTML report containing:

1. **Arrival/departure curve** — line chart of running occupancy over time, per zone
2. **Peak windows** — table of top-5 busiest 15-min windows with headcounts
3. **Staffing heatmap** — zones × time blocks, color-coded by staffing adequacy
4. **Spend velocity** — revenue-per-head over time (if POS data available)
5. **Recommendations** — "Add 3 bar staff between 20:45–21:30 in Zone A based on
   arrival surge pattern"

---

## Phase 2: Real-Time Streaming (Kappa Architecture)

**Only build this when you have a venue partner providing live data feeds.**

### Unified Event Schema (Avro/JSON Schema)

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "UnifiedSpatialEvent",
  "type": "object",
  "properties": {
    "event_id":    { "type": "string", "format": "uuid" },
    "timestamp":   { "type": "string", "format": "date-time" },
    "venue_id":    { "type": "string" },
    "zone_id":     { "type": "string" },
    "source_type": { "type": "string", "enum": ["TICKET_SCAN", "WIFI_PROBE", "POS", "PARKING_LOOP", "MANUAL_COUNT"] },
    "sensor_id":   { "type": "string" },
    "direction":   { "type": "string", "enum": ["IN", "OUT", "PROBE", "TRANSACTION"] },
    "delta_count": { "type": "integer" }
  },
  "required": ["event_id", "timestamp", "venue_id", "source_type", "direction", "delta_count"]
}
```

### Streaming Infrastructure

```
┌─────────────────────────────────────────────────────────────────────┐
│                        INGESTION LAYER                              │
│                                                                     │
│  Ticket scanner webhook ──┐                                         │
│  Wi-Fi probe syslog ──────┼──► Connector (normalize to schema) ──►  │
│  POS webhook ─────────────┘                                         │
└───────────────────────────────────┬─────────────────────────────────┘
                                    │
┌───────────────────────────────────▼─────────────────────────────────┐
│                    Redpanda (Event Streaming)                       │
│                                                                     │
│  Topics:                                                            │
│    sensor-ingest-stream     (raw, partitioned by venue_id)          │
│    occupancy-updates        (computed, partitioned by venue_id)     │
│    staffing-alerts          (threshold breaches)                    │
└───────────────────────────────────┬─────────────────────────────────┘
                                    │
┌───────────────────────────────────▼─────────────────────────────────┐
│                STREAM PROCESSING (Flink / Materialize)              │
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │  Materialized View: live_venue_occupancy                    │    │
│  │                                                             │    │
│  │  SELECT                                                     │    │
│  │      venue_id,                                              │    │
│  │      zone_id,                                               │    │
│  │      SUM(CASE                                               │    │
│  │          WHEN direction = 'IN' THEN delta_count             │    │
│  │          WHEN direction = 'OUT' THEN -delta_count           │    │
│  │          ELSE 0                                             │    │
│  │      END) AS current_occupancy,                             │    │
│  │      COUNT(CASE WHEN source_type = 'WIFI_PROBE'             │    │
│  │          THEN 1 END) AS wifi_probe_count,                   │    │
│  │      MAX(timestamp) AS last_updated                         │    │
│  │  FROM spatial_sensor_stream                                 │    │
│  │  WHERE timestamp >= NOW() - INTERVAL '15 minutes'           │    │
│  │  GROUP BY venue_id, zone_id;                                │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │  Alert Rule: staffing_threshold_breach                      │    │
│  │                                                             │    │
│  │  EMIT TO 'staffing-alerts'                                  │    │
│  │  WHEN current_occupancy / expected_staff > 150              │    │
│  │  FOR zone_id IN active_zones                                │    │
│  └─────────────────────────────────────────────────────────────┘    │
└───────────────────────────────────┬─────────────────────────────────┘
                                    │
                 ┌──────────────────┴──────────────────┐
                 │                                      │
    ┌────────────▼────────────┐           ┌────────────▼────────────┐
    │   HISTORICAL STORAGE    │           │    REAL-TIME SERVING    │
    │   DuckDB (OLAP)         │           │    PostgreSQL           │
    │   Post-event analytics  │           │    + WebSocket push     │
    └─────────────────────────┘           └────────────┬────────────┘
                                                       │
                                          ┌────────────▼────────────┐
                                          │    Dashboard (React)    │
                                          │    Live occupancy map   │
                                          │    Staffing alerts      │
                                          │    Spend velocity       │
                                          └─────────────────────────┘
```

### Wi-Fi Probe Calibration (Critical)

Wi-Fi probe counts are **not** absolute headcounts due to MAC randomization.
They must be calibrated against a ground-truth signal:

```python
# calibration/wifi_calibration.py
"""
Calibrate Wi-Fi probe counts against ticket scan ground truth.
Produces a venue-specific correction factor.
"""

def compute_calibration_factor(
    ticket_scan_count: int,
    wifi_probe_count: int,
    time_window_minutes: int = 15
) -> float:
    """
    Simple linear calibration:
    actual_occupancy ≈ wifi_probe_count × calibration_factor

    Must be recomputed per-venue (different Wi-Fi density, different
    phone penetration rates, different AP placement).
    """
    if wifi_probe_count == 0:
        return 1.0
    return ticket_scan_count / wifi_probe_count

# In practice: compute this factor over multiple events at the same venue,
# take the median, and apply it as a venue-specific constant. Update it
# whenever ticket scan data is available as ground truth.
```

---

## Phase 3: Municipal Data Enrichment

### Dubai Pulse Data Access

**How to apply:**

1. Create a UAE PASS account (uaepass.ae)
2. Log in to dubaipulse.gov.ae
3. Navigate to "Request Data"
4. Submit application with:
   - Use case description (venue occupancy analytics)
   - Data requested (RTA parking occupancy, transit ridership by station)
   - Data handling plan (aggregated, anonymized, PDPL-compliant)
   - Organization details

**Alternative path:** DDA iPaaS Developer Portal (developer.digitaldubai.ae)
for technical API integration — requires the same UAE PASS auth but provides
more structured API access.

**What's realistically available:**

| Dataset | Format | Granularity | Real-time? |
|---|---|---|---|
| RTA parking occupancy | CSV / API | Per-lot, hourly | Batched (not streaming) |
| Dubai Metro ridership | CSV | Per-station, daily | Batched |
| Bus ridership | CSV | Per-route, daily | Batched |
| Traffic flow counts | CSV | Per-sensor, 15-min | Near-real-time via iPaaS |

**Key limitation:** Dubai Pulse "real-time" is typically batched at 15-minute
to hourly intervals, not sub-second streaming. Design accordingly — use it as
an enrichment signal on the historical OLAP side (DuckDB), not as a streaming
input to Flink.

---

## Stack Summary

| Layer | Phase 1 | Phase 2 | Phase 3 |
|---|---|---|---|
| **Ingestion** | Python scripts, CSV | Redpanda connectors | + Dubai Pulse API poller |
| **Processing** | DuckDB SQL | Flink / Materialize | + municipal enrichment joins |
| **Storage** | DuckDB (Parquet) | DuckDB + PostgreSQL | Same |
| **Serving** | Generated PDF/HTML report | React dashboard + WebSocket | + multi-venue aggregation |
| **Orchestration** | Makefile / manual | Dagster or Prefect | Same |
| **CI/CD** | GitHub Actions | GitHub Actions | Same |
| **Infra** | Local | Docker Compose → Fly.io / Railway | Same + Dubai Pulse cron |

---

## Privacy & Compliance (UAE PDPL)

### Data classification

| Data type | PDPL status | Handling |
|---|---|---|
| Ticket scans (named) | Personal data | Process under legitimate interest; anonymize in pipeline |
| Wi-Fi MAC addresses | Personal data | Hash + aggregate within Flink; never store raw MACs |
| POS transactions | Personal data if linked to identity | Aggregate to counts + amounts; no cardholder data |
| Parking counts | Not personal (aggregated) | No restrictions |
| RTA transit counts | Not personal (aggregated) | No restrictions |

### Design principles

1. **Aggregate before storage:** The Flink pipeline outputs zone-level counts,
   never individual-level records, to the serving layer.
2. **Raw retention window:** Raw events (with sensor_id) retained for 72 hours
   for debugging, then purged. Only aggregated data persists.
3. **Venue as controller:** The venue operator signs a data processing agreement.
   They own the data; we are the processor.

---

## Build Order

1. **Talk to the event contact** — get ticket scan CSVs from 2–3 past events
2. **Phase 1 batch analytics** — DuckDB, arrival curves, staffing mismatch
3. **Post-event report generator** — PDF/HTML output the contact can use
4. **Apply to Dubai Pulse** — submit data request, don't block on it
5. **Phase 2 streaming** — only when a venue offers live data feeds
6. **Phase 3 municipal** — only after Dubai Pulse access is granted

**Do not build Phase 2 infrastructure before Phase 1 proves value with real
data.** The streaming architecture is the easy part. Getting the data and
proving the staffing insight is the hard part.
