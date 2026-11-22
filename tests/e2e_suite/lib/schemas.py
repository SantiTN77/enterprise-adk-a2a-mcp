from __future__ import annotations

import re
import uuid
from datetime import datetime
from typing import Any, Literal
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

RETIRED_GEMINI_PREFIXES = ("gemini-2.0", "gemini-2.5", "gemini-1.")
ALLOWED_GEMINI_PREFIXES = ("gemini-3.8-flash", "gemini-3.5-flash-lite", "gemini-3.")

SECRET_LEAK_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("pem_private_key", re.compile(r"-----BEGIN\s+(?:RSA\s+|EC\s+|OPENSSH\s+)?PRIVATE\s+KEY-----")),
    ("service_account_json", re.compile(r'"type"\s*:\s*"service_account"')),
    ("gcp_private_key_env", re.compile(r"\bGCP_PRIVATE_KEY\b\s*[:=]")),
    ("next_public_gcp", re.compile(r"\bNEXT_PUBLIC_[A-Z0-9_]*(?:GCP|PRIVATE|SECRET|TOKEN|KEY)\b")),
    ("raw_bearer_jwt", re.compile(r"Authorization\s*:\s*Bearer\s+eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+")),
    ("python_traceback", re.compile(r"Traceback \(most recent call last\):")),
)


def find_secret_leaks(payload_text: str) -> list[str]:
    hits: list[str] = []
    for label, pattern in SECRET_LEAK_PATTERNS:
        if pattern.search(payload_text):
            hits.append(label)
    return hits


def assert_no_leaked_secrets(payload_text: str, *, context: str = "response") -> None:
    hits = find_secret_leaks(payload_text)
    if hits:
        raise AssertionError(f"Sensitive material or stack trace leaked in {context}: {hits}")


class AgentHealthzResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    status: Literal["ok"]
    agent: Literal["financial_analysis_agent", "audit_compliance_agent"]
    mcp_tools: list[str] = Field(min_length=1)


class AgentCardInterface(BaseModel):
    model_config = ConfigDict(extra="allow")

    url: str = Field(min_length=1)
    protocolBinding: str = Field(min_length=1)
    protocolVersion: str = Field(min_length=1)


