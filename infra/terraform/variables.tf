variable "project_id" {
  description = "GCP project ID hosting Cloud Run, Vertex AI, GCS, and Secret Manager."
  type        = string
  default     = "gen-lang-client-0527325883"
}

variable "region" {
  description = "GCP region for Cloud Run, GCS bucket, and Artifact Registry."
  type        = string
  default     = "us-central1"
}

variable "vertex_ai_location" {
  description = "Vertex AI location for Gemini GA endpoints."
  type        = string
  default     = "global"
}

variable "gemini_model" {
  description = "Default Gemini model ID used by ADK agents."
  type        = string
  default     = "gemini-3.8-flash"
}

variable "artifact_registry_repo" {
  description = "Dedicated Artifact Registry Docker repository ID."
  type        = string
  default     = "enterprise-adk-a2a-mcp"
}

variable "bucket_name" {
  description = "GCS bucket name for synthetic sample documents and analysis reports."
  type        = string
  default     = "enterprise-adk-docs-gen-lang-client-0527325883"
}

variable "bucket_force_destroy" {
  description = "Allow destroying the GCS bucket even when objects remain."
  type        = bool
  default     = true
}

variable "compliance_secret_id" {
  description = "Secret Manager secret ID storing deterministic compliance policy rules."
  type        = string
  default     = "adk-compliance-policy-rules"
}

variable "financial_agent_image" {
  description = "Container image URI for adk-financial-agent."
  type        = string
  default     = "us-central1-docker.pkg.dev/gen-lang-client-0527325883/enterprise-adk-a2a-mcp/adk-financial-agent:latest"
}

variable "compliance_agent_image" {
  description = "Container image URI for adk-compliance-agent."
  type        = string
  default     = "us-central1-docker.pkg.dev/gen-lang-client-0527325883/enterprise-adk-a2a-mcp/adk-compliance-agent:latest"
}

variable "orchestrator_image" {
  description = "Container image URI for adk-orchestrator."
  type        = string
  default     = "us-central1-docker.pkg.dev/gen-lang-client-0527325883/enterprise-adk-a2a-mcp/adk-orchestrator:latest"
}
