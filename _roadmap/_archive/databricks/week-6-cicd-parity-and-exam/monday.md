# Week 6 · Monday — Databricks Asset Bundles (DAB)

⏱️ **~2.5 hrs** · 70% learn / 30% lab · **Domain:** CI/CD (10%)
🎯 **One-liner:** learn DAB — the IaC + CI/CD primitive the 2025 exam expects — by bundling one job.

> ▶️ **Start here (first 15 min):** `databricks bundle init` from a template, then `databricks bundle
> validate`. Seeing a green validate on a scaffold is the fastest possible DAB win.

---

## 🎯 If you only do one thing today
Get a **single job** bundled and `bundle validate`-ing green. The concept (config-as-code with targets)
matters more than coverage today.

## Parts (tick as you go)

### ⬜ Part 1 — What DAB is & why · ~50 min  *(learn)*
- [ ] Docs: **"What are Databricks Asset Bundles?"**, **"Bundle configuration"**, **"Bundle deployment modes"**,
      **"Run a CI/CD workflow with a bundle"**.
- [ ] Notes: a `databricks.yml` packages notebooks/pipelines/jobs **as code**, with **targets**
      (dev/staging/prod) and per-target overrides. It replaced ad-hoc deploy scripts.

### ⬜ Part 2 — Bundle one job · ~40 min  *(lab)*
- [ ] In `resources/databricks.yml`, wrap **one** existing job. Run `bundle validate`, then `bundle deploy
      --target dev`, then `bundle run`.

### ⬜ Part 3 — Map it to what you've built · ~20 min  *(connect)*
- [ ] One line: how DAB targets correspond to your existing
      [`deploy.yml`](../../../.github/workflows/deploy.yml) promotion flow (smoke staging → promote → deploy → smoke prod).

## 🐍 You already know this
A bundle is **infrastructure-as-code** — the same idea as the Terraform you already wrote in `infra/`, but
for Databricks jobs/pipelines. `targets` are just environment configs (dev/staging/prod) with overrides.
If you've done `terraform apply` against workspaces, DAB will feel familiar fast.

## 📚 Resources (pick ONE)
- Academy → Data Engineering path → "Deploy with Databricks Asset Bundles" / DevOps module.

## 🏁 Done when
- [ ] One job bundled; `bundle validate` + `deploy --target dev` + `run` all succeed.
- [ ] You can explain DAB targets in terms of your existing GCP promotion flow.

## 🅿️ Park it
Tomorrow you expand to dev/staging/prod targets + wire CI. Note any per-target difference you'll need
(different catalogs, schedules, dev vs prod mode).

## Notes & gotchas
-