class AgentCardSkill(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    description: str = Field(min_length=1)


class AgentCard(BaseModel):
    model_config = ConfigDict(extra="allow")

    name: str = Field(min_length=1)
    description: str = Field(min_length=1)
    version: str = Field(min_length=1)
    capabilities: dict[str, Any]
    defaultInputModes: list[str] = Field(min_length=1)
    defaultOutputModes: list[str] = Field(min_length=1)
    skills: list[AgentCardSkill] = Field(min_length=1)
    supportedInterfaces: list[AgentCardInterface] = Field(min_length=1)


def validate_agent_card_url(card: AgentCard, expected_base_url: str) -> None:
    """Validate AgentCard interface URL against expected base URL.

    Probe on google-adk==2.15.0 produces `https://<host>:443` when port=443,
    while PROJECT.md specifies `PUBLIC_PROTOCOL://PUBLIC_HOST(:PUBLIC_PORT)`.
    Accept both `https://<host>` and `https://<host>:443` (and `http://<host>:<port>` locally).
    """
    advertised = card.supportedInterfaces[0].url.rstrip("/")
    parsed_expected = urlparse(expected_base_url)
    parsed_adv = urlparse(advertised)

    if parsed_expected.scheme == "https":
        assert parsed_adv.scheme == "https", f"Expected https:// AgentCard URL, got {advertised!r}"
        assert parsed_adv.hostname == parsed_expected.hostname, (
            f"AgentCard host mismatch: expected {parsed_expected.hostname!r}, got {parsed_adv.hostname!r}"
        )
        assert parsed_adv.port in (None, 443), f"Unexpected https AgentCard port in {advertised!r}"
        for forbidden in ("localhost", "127.0.0.1", "0.0.0.0", ":8080"):
            assert forbidden not in advertised, f"Forbidden internal host/port {forbidden!r} in {advertised!r}"
    else:
        assert advertised == expected_base_url, f"Expected {expected_base_url!r}, got {advertised!r}"


class OrchestratorHealthzResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    status: Literal["ok"]
    service: Literal["adk-orchestrator"]
    agents: dict[str, str]

    @field_validator("agents")
    @classmethod
    def check_agents(cls, value: dict[str, str]) -> dict[str, str]:
        if "financial" not in value or "compliance" not in value:
            raise ValueError("Orchestrator /healthz 'agents' must include 'financial' and 'compliance'.")
        for key in ("financial", "compliance"):
            if not value[key].startswith(("https://", "http://")):
                raise ValueError(f"Agent URL for {key!r} must be a valid URL, got {value[key]!r}")
        return value


class ScenarioItem(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    doc_id: str = Field(min_length=1)
    gcs_uri: str = Field(min_length=5)
    description: str = Field(min_length=1)
    default_prompt: str = Field(min_length=1)

    @field_validator("gcs_uri")
    @classmethod
    def check_gcs_uri(cls, value: str) -> str:
        if not value.startswith("gs://"):
            raise ValueError(f"gcs_uri must start with 'gs://', got {value!r}")
        return value


class ScenariosResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    scenarios: list[ScenarioItem] = Field(min_length=1)


class FinancialAnalysis(BaseModel):
    model_config = ConfigDict(extra="allow")

    summary: str = Field(min_length=1)
    key_metrics: dict[str, Any]
    anomalies: list[Any]
    sources: list[str]


class ComplianceAudit(BaseModel):
    model_config = ConfigDict(extra="allow")

    summary: str = Field(min_length=1)
    policy_id: str = Field(min_length=1)
    controls_evaluated: list[Any]
    violations: list[Any]
    compliant: bool


class A2ATraceStep(BaseModel):
    model_config = ConfigDict(extra="allow")

    step: int = Field(ge=1)
    caller: str = Field(min_length=1)
    target: str = Field(min_length=1)
    protocol: Literal["A2A"]
    auth: Literal["CloudRun-OIDC-IAM"]
    mcp_tools: list[str]
    latency_ms: float = Field(ge=0)
    status: str = Field(min_length=1)


class GCPProvenance(BaseModel):
    model_config = ConfigDict(extra="allow")

    vertex_ai_model: str = Field(min_length=1)
    vertex_ai_location: Literal["global"]
    gcs_bucket: str = Field(min_length=1)
    report_gcs_uri: str | None = None
    secret_manager_policy: Literal["adk-compliance-policy-rules"]

    @field_validator("vertex_ai_model")
    @classmethod
    def check_gemini_model(cls, value: str) -> str:
        lower = value.lower()
        for retired in RETIRED_GEMINI_PREFIXES:
            if lower.startswith(retired):
                raise ValueError(f"Retired Gemini model forbidden: {value!r}")
        if not any(lower.startswith(prefix) for prefix in ALLOWED_GEMINI_PREFIXES):
            raise ValueError(f"Unexpected Vertex AI model {value!r}; expected gemini-3.8-flash or gemini-3.x")
        return value


class SecurityPosture(BaseModel):
    model_config = ConfigDict(extra="allow")

    cloud_run_iam: Literal["private-oidc-enforced"]
    min_instances: Literal[0]
    max_instances: Literal[2]


class AnalyzeResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    run_id: str
    timestamp_utc: str
    scenario_id: str = Field(min_length=1)
    doc_id: str = Field(min_length=1)
    executive_summary: str = Field(min_length=1)
    overall_risk_rating: Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]
    financial_analysis: FinancialAnalysis
    compliance_audit: ComplianceAudit
    recommendations: list[Any]
    a2a_trace: list[A2ATraceStep] = Field(min_length=1)
    gcp_provenance: GCPProvenance
    security_posture: SecurityPosture

    @field_validator("run_id")
    @classmethod
    def check_run_id_uuid(cls, value: str) -> str:
        uuid.UUID(value)
        return value

    @field_validator("timestamp_utc")
    @classmethod
    def check_timestamp_iso(cls, value: str) -> str:
        normalized = value.replace("Z", "+00:00")
        datetime.fromisoformat(normalized)
        return value

    @model_validator(mode="after")
    def check_dual_agent_trace(self) -> "AnalyzeResponse":
        targets = {step.target.lower() for step in self.a2a_trace}
        has_fin = any("financial" in t for t in targets)
        has_comp = any("compliance" in t for t in targets)
        if not (has_fin and has_comp):
            raise ValueError(
                f"a2a_trace must include both financial and compliance agent delegations, got {sorted(targets)}"
            )
        return self
