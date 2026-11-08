# AX-20 launch run: evidence and switch-on gate (TEMPLATE, not yet run)

Status: TEMPLATE. Nothing below has been run. Fill each line with `true`, `false` or `pending` and an evidence path.
An agent never deploys, commits or switches the flag on. The owner records the yes.

- Date of run: ____
- Frozen snapshot (`freeze.json` hash): ____
- App build: `VITE_ASSISTANT_ENABLED=true`, `VITE_DATA_BASE` = ____ , `VITE_ASSISTANT_WORKER_URL` = ____ (preview Worker, owner's deploy)
- Worker: preview environment, `DAILY_NEURON_CAP` = ____ (at most 10,000), per-visitor limit = ____
- Bar: AX-13 `_evidence/AX-13-2026-11-08/bar.json` after the ruling-1 amendment. Not changed for this run.

## Run steps

1. `python3 scripts/assistant_freeze.py --verify` exit code: ____ (evidence: ____)
2. Build into a scratch folder: `vite build --manifest --outDir <scratch>` (flag on). Evidence: ____
3. Browser check through the real drawer: `ASSISTANT_E2E_ENDPOINT=<worker chat url> E2E_BASE_URL=<preview> npx playwright test e2e/assistant-launch.e2e.ts` result: ____
4. AX-13's question set, 5 repeats each, driven through the real drawer (not the CLI). Results file: ____
5. `/admin/usage` before: ____ after: ____ (the owner supplies the admin token; it is never stored)
6. Switches: pause shows "answers are paused for today" ____ ; per-visitor limit ____ ; 409 after a deliberate catalogue mismatch ____ ; CSP report-only log has no unexpected violations ____
7. Flag-on perf: `node scripts/check_bundle_size.mjs --dist <scratch>` passes the split budget (AX-14 ruling 1: global limits for everything else, `maxAssistant*` limits for the lazy assistant chunks). Output: ____

## Bar result (scored against AX-13's recorded bar)

| Measure | Required | Measured | Pass |
| :-- | :-- | :-- | :-- |
| Numbers grounded | 100% | ____ | ____ |
| Refusals correct | 100% | ____ | ____ |
| Right tool | at least 95% of runs | ____ | ____ |
| Largest run | at most 18,000 tokens | ____ | ____ |
| Human read of 10 answers | passed | ____ | ____ |

Overall: PASS / FAIL. Failures listed: ____

Non-scored lines (AX-13 ruling 2), reported as measured, not part of the bar:

- Checker pass rate: ____
- `REPAIR_SKIPPED` rate: ____ (AX-13 ruling AX-10-1 revisit trigger: more than 5% reopens the 6th-round question)

## Cost

| Item | Value |
| :-- | :-- |
| Questions, rounds, neurons (from `/admin/usage` delta) | ____ |
| Neurons per answer | ____ |
| Answers per day on 10,000 neurons | ____ |
| HD6 estimate | 12-40 answers per day |
| Date measured | ____ |

## The owner's switch-on gate (all must be true)

| # | Gate | State | Evidence |
| :-- | :-- | :-- | :-- |
| 1 | AX-13's bar passed in this run: 100% numbers grounded, 100% refusals correct, right tool at least 95%, no run over 18,000 tokens, human read of 10 passed | pending | ____ |
| 2 | Freeze verified (`--verify` exit 0); HD5 branch recorded (A: transform-only, held classes refused; B: ML cards in) | pending | ____ |
| 3 | Worker: default `DAILY_NEURON_CAP` at most 10,000; per-visitor limit counted per question; pause switch tested; no key in the bundle (`scan-bundle` passed in CI on this build). Clears `AXW1` (`board.py --ship` exits 0) | pending | ____ |
| 4 | Turnstile works under the CSP (`HD11` applied). Separate owner decision: CSP from Report-Only to enforcing | pending | ____ |
| 5 | Capacity accepted: measured answers per day recorded and the owner accepts it (HD6) | pending | ____ |
| 6 | Held-class refusals read correctly to the owner (traffic cost, ML, pit verdict, AX-15a dirty-air-dependent stubs held under HD2 = C); no archived DA-03 number or chance-line number anywhere in the run | pending | ____ |
| 7 | Published data is the frozen snapshot, published to the CDN with its own owner yes | pending | ____ |
| 8 | The owner writes "switch on" in the log, then rebuilds with `VITE_ASSISTANT_ENABLED=true` and deploys (`make app-deploy` or the staged publish targets) | pending | ____ |

Owner's decision: ____ (date, initials)
