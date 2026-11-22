"""FastAPI entrypoint for the ADK Enterprise Multi-Agent Orchestrator."""

from __future__ import annotations

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from orchestrator.agent import (
    execute_multi_agent_analysis,
    get_compliance_agent_url,
    get_financial_agent_url,
    load_scenarios_from_gcs,
)
from orchestrator.schemas import AnalyzeRequest, AnalyzeResponse, ScenariosResponse


def create_app(
    *,
    financial_url: str | None = None,
    compliance_url: str | None = None,
    oidc_enabled: bool | None = None,
    a2a_transport: httpx.AsyncBaseTransport | None = None,
) -> FastAPI:
    """Create the FastAPI application for adk-orchestrator."""
    app = FastAPI(
        title="ADK Enterprise Multi-Agent Orchestrator",
        version="0.1.0",
    )

    @app.get("/healthz")
    @app.get("/health")
    @app.get("/api/health")
    async def healthz() -> dict[str, object]:
        fin_url = (financial_url or get_financial_agent_url()).rstrip("/")
        comp_url = (compliance_url or get_compliance_agent_url()).rstrip("/")
        return {
            "status": "ok",
            "service": "adk-orchestrator",
            "agents": {
                "financial": fin_url,
                "compliance": comp_url,
            },
        }

    @app.get("/api/scenarios", response_model=ScenariosResponse)
    async def list_scenarios() -> ScenariosResponse:
        return load_scenarios_from_gcs()

    @app.post("/api/analyze", response_model=AnalyzeResponse)
    async def analyze(request: Request) -> AnalyzeResponse | JSONResponse:
        content_type = (request.headers.get("content-type") or "").lower()
        if "application/json" not in content_type:
            raise HTTPException(
                status_code=415,
                detail="Content-Type must be application/json.",
            )

        try:
            raw_json = await request.json()
        except Exception as exc:
            raise HTTPException(
                status_code=400,
                detail="Request body must be valid JSON.",
            ) from exc

        if not isinstance(raw_json, dict) or not raw_json:
            raise HTTPException(
                status_code=422,
                detail="Request payload must be a non-empty JSON object.",
            )

        try:
            parsed_req = AnalyzeRequest.model_validate(raw_json)
        except ValidationError as exc:
            return JSONResponse(
                status_code=422,
                content={
                    "detail": "Invalid analysis request payload.",
                    "errors": exc.errors(),
                },
            )

        return await execute_multi_agent_analysis(
            parsed_req,
            financial_url=financial_url,
            compliance_url=compliance_url,
            oidc_enabled=oidc_enabled,
            a2a_transport=a2a_transport,
        )

    return app


app = create_app()
