# APIs the deploy + CDN + WIF + budget depend on. Mirrors `gcloud services enable` in
# scripts/setup_wif.sh, plus the billing/monitoring APIs the budget needs. disable_on_destroy
# = false so a `terraform destroy` of this module never tears down APIs other things may use.
resource "google_project_service" "enabled" {
  for_each = toset([
    "iam.googleapis.com",
    "iamcredentials.googleapis.com",
    "sts.googleapis.com",
    "storage.googleapis.com",
    "firebase.googleapis.com",
    "firebasehosting.googleapis.com",
    "cloudresourcemanager.googleapis.com",
    "cloudbilling.googleapis.com",
    "billingbudgets.googleapis.com",
    "monitoring.googleapis.com",
  ])

  project            = var.project_id
  service            = each.value
  disable_on_destroy = false
}
