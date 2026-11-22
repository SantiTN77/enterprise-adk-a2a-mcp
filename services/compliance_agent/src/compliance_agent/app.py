"""FastAPI + ADK + A2A application entrypoint for the Audit & Compliance Agent."""

from __future__ import annotations

import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from google.adk.a2a.utils.agent_to_a2a import to_a2a
from google.adk.agents import LlmAgent
from google.adk.tools.mcp_tool import McpToolset, StdioConnectionParams
from mcp import StdioServerParameters
from pydantic import BaseModel, Field

COMPLIANCE_AGENT_NAME = "audit_compliance_agent"
COMPLIANCE_MCP_TOOLS = [
    "fetch_compliance_policy",
    "read_audit_evidence",
    "evaluate_control_matrix",
]


class ControlEvaluationResult(BaseModel):
    """Typed evaluation record for a single compliance control."""

    control_id: str
    name: str
    framework: str
    severity: str
    status: str
    observed_summary: str = Field(description="Concise summary of observed evidence.")
    expected_or_threshold: str
    rationale: str


class ComplianceAuditOutput(BaseModel):
    """Structured JSON output schema enforced for the audit & compliance agent."""

    summary: str = Field(description="Executive compliance assessment summary.")
    doc_id: str = Field(description="Primary evaluated GCS evidence document identifier.")
    policy_id: str = Field(description="Compliance policy identifier evaluated.")
    compliant: bool = Field(description="True only when zero controls fail.")
    findings: list[str] = Field(description="Key compliance findings grounded in tool outputs.")
    control_results: list[ControlEvaluationResult] = Field(
        description="Deterministic control evaluation outcomes."
    )
    violations: list[ControlEvaluationResult] = Field(
        description="Subset of controls that failed compliance checks."
    )
    mcp_tools_called: list[str] = Field(description="Exact MCP tool names invoked.")
    gcs_sources: list[str] = Field(description="Exact gs:// URIs read during audit.")
    secret_policies_checked: list[str] = Field(
        description="Secret Manager policy resource names or IDs checked."
    )


def _mcp_child_env() -> dict[str, str]:
    src_dir = str(Path(__file__).resolve().parents[1])
    env = os.environ.copy()
    existing = env.get("PYTHONPATH", "")
    parts = [part for part in existing.split(os.pathsep) if part]
    if src_dir not in parts:
        env["PYTHONPATH"] = os.pathsep.join([src_dir, *parts])
    return env


def create_app(
    *,
    public_host: str | None = None,
    public_port: int | None = None,
    public_protocol: str | None = None,
    model_name: str | None = None,
) -> FastAPI:
    """Create the FastAPI application exposing the Audit & Compliance A2A agent."""
    resolved_host = public_host or os.environ.get("PUBLIC_HOST", "localhost")
    resolved_port = public_port if public_port is not None else int(os.environ.get("PUBLIC_PORT", "8002"))
    resolved_protocol = public_protocol or os.environ.get("PUBLIC_PROTOCOL", "http")
    resolved_model = model_name or os.environ.get("GEMINI_MODEL", "gemini-3.8-flash")

    toolset = McpToolset(
        connection_params=StdioConnectionParams(
            server_params=StdioServerParameters(
                command=sys.executable,
                args=["-m", "compliance_agent.mcp_server"],
                env=_mcp_child_env(),
            ),
            timeout=30.0,
        )
    )

    agent = LlmAgent(
        name=COMPLIANCE_AGENT_NAME,
        model=resolved_model,
        description=(
            "Enterprise Audit & Compliance Agent that retrieves compliance policies from Secret Manager, "
            "reads audit evidence from GCS, and evaluates deterministic SOX, SOC2, FinOps, and Treasury controls."
        ),
        instruction=(
            "You are the Enterprise Audit & Compliance Agent. "
            "Always ground your audit assessment strictly in MCP tool outputs. "
            "1. Call fetch_compliance_policy() to retrieve the authoritative compliance policy rules from GCP Secret Manager. "
            "2. Call read_audit_evidence(doc_id) to retrieve the target audit evidence JSON from GCS. "
            "3. ALWAYS call evaluate_control_matrix(document_json, policy_json) passing the evidence JSON and policy JSON "
            "to obtain deterministic control_results, violations, and compliant status. Never fabricate a PASS when evidence is missing. "
            "4. Populate mcp_tools_called, gcs_sources, and secret_policies_checked accurately from the tool responses. "
            "5. Respond strictly using the structured JSON schema."
        ),
        tools=[toolset],
        output_schema=ComplianceAuditOutput,
    )

    @asynccontextmanager
    async def toolset_lifespan(_starlette_app: object):
        try:
            yield
        finally:
            await toolset.close()

    a2a_app = to_a2a(
        agent,
        host=resolved_host,
        port=resolved_port,
        protocol=resolved_protocol,
        lifespan=toolset_lifespan,
    )

    @asynccontextmanager
    async def fastapi_lifespan(_app: FastAPI):
        async with a2a_app.router.lifespan_context(a2a_app):
            yield

    app = FastAPI(
        title="Audit & Compliance A2A Agent",
        version="0.1.0",
        lifespan=fastapi_lifespan,
    )

    @app.get("/healthz")
    @app.get("/health")
    @app.get("/api/health")
    async def healthz() -> dict[str, object]:
        return {
            "status": "ok",
            "agent": COMPLIANCE_AGENT_NAME,
            "mcp_tools": COMPLIANCE_MCP_TOOLS,
        }

    # Mount A2A Starlette app AFTER /healthz so /healthz is never shadowed by "/"
    app.mount("/", a2a_app)
    return app


app = create_app()
