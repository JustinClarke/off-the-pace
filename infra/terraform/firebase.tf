# Firebase Hosting OPTIONAL (var.manage_firebase, default off).
#
# Deliberate split of ownership:
#   • Terraform owns the *existence* of the Firebase project association + the hosting site.
#   • The runtime hosting config headers, CSP, cache-control, rewrites stays in
#     firebase.json, deployed by the firebase CLI in deploy.yml, because it is coupled to the
#     built bundle (app/dist) and changes per release. Two sources of truth for headers would
#     fight each other, so Terraform intentionally does NOT manage google_firebase_hosting_version.
#
# The default site already exists (CLI-created). Enabling this requires importing it first
# (README → Firebase); left off by default so a first `apply` can't disrupt live hosting.

resource "google_firebase_project" "default" {
  count    = var.manage_firebase ? 1 : 0
  provider = google-beta
  project  = var.project_id

  depends_on = [google_project_service.enabled]
}

resource "google_firebase_hosting_site" "app" {
  count    = var.manage_firebase ? 1 : 0
  provider = google-beta
  project  = var.project_id
  site_id  = var.firebase_site_id

  depends_on = [google_firebase_project.default]
}
