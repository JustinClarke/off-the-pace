# Inputs. Defaults match the live project so a bare `terraform plan` (after import) is a
# no-op against the existing infra the scripts created. Override via terraform.tfvars.

variable "project_id" {
  description = "GCP project ID hosting the CDN bucket + Firebase site."
  type        = string
  default     = "off-the-pace"
}

variable "project_number" {
  description = "GCP project NUMBER (not the ID). Needed for the WIF principalSet and the budget filter. `gcloud projects describe <id> --format='value(projectNumber)'`."
  type        = string
}

variable "region" {
  description = "Default region for the providers (resource-specific locations override)."
  type        = string
  default     = "us-central1"
}

# ── CDN bucket (codifies the hand-created gs://off-the-pace-cdn + infra/cors.json + infra/gcs_lifecycle.json) ──

variable "cdn_bucket_name" {
  description = "Name of the public CDN bucket the app reads from (no gs:// prefix)."
  type        = string
  default     = "off-the-pace-cdn"
}

variable "bucket_location" {
  description = "Location of the CDN bucket. Multi-region US for a read-heavy public CDN. Immutable after create must match the existing bucket or the import/plan will want to replace it."
  type        = string
  default     = "US"
}

# ── Workload Identity Federation (codifies scripts/setup_wif.sh) ──

variable "github_repo" {
  description = "owner/name of the repo allowed to impersonate the deploy SA. The OIDC attribute-condition locks token exchange to this repo only."
  type        = string
  default     = "JustinClarke/off-the-pace"
}

variable "pool_id" {
  description = "Workload Identity Pool ID."
  type        = string
  default     = "github-pool"
}

variable "provider_id" {
  description = "Workload Identity Pool OIDC provider ID."
  type        = string
  default     = "github-provider"
}

variable "deploy_sa_name" {
  description = "Account ID (local part) of the keyless deploy service account."
  type        = string
  default     = "gh-deploy"
}

# ── Firebase Hosting (optional see firebase.tf) ──

variable "manage_firebase" {
  description = "Whether Terraform manages the Firebase project association + hosting site. Default off: the existing default site is CLI-managed and runtime config (headers/CSP/rewrites) lives in firebase.json. Enable only after importing the existing site (README → Firebase)."
  type        = bool
  default     = false
}

variable "firebase_site_id" {
  description = "Firebase Hosting site ID (the default site is usually the project ID)."
  type        = string
  default     = "off-the-pace"
}

# ── Cost monitoring ──

variable "billing_account" {
  description = "Billing account ID (XXXXXX-XXXXXX-XXXXXX) the budget is created under. Empty disables the budget + its alert channels (so `validate`/`plan` work without billing access)."
  type        = string
  default     = ""
}

variable "budget_amount_usd" {
  description = "Monthly budget threshold (USD) for the CDN's storage + egress. Tune from the actual bill; alerts fire at 50/90/100% actual + 100% forecast."
  type        = number
  default     = 50
}

variable "budget_alert_emails" {
  description = "Email addresses to notify on budget threshold breach (in addition to the project's billing admins)."
  type        = list(string)
  default     = []
}

variable "budget_filter_services" {
  description = "Cloud Billing service IDs the budget is scoped to. Default = Cloud Storage (covers bucket storage + egress SKUs). Empty list = project-wide. Look up with the Cloud Billing Catalog API / `gcloud billing accounts list`."
  type        = list(string)
  default     = ["services/95FF-2EF5-5EA1"] # Cloud Storage
}
