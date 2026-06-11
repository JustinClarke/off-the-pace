# The two values the CD workflows need as repo-level Actions variables identical to what
# scripts/setup_wif.sh prints (Settings → Secrets and variables → Actions → Variables).
output "workload_identity_provider" {
  description = "Set as repo Actions var GCP_WORKLOAD_IDENTITY_PROVIDER."
  value       = google_iam_workload_identity_pool_provider.github.name
}

output "deploy_service_account" {
  description = "Set as repo Actions var GCP_DEPLOY_SERVICE_ACCOUNT."
  value       = google_service_account.deploy.email
}

output "cdn_bucket_url" {
  description = "gs:// URL of the CDN bucket."
  value       = google_storage_bucket.cdn.url
}

output "budget_enabled" {
  description = "Whether the cost budget was created (false until billing_account is set)."
  value       = local.budget_enabled
}
