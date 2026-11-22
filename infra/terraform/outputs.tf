output "orchestrator_url" {
  description = "Live Cloud Run v2 URI for adk-orchestrator."
  value       = google_cloud_run_v2_service.orchestrator.uri
}

output "financial_agent_url" {
  description = "Live Cloud Run v2 URI for adk-financial-agent."
  value       = google_cloud_run_v2_service.financial_agent.uri
}

output "compliance_agent_url" {
  description = "Live Cloud Run v2 URI for adk-compliance-agent."
  value       = google_cloud_run_v2_service.compliance_agent.uri
}

output "deterministic_urls" {
  description = "Deterministic project-number-based Cloud Run URLs used for OIDC audience alignment."
  value = {
    orchestrator     = "https://${local.orchestrator_host}"
    financial_agent  = "https://${local.financial_agent_host}"
    compliance_agent = "https://${local.compliance_agent_host}"
  }
}

output "gcs_bucket_name" {
  description = "GCS bucket storing sample documents and persisted analysis reports."
  value       = google_storage_bucket.docs.name
}

output "compliance_secret_id" {
  description = "Secret Manager secret ID for compliance policy rules."
  value       = google_secret_manager_secret.compliance_policy_rules.secret_id
}

output "artifact_registry_repository_url" {
  description = "Docker repository base path in Artifact Registry."
  value       = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.containers.repository_id}"
}

output "service_account_emails" {
  description = "Emails of the 4 least-privilege service accounts."
  value = {
    orchestrator     = google_service_account.orchestrator.email
    financial_agent  = google_service_account.financial_agent.email
    compliance_agent = google_service_account.compliance_agent.email
    vercel_bff       = google_service_account.vercel_bff.email
  }
}
