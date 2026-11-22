"""FastAPI + ADK + A2A application entrypoint for the Financial Analysis Agent."""

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

FINANCIAL_AGENT_NAME = "financial_analysis_agent"
FINANCIAL_MCP_TOOLS = [
    "list_enterprise_documents",
    "read_enterprise_document",
    "compute_financial_ratios",
]


class FinancialMetricsSummary(BaseModel):
    """Typed financial ratio metrics returned by the financial analysis agent."""

    revenue_usd: float | None = None
    operating_expenses_usd: float | None = None
    operating_income_usd: float | None = None
    operating_margin_pct: float | None = None
    expense_to_revenue_ratio: float | None = None
    total_assets_usd: float | None = None
    total_liabilities_usd: float | None = None
    net_equity_usd: float | None = None
    debt_to_assets_ratio: float | None = None
    debt_to_equity_ratio: float | None = None
    operating_cash_flow_usd: float | None = None
    cash_to_liabilities_ratio: float | None = None
    cash_flow_margin_pct: float | None = None
    budgeted_spend_usd: float | None = None
    actual_spend_usd: float | None = None
    budget_variance_usd: float | None = None
    budget_variance_pct: float | None = None


class FinancialAnomaly(BaseModel):
    """Typed financial anomaly detected deterministically."""

    code: str
    severity: str
    metric: str
    value: float | None = None
    threshold: str
    message: str


class FinancialAnalysisOutput(BaseModel):
    """Structured JSON output schema enforced for the financial analysis agent."""

    summary: str = Field(description="Executive summary of financial health and variance findings.")
    doc_id: str = Field(description="Primary analyzed GCS document identifier.")
    findings: list[str] = Field(description="Key quantitative findings grounded in tool outputs.")
    metrics: FinancialMetricsSummary = Field(description="Computed deterministic financial metrics.")
    anomalies: list[FinancialAnomaly] = Field(description="Deterministic financial anomalies flagged.")
    mcp_tools_called: list[str] = Field(description="Exact MCP tool names invoked during analysis.")
    gcs_sources: list[str] = Field(description="Exact gs:// URIs read during analysis.")


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
    """Create the FastAPI application exposing the Financial Analysis A2A agent."""
    resolved_host = public_host or os.environ.get("PUBLIC_HOST", "localhost")
    resolved_port = public_port if public_port is not None else int(os.environ.get("PUBLIC_PORT", "8001"))
    resolved_protocol = public_protocol or os.environ.get("PUBLIC_PROTOCOL", "http")
    resolved_model = model_name or os.environ.get("GEMINI_MODEL", "gemini-3.8-flash")

    toolset = McpToolset(
        connection_params=StdioConnectionParams(
            server_params=StdioServerParameters(
                command=sys.executable,
                args=["-m", "financial_agent.mcp_server"],
                env=_mcp_child_env(),
            ),
            timeout=30.0,
        )
    )

    agent = LlmAgent(
        name=FINANCIAL_AGENT_NAME,
        model=resolved_model,
        description=(
            "Enterprise Financial & Document Analysis Agent that reads financial documents from GCS "
            "and computes deterministic profitability, leverage, liquidity, and budget variance ratios."
        ),
        instruction=(
            "You are the Enterprise Financial & Document Analysis Agent. "
            "Always ground your analysis strictly in MCP tool outputs. "
            "1. If no specific doc_id is provided or you need to discover available files, call list_enterprise_documents(). "
            "2. Call read_enterprise_document(doc_id) to inspect the target enterprise JSON document from GCS. "
            "3. Extract numeric inputs from financial_summary (revenue_usd, operating_expenses_usd, total_liabilities_usd, "
            "total_assets_usd, operating_cash_flow_usd, budgeted_spend_usd, actual_spend_usd; pass 0.0 for any missing "
            "balance-sheet field rather than fabricating numbers) and ALWAYS call compute_financial_ratios(...) to obtain "
            "deterministic metrics and anomalies. "
            "4. Record every MCP tool name you invoked in mcp_tools_called and every gs:// URI returned in gcs_sources. "
            "5. Respond strictly using the structured JSON schema."
        ),
        tools=[toolset],
        output_schema=FinancialAnalysisOutput,
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
        title="Financial & Document Analysis A2A Agent",
        version="0.1.0",
        lifespan=fastapi_lifespan,
    )

    @app.get("/healthz")
    @app.get("/health")
    @app.get("/api/health")
    async def healthz() -> dict[str, object]:
        return {
            "status": "ok",
            "agent": FINANCIAL_AGENT_NAME,
            "mcp_tools": FINANCIAL_MCP_TOOLS,
        }

    # Mount A2A Starlette app AFTER /healthz so /healthz is never shadowed by "/"
    app.mount("/", a2a_app)
    return app


app = create_app()
