# Infrastructure as Code (Terraform)

Implements **Phase 6 (IaC & cost, F10)** of [`SYSTEM_DESIGN_AUDIT.md`](../../SYSTEM_DESIGN_AUDIT.md).
Turns the imperative provisioning scripts into a single reviewable, reproducible Terraform module,
and adds the cost-monitoring half of the phase.

## What this codifies

| Resource | Was (imperative) | Terraform |
|---|---|---|
| CDN bucket `gs://off-the-pace-cdn` | manual `gcloud storage buckets create` | [`bucket.tf`](bucket.tf) |
| Bucket **CORS** | hand-applied [`cors.json`](../cors.json) | `cors {}` in `bucket.tf` |
| Bucket **versioning + lifecycle GC** | [`gcs_lifecycle.json`](../gcs_lifecycle.json) via `apply_bucket_lifecycle.sh` | `lifecycle_rule {}` in `bucket.tf` |
| Public read (`allUsers`) | manual IAM | `bucket.tf` |
| **WIF** pool + OIDC provider + deploy SA + bindings | [`scripts/setup_wif.sh`](../../scripts/setup_wif.sh) | [`wif.tf`](wif.tf) |
| Enabled APIs | `gcloud services enable` | [`services.tf`](services.tf) |
| Firebase project + hosting site | firebase CLI | [`firebase.tf`](firebase.tf) **optional**, default off |
| **Cost budget** + email alerts | _did not exist_ | [`budget.tf`](budget.tf) |

Terraform is now the **source of truth** for the bucket, CORS, lifecycle, and WIF. The scripts
(`setup_wif.sh`, `apply_bucket_lifecycle.sh`, `infra/cors.json`, `gcs_lifecycle.json`) remain as the
no-Terraform interim / disaster-recovery path keep them in sync if you change the `.tf`.

### Deliberate ownership split

The Firebase **runtime config** headers, CSP, cache-control, rewrites stays in
[`firebase.json`](../../firebase.json), deployed by the firebase CLI in `deploy.yml`, because it is
coupled to the built bundle and changes per release. Terraform owns only the *existence* of the
Firebase site, not `google_firebase_hosting_version`, so the two never fight over headers. That's
why `manage_firebase` defaults to `false`.

## Prerequisites

- `terraform >= 1.5`
- A project **owner** (or equivalent) authenticated for Application Default Credentials:
  `gcloud auth application-default login`
- A GCS **state bucket** (create once; it is itself infra and not managed here):
  ```bash
  gcloud storage buckets create gs://off-the-pace-tfstate \
    --project off-the-pace --location US --uniform-bucket-level-access
  gcloud storage buckets update gs://off-the-pace-tfstate --versioning
  ```

## First-time setup (existing project)

The bucket, WIF, and SA **already exist** (the scripts created them). Adopt them into state before
the first apply, or Terraform will try to re-create them and fail.

```bash
cp terraform.tfvars.example terraform.tfvars   # set project_number (required)

make tf-init        # terraform init with the state backend (see below)
make tf-import      # bash import.sh pull existing resources into state
make tf-plan        # expect a near no-op; any *changes* are real script↔TF drift review them
make tf-apply       # reconcile
```

`tf-init` passes the backend config:

```bash
terraform -chdir=infra/terraform init \
  -backend-config="bucket=off-the-pace-tfstate" \
  -backend-config="prefix=infra"
```

After the first successful init, commit a multi-platform provider lock so CI is reproducible:

```bash
terraform -chdir=infra/terraform providers lock \
  -platform=linux_amd64 -platform=darwin_arm64
git add -f infra/terraform/.terraform.lock.hcl
```

## Greenfield setup (new project)

No import step `make tf-init && make tf-apply` creates everything. Then set the two repo Actions
variables from the outputs (these replace running `setup_wif.sh`):

```bash
terraform -chdir=infra/terraform output workload_identity_provider  # → GCP_WORKLOAD_IDENTITY_PROVIDER
terraform -chdir=infra/terraform output deploy_service_account      # → GCP_DEPLOY_SERVICE_ACCOUNT
```

## Cost monitoring

The budget + alert channels are gated on `billing_account` leave it empty and they're skipped
(so `plan`/`validate` work without billing access). To enable:

```hcl
# terraform.tfvars
billing_account     = "XXXXXX-XXXXXX-XXXXXX"   # gcloud billing accounts list
budget_amount_usd   = 50
budget_alert_emails = ["justinclarke241@gmail.com"]
```

Scoped to the Cloud Storage service (storage + egress SKUs) via `budget_filter_services`; set it to
`[]` for a project-wide budget. Alerts fire at 50/90/100% of actual spend and 100% of *forecast*.
This is the cost analogue of the SLO alerting in [`.github/OBSERVABILITY.md`](../../.github/OBSERVABILITY.md).

## Firebase (optional)

To bring hosting under Terraform, import the existing site first, then flip the flag:

```bash
terraform -chdir=infra/terraform import \
  'google_firebase_project.default[0]' off-the-pace
terraform -chdir=infra/terraform import \
  'google_firebase_hosting_site.app[0]' projects/off-the-pace/sites/off-the-pace
# then set manage_firebase = true and apply
```

## Local checks (no cloud creds)

```bash
make tf-validate    # terraform fmt -check -recursive + terraform validate
```

`validate` runs against `init -backend=false`, so it needs no credentials and no state it's the
gate to run before every change. **Operator-gated:** `apply` needs a project owner; this repo ships
the config, not the credentials.
