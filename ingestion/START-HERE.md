# Start here: getting all the F1 data

You need no accounts, passwords or keys. FastF1 and Jolpica are public.

## One-time setup

```bash
make setup            # builds the Python environment (.venv)
```

## Get everything (first time, takes many hours)

```bash
make ingest-full
```

This opens a live terminal view. It shows the phase, the season being pulled, how
many sessions have been written, rate-limit waits, the known gaps, and any problems.

- FastF1 allows 500 calls an hour, so the run waits between hours. Leave it running.
- **Ctrl+C stops it safely.** Run `make ingest-full` again to carry on. Finished
  sessions are skipped, so nothing is pulled twice.
- At the end it checks the data is complete, locks it (read-only, with a checksum
  manifest), and verifies the lock.

Preview what would happen without pulling anything:

```bash
make ingest-full DRY_RUN=1
```

## Keep it up to date

After each race weekend:

```bash
make ingest-update                 # the current season
make ingest-update SEASON=2025     # or a specific season
```

It only pulls rounds it doesn't already have, then locks and verifies again.

## Reading the result

- `make verify-bronze` re-checks completeness at any time.
- `make bronze-verify` checks the lock (nothing changed since it was written).
- Known gaps are listed in `ingestion/known_gaps.txt`, and each locked Bronze
  copies that list to `data/bronze/KNOWN_GAPS.txt`. These are sessions the source
  cannot deliver completely. The run records them and carries on.
- If the completeness check finds something new, the run stops before locking and
  says what is missing. Fix it, or add it to `known_gaps.txt` with a reason, then
  re-run `make ingest-full`.

## If something goes wrong

- **A session keeps failing:** check the log in `data/logs/`. If the source really
  cannot provide it, add it to `ingestion/known_gaps.txt` with a short reason.
- **"Rate limit" waits:** normal. The run resumes by itself.
- **Starting over:** not needed. Re-running resumes. Only delete `data/bronze` if you
  want a full rebuild, and then run `make ingest-full` again.

## Windows

Run these from WSL (Ubuntu). The lock step uses macOS file flags; elsewhere the
immutable flag is skipped and the checksum manifest still protects the data.
