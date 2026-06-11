# The public CDN bucket the live app fetches all data/models from (DATA_CDN_BASE).
# Codifies the hand-created gs://off-the-pace-cdn together with the previously hand-applied
# infra/cors.json (CORS) and infra/gcs_lifecycle.json (versioning + lifecycle GC). Terraform is now
# the source of truth for these three; the scripts remain the no-Terraform interim.
resource "google_storage_bucket" "cdn" {
  name     = var.cdn_bucket_name
  project  = var.project_id
  location = var.bucket_location

  storage_class               = "STANDARD"
  uniform_bucket_level_access = true
  # Public reads require IAM (allUsers) keep prevention "inherited", not "enforced".
  public_access_prevention = "inherited"

  # Durable rollback + the noncurrent-version lifecycle rule depend on this.
  versioning {
    enabled = true
  }

  # Mirrors infra/cors.json the app fetches cross-origin parquet/ONNX from any origin.
  cors {
    origin          = ["*"]
    method          = ["GET", "HEAD"]
    response_header = ["Content-Type", "Access-Control-Allow-Origin", "Cross-Origin-Resource-Policy"]
    max_age_seconds = 3600
  }

  # ── Lifecycle GC mirrors infra/gcs_lifecycle.json ────────────────────────────
  # The no-delete publish + in-place overwrite would accrete storage forever.

  # Expire superseded versions 30d after they're replaced, but keep the 3 newest so a
  # recent rollback can still restore real parquet bytes (.github/DEPLOYMENT.md → Rollback).
  lifecycle_rule {
    action {
      type = "Delete"
    }
    condition {
      days_since_noncurrent_time = 30
      num_newer_versions         = 3
    }
  }

  # Staging is rebuilt every release reap it 14d after last update.
  lifecycle_rule {
    action {
      type = "Delete"
    }
    condition {
      age            = 14
      matches_prefix = ["staging/"]
    }
  }

  # Rollback pointers keep 180d, far longer than any realistic rollback window.
  lifecycle_rule {
    action {
      type = "Delete"
    }
    condition {
      age            = 180
      matches_prefix = ["data/manifest-archive/"]
    }
  }

  depends_on = [google_project_service.enabled]
}

# Public read of objects the CDN serves the app's data/models to any browser.
resource "google_storage_bucket_iam_member" "public_read" {
  bucket = google_storage_bucket.cdn.name
  role   = "roles/storage.objectViewer"
  member = "allUsers"
}
