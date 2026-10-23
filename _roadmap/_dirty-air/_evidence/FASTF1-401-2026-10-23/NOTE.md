# FastF1 vs livetiming 401 (2026-10-23)

Verdict: **not fixed by any release version tested** (3.8.3, which is also the latest stable). A 3.9.0a0 pre-release adds F1-account authentication for livetiming, so the fix exists only as a pre-release and needs an F1 account (F1_USERNAME/F1_PASSWORD) that was not available here. The account path was NOT tested, so "fixed by 3.9.0a0 with credentials" is unverified.

Scratch: /private/tmp/claude-501/-Users-justin-github-off-the-pace/1fdfffb0-6280-4ac0-900e-471f09f2c9ba/scratchpad/fastf1-env/ (venvs v383, vlatest, vpre; try.py; own FastF1 caches). No repo file changed; ingestion/requirements.txt untouched.

## Installs
- System python3 is 3.9.6: `pip install fastf1==3.8.3` fails ("No matching distribution"), since 3.8.0 dropped Python 3.9 (requires >=3.10).
- Used `uv venv -p 3.12`. PyPI: latest stable is 3.8.3 (2026-04-29); only newer is 3.9.0a0 (2026-10-18, pre-release).
- v383: fastf1 3.8.3. vlatest (`pip install fastf1`): resolves to 3.8.3, same as v383. vpre (`--pre fastf1==3.9.0a0`): 3.9.0a0.

## Session load: 2018 Abu Dhabi race (get_session(2018,'Abu Dhabi','R').load(laps=True, ...))
- 3.8.3: "Failed to load session info data!", then status, lap count, track status and timing all "Failed to load ...". load() ends with only Ergast/Jolpica driver info; `session.laps` raises `DataNotLoadedError`. Position data not reachable (same failures with telemetry=True; session_info never loads).
- 3.9.0a0: same failures, plus "Failed to authenticate with Formula 1 account, continuing without authentication: No F1 account credentials available. Set the environment variables F1_USERNAME and F1_PASSWORD." Same DataNotLoadedError.

## Changelog
- GitHub release v3.9.0-a0 (2026-10-18, prerelease): "adds support for now required authentication on F1 livetiming archive endpoints", "adds support for new oauth based authentication method in addition to browser based login flow".
- 3.9.0a0 source (fastf1/internals/f1account/__init__.py): "sends the F1TV subscription token as Bearer token to livetiming"; credentials read from F1_USERNAME / F1_PASSWORD.
- 3.8.0 to 3.8.3 notes: nothing on livetiming access, auth, headers or endpoints (3.8.0 drops Python 3.9; 3.8.1 pre-season testing; 3.8.2/3.8.3 bug fixes).
- 3.9.0 "in development" changelog (docs/changelog/current.rst) does not mention auth yet; only the release text does.

## Headers vs access (curl, URL .../2018/2018-11-25_Abu_Dhabi_Grand_Prix/2018-11-25_Race/)
FastF1 3.8.3 sends: Connection: close, TE: identity, User-Agent: BestHTTP, Accept-Encoding: gzip, identity (fastf1/_api.py). It falls back on status >=400 to https://livetiming-mirror.fastf1.dev.
- SessionInfo.json, no special headers: 401
- SessionInfo.json, FastF1-style headers: 401
- SessionInfo.jsonStream (the page FastF1 requests), FastF1 headers: 401
- SessionInfo.json, browser UA: 401
- /static/2018/Index.json and /static/2025/Index.json with UA BestHTTP: 401
- with a bogus `Authorization: Bearer x`: 401
- Response: HTTP/2 401, empty body, `server: CloudFront`, `x-cache: FunctionGeneratedResponse from cloudfront` (a CloudFront function rejects it). Cause is access, not headers.
- Mirror livetiming-mirror.fastf1.dev SessionInfo.json and .jsonStream for this session: 404 (no fallback data).
- Control: api.jolpi.ca/ergast/f1/2018/24/results.json: 200.

## MultiViewer circuit API (read only)
- Working pattern: `GET https://api.multiviewer.app/api/v1/circuits/{circuit_key}/{year}` with the numeric F1 circuit key (what FastF1 uses). Index: `/api/v1/circuits` (200, dict keyed by circuit key, with `years`).
- `/circuits/70/2018` (Yas Marina): 200, year 2018, 21 corners, 20 marshalSectors (each has number, trackPosition x/y, angle, length), 20 marshalLights.
- `/circuits/22/2018` (Monaco): 200 but payload `year` = 2019 (falls back to another year; matches DA-01 caveat).
- A name slug (`/circuits/abu-dhabi/2018`): 400 "Invalid circuit_key". Unknown number (9999): 404 "Circuit not found". So the earlier 404 came from a wrong or unknown key, not a dead API. The circuit key normally comes from session_info (Meeting.Circuit.Key), which is unreachable while livetiming 401s; take it from the `/circuits` index instead (ask by name/country).
- DA-01 already recorded marshal sectors for 58 of 59 races 2018-2020.

## Unverified
- 3.9.0a0 with real F1 account credentials (needs an F1TV subscription token; not tested, no credentials, not asked).
- Whether non-session endpoints for pre-cached data exist elsewhere.
- Behaviour from another network (only this machine's CloudFront PoP DXB53 tested).
