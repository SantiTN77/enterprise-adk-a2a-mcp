resource "google_service_account" "orchestrator" {
  project      = var.project_id
  account_id   = "adk-orchestrator"
  display_name = "ADK Orchestrator Cloud Run Service Account"

  depends_on = [google_project_service.apis]
}

resource "google_service_account" "financial_agent" {
  project      = var.project_id
  account_id   = "adk-financial-agent"
  display_name = "ADK Financial Analysis Agent Cloud Run Service Account"

  depends_on = [google_project_service.apis]
}

resource "google_service_account" "compliance_agent" {
  project      = var.project_id
  account_id   = "adk-compliance-agent"
  display_name = "ADK Audit & Compliance Agent Cloud Run Service Account"

  depends_on = [google_project_service.apis]
}

resource "google_service_account" "vercel_bff" {
  project      = var.project_id
  account_id   = "vercel-bff-invoker"
  display_name = "Vercel Next.js BFF OIDC Invoker Service Account"

  depends_on = [google_project_service.apis]
}

# Project-level Vertex AI + Cloud Logging permissions for the 3 ADK agent SAs only
resource "google_project_iam_member" "orchestrator_aiplatform" {
  project = var.project_id
  role    = "roles/aiplatform.user"
  member  = "serviceAccount:${google_service_account.orchestrator.email}"
}

resource "google_project_iam_member" "orchestrator_logging" {
  project = var.project_id
  role    = "roles/logging.logWriter"
  member  = "serviceAccount:${google_service_account.orchestrator.email}"
}

resource "google_project_iam_member" "financial_aiplatform" {
  project = var.project_id
  role    = "roles/aiplatform.user"
  member  = "serviceAccount:${google_service_account.financial_agent.email}"
}

resource "google_project_iam_member" "financial_logging" {
  project = var.project_id
  role    = "roles/logging.logWriter"
  member  = "serviceAccount:${google_service_account.financial_agent.email}"
}

resource "google_project_iam_member" "compliance_aiplatform" {
  project = var.project_id
  role    = "roles/aiplatform.user"
  member  = "serviceAccount:${google_service_account.compliance_agent.email}"
}

resource "google_project_iam_member" "compliance_logging" {
  project = var.project_id
  role    = "roles/logging.logWriter"
  member  = "serviceAccount:${google_service_account.compliance_agent.email}"
}

# Scoped GCS bucket permissions
resource "google_storage_bucket_iam_member" "financial_bucket_viewer" {
  bucket = google_storage_bucket.docs.name
  role   = "roles/storage.objectViewer"
  member = "serviceAccount:${google_service_account.financial_agent.email}"
}

resource "google_storage_bucket_iam_member" "compliance_bucket_viewer" {
  bucket = google_storage_bucket.docs.name
  role   = "roles/storage.objectViewer"
  member = "serviceAccount:${google_service_account.compliance_agent.email}"
}

resource "google_storage_bucket_iam_member" "orchestrator_bucket_user" {
  bucket = google_storage_bucket.docs.name
  role   = "roles/storage.objectUser"
  member = "serviceAccount:${google_service_account.orchestrator.email}"
}

# Scoped Secret Manager permission: ONLY adk-compliance-agent may read compliance policy rules
resource "google_secret_manager_secret_iam_member" "compliance_secret_accessor" {
  project   = var.project_id
  secret_id = google_secret_manager_secret.compliance_policy_rules.secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.compliance_agent.email}"
}

# Strict private Cloud Run service-to-service IAM invoker bindings (ZERO allUsers)
resource "google_cloud_run_v2_service_iam_member" "vercel_bff_invoke_orchestrator" {
  project  = var.project_id
  location = google_cloud_run_v2_service.orchestrator.location
  name     = google_cloud_run_v2_service.orchestrator.name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.vercel_bff.email}"
}

resource "google_cloud_run_v2_service_iam_member" "orchestrator_invoke_financial" {
  project  = var.project_id
  location = google_cloud_run_v2_service.financial_agent.location
  name     = google_cloud_run_v2_service.financial_agent.name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.orchestrator.email}"
}

resource "google_cloud_run_v2_service_iam_member" "orchestrator_invoke_compliance" {
  project  = var.project_id
  location = google_cloud_run_v2_service.compliance_agent.location
  name     = google_cloud_run_v2_service.compliance_agent.name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.orchestrator.email}"
}
