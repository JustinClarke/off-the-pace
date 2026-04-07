# Workload Identity Federation so GitHub Actions deploys with NO long-lived key.
# Codifies scripts/setup_wif.sh 1:1. The outputs (outputs.tf) are the two repo Actions
# variables the deploy/preview/pipeline workflows consume.

resource "google_iam_workload_identity_pool" "github" {
  project                   = var.project_id
  workload_identity_pool_id = var.pool_id
  display_name              = "GitHub Actions pool"

  depends_on = [google_project_service.enabled]
}

# OIDC provider locked to this repo. The attribute-condition restricts token exchange to
# var.github_repo without it ANY GitHub repo could impersonate the deploy SA.
resource "google_iam_workload_identity_pool_provider" "github" {
  project                            = var.project_id
  workload_identity_pool_id          = google_iam_workload_identity_pool.github.workload_identity_pool_id
  workload_identity_pool_provider_id = var.provider_id
  display_name                       = "GitHub OIDC"

  attribute_mapping = {
    "google.subject"             = "assertion.sub"
    "attribute.repository"       = "assertion.repository"
    "attribute.repository_owner" = "assertion.repository_owner"
  }
  attribute_condition = "assertion.repository == '${var.github_repo}'"

  oidc {
    issuer_uri = "https://token.actions.githubusercontent.com"
  }
}

# Keyless deploy service account least privilege (see the IAM bindings below).
resource "google_service_account" "deploy" {
  project      = var.project_id
  account_id   = var.deploy_sa_name
  display_name = "GitHub Actions deploy (WIF, no keys)"

  depends_on = [google_project_service.enabled]
}

# Bucket: object admin scoped to the CDN bucket ONLY (not project-wide storage admin).
resource "google_storage_bucket_iam_member" "deploy_object_admin" {
  bucket = google_storage_bucket.cdn.name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${google_service_account.deploy.email}"
}

# Firebase Hosting deploy.
resource "google_project_iam_member" "deploy_firebase" {
  project = var.project_id
  role    = "roles/firebasehosting.admin"
  member  = "serviceAccount:${google_service_account.deploy.email}"
}

# The API-enablement check the firebase CLI performs at deploy time.
resource "google_project_iam_member" "deploy_serviceusage" {
  project = var.project_id
  role    = "roles/serviceusage.serviceUsageConsumer"
  member  = "serviceAccount:${google_service_account.deploy.email}"
}

# Let this repo and only this repo impersonate the deploy SA via the pool.
resource "google_service_account_iam_member" "deploy_wif_user" {
  service_account_id = google_service_account.deploy.name
  role               = "roles/iam.workloadIdentityUser"
  member             = "principalSet://iam.googleapis.com/projects/${var.project_number}/locations/global/workloadIdentityPools/${google_iam_workload_identity_pool.github.workload_identity_pool_id}/attribute.repository/${var.github_repo}"
}
