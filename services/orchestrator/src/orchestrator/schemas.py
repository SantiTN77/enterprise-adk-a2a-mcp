"""Pydantic request and response schemas for the ADK Enterprise Orchestrator."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

RiskRating = Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]


class ScenarioItem(BaseModel):
    """Metadata for a 1-click enterprise scenario backed by a synthetic GCS document."""

    id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    doc_id: str = Field(min_length=1)
    gcs_uri: str = Field(min_length=5)
    description: str = Field(min_length=1)
    default_prompt: str = Field(min_length=1)


class ScenariosResponse(BaseModel):
    """Catalog of enterprise scenarios returned by GET /api/scenarios."""

    scenarios: list[ScenarioItem]


class AnalyzeRequest(BaseModel):
    """Incoming request body for POST /api/analyze."""

    model_config = ConfigDict(extra="forbid")

    scenario_id: str = Field(min_length=1, max_length=128)
    doc_id: str | None = Field(default=None, max_length=256)
    prompt: str = Field(min_length=1, max_length=8000)
    document_text: str | None = Field(default=None, max_length=20_000)
    persist_report: bool = Field(default=True)

    @field_validator("scenario_id")
    @classmethod
    def validate_scenario_id(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("scenario_id cannot be empty.")
        return cleaned

    @field_validator("prompt")
    @classmethod
    def validate_prompt(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("prompt cannot be empty.")
        return cleaned

    @field_validator("doc_id")
    @classmethod
    def normalize_doc_id(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned if cleaned else None

    @field_validator("document_text")
    @classmethod
    def normalize_document_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned if cleaned else None

    @model_validator(mode="after")
    def require_doc_id_or_document_text(self) -> "AnalyzeRequest":
        if not self.doc_id and not self.document_text:
            if self.scenario_id in {
                "q3_cloud_vendor_review",
                "series_b_revenue_audit",
                "treasury_controls_memo",
            }:
                self.doc_id = f"samples/{self.scenario_id}.json"
            else:
                raise ValueError("Either doc_id or document_text must be provided.")
        return self


class FinancialAnalysisSection(BaseModel):
    """Structured financial analysis findings synthesized from financial_analysis_agent."""

    summary: str = Field(min_length=1)
    key_metrics: dict[str, Any] = Field(default_factory=dict)
    anomalies: list[Any] = Field(default_factory=list)
    sources: list[str] = Field(default_factory=list)


class ComplianceAuditSection(BaseModel):
    """Structured compliance and controls audit findings from audit_compliance_agent."""

    summary: str = Field(min_length=1)
    policy_id: str = Field(default="adk-compliance-policy-rules", min_length=1)
    controls_evaluated: list[Any] = Field(default_factory=list)
    violations: list[Any] = Field(default_factory=list)
    compliant: bool


class A2ATraceStep(BaseModel):
    """Single hop in the multi-agent A2A + MCP execution trace."""

    step: int = Field(ge=1)
    caller: str = Field(default="adk-orchestrator", min_length=1)
    target: str = Field(min_length=1)
    protocol: Literal["A2A"] = "A2A"
    auth: Literal["CloudRun-OIDC-IAM"] = "CloudRun-OIDC-IAM"
    mcp_tools: list[str] = Field(default_factory=list)
    latency_ms: float = Field(gt=0)
    status: str = Field(default="SUCCESS", min_length=1)


class GcpProvenance(BaseModel):
    """GCP service provenance metadata proving live Vertex AI, GCS, and Secret Manager integration."""

    vertex_ai_model: str = Field(default="gemini-3.8-flash", min_length=1)
    vertex_ai_location: Literal["global"] = "global"
    gcs_bucket: str = Field(min_length=1)
    report_gcs_uri: str | None = None
    secret_manager_policy: Literal["adk-compliance-policy-rules"] = "adk-compliance-policy-rules"


class SecurityPosture(BaseModel):
    """Runtime Cloud Run IAM and zero-idle scaling posture metadata."""

    cloud_run_iam: Literal["private-oidc-enforced"] = "private-oidc-enforced"
    min_instances: Literal[0] = 0
    max_instances: Literal[2] = 2


class OrchestratorSynthesisOutput(BaseModel):
    """Structured output schema produced by the Orchestrator ADK LlmAgent."""

    executive_summary: str = Field(
        description="Concise executive synthesis of financial analysis and compliance audit findings."
    )
    overall_risk_rating: RiskRating = Field(
        description="Overall enterprise risk rating: LOW, MEDIUM, HIGH, or CRITICAL."
    )
    recommendations: list[str] = Field(
        description="Actionable executive remediation recommendations grounded in agent findings."
    )


class AnalyzeResponse(BaseModel):
    """Full structured response returned by POST /api/analyze."""

    run_id: str
    timestamp_utc: str
    scenario_id: str
    doc_id: str
    executive_summary: str
    overall_risk_rating: RiskRating
    financial_analysis: FinancialAnalysisSection
    compliance_audit: ComplianceAuditSection
    recommendations: list[Any]
    a2a_trace: list[A2ATraceStep]
    gcp_provenance: GcpProvenance
    security_posture: SecurityPosture

    @field_validator("run_id")
    @classmethod
    def check_uuid(cls, value: str) -> str:
        uuid.UUID(value)
        return value

    @field_validator("timestamp_utc")
    @classmethod
    def check_timestamp(cls, value: str) -> str:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
        return value
