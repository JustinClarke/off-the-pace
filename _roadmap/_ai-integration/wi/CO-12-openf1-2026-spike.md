# CO-12 — OpenF1 2026 ingest spike

**Status:** SPEC (nothing run). **Group:** D carry-over · **Depends on:** none · **Blocker:** owner approval to start.

**Sources:** `ingestion/`.

## Why

FastF1's archive returns 401 for 2026, so 2026 data can't come through it from this machine. OpenF1 serves 2026 stints, pit stops, race control and laps. Without 2026 data there is no clean test (`CO-10`).

## Method

1. Fix the 2026 calendar from one source before ingesting. FastF1 and OpenF1 disagree (for example 2026-10-04: Bahrain vs Kuala Lumpur).
2. Ingest 2026 stints, pit stops (including time stationary), race control and laps into the bronze layer. Ingest only.
3. Record coverage per race: laps, stints, pit stops, race control.
4. Do not fit, score or build marts on the new data in this item.

## Definition of done

Coverage table per 2026 race; calendar source recorded; ingestion tests pass with counts reported; nothing scored.
