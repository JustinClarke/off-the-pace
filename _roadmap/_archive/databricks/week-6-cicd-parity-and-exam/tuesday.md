# Week 6 · Tuesday — Targets + CI deploy

⏱️ **~3 hrs** · 90% build · **Build day** 🔨
🎯 **One-liner:** bundle the real Week-4 pipeline + job across dev/staging/prod, and deploy from CI.

> ▶️ **Start here (first 15 min):** add a `staging` target to yesterday's `databricks.yml` and
> `bundle deploy --target staging`. One more target than yesterday — small step, real progress.

---

## 🎯 If you only do one thing today
Get the **pipeline + job bundled with dev/staging/prod targets** and deploying. CI automation is the bonus;
the bundle-with-targets is the must.

## Parts (tick as you go)

### ⬜ Part 1 — Bundle the real workload · ~1.25 hrs  *(build)*
- [ ] In `resources/databricks.yml`, bundle the **Week-4 pipeline + 7-stage job**.
- [ ] Define `dev`, `staging`, `prod` targets: different catalogs/schedules; **dev = development mode,
      prod = production mode**.

### ⬜ Part 2 — CI deploy · ~1 hr  *(build)*
- [ ] Add a GitHub Actions workflow to `off-the-pace-spark`: `databricks bundle deploy --target staging` on
      push to `main`, plus a **gated** `--target prod`.
- [ ] You don't need full keyless OIDC for the cert — but note where it'd plug in (you've done the GCP/WIF equivalent).

### ⬜ Part 3 — Document the promotion map · ~30 min  *(production engineering)*
- [ ] In the repo README: how WIF/Firebase ↔ DAB targets correspond conceptually. This is the "I migrated a
      production-style deploy flow" story for interviews.

## 🐍 You already know this
You've already built this exact promotion flow once — in GitHub Actions for GCP
([`deploy.yml`](../../../.github/workflows/deploy.yml), [`setup_wif.sh`](../../../scripts/setup_wif.sh)).
You're **porting an orchestration you designed**, not learning CD from zero. Same staging→prod discipline, new tool.

## 🏁 Done when
- [ ] Pipeline + job bundled across dev/staging/prod; `deploy --target staging` works from CI.
- [ ] Prod deploy is gated (not from a notebook).

## 🅿️ Park it
Tomorrow is the project's actual finish line: the **full 60-model parity cutover**. Make sure the
full-corpus build can run end-to-end (the one big batch Free Edition can do).

## Notes & gotchas
-
