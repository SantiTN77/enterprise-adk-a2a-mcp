"""Genuine OS-pipe stdio IPC tests for compliance_agent MCP server."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

SERVICE_DIR = Path(__file__).resolve().parents[1]
SRC_DIR = SERVICE_DIR / "src"
HARNESS_PATH = Path(__file__).resolve().parent / "mcp_test_harness.py"


def _stdio_env(extra: dict[str, str] | None = None) -> dict[str, str]:
    env = os.environ.copy()
    existing = env.get("PYTHONPATH", "")
    parts = [p for p in existing.split(os.pathsep) if p]
    if str(SRC_DIR) not in parts:
        env["PYTHONPATH"] = os.pathsep.join([str(SRC_DIR), *parts])
    if extra:
        env.update(extra)
    return env


@pytest.mark.asyncio
async def test_production_mcp_stdio_entrypoint_list_and_evaluate() -> None:
    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "compliance_agent.mcp_server"],
        env=_stdio_env(),
    )
    async with stdio_client(params) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            tools_result = await session.list_tools()
            assert {t.name for t in tools_result.tools} == {
                "fetch_compliance_policy",
                "read_audit_evidence",
                "evaluate_control_matrix",
            }

            doc_json = json.dumps(
                {
                    "doc_id": "samples/smoke.json",
                    "financial_summary": {"budgeted_spend_usd": 100.0, "actual_spend_usd": 125.0},
                }
            )
            pol_json = json.dumps(
                {
                    "policy_id": "POL-SMOKE",
                    "thresholds": {"max_budget_variance_pct": 10.0},
                    "controls": [{"control_id": "FIN-VAR-01", "name": "Variance", "severity": "HIGH"}],
                }
            )
            res = await session.call_tool(
                "evaluate_control_matrix",
                {"document_json": doc_json, "policy_json": pol_json},
            )
            assert res.is_error is False
            payload = json.loads(res.content[0].text)
            assert payload["compliant"] is False
            assert payload["violations"][0]["control_id"] == "FIN-VAR-01"


@pytest.mark.asyncio
async def test_harness_mcp_stdio_secret_and_gcs_tools() -> None:
    params = StdioServerParameters(
        command=sys.executable,
        args=[str(HARNESS_PATH)],
        env=_stdio_env(
            {
                "GOOGLE_CLOUD_PROJECT": "test-project",
                "GCS_BUCKET_NAME": "test-enterprise-bucket",
                "COMPLIANCE_SECRET_ID": "adk-compliance-policy-rules",
            }
        ),
    )
    async with stdio_client(params) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()

            pol_res = await session.call_tool("fetch_compliance_policy", {})
            assert pol_res.is_error is False
            pol_data = json.loads(pol_res.content[0].text)
            assert pol_data["secret_id"] == "adk-compliance-policy-rules"
            assert pol_data["policy"]["policy_id"] == "ENT-COMP-POLICY-TEST"

            ev_res = await session.call_tool(
                "read_audit_evidence",
                {"doc_id": "q3_cloud_vendor_review"},
            )
            assert ev_res.is_error is False
            ev_data = json.loads(ev_res.content[0].text)
            assert ev_data["doc_id"] == "samples/q3_cloud_vendor_review.json"

            # End-to-end envelope evaluation over stdio
            eval_res = await session.call_tool(
                "evaluate_control_matrix",
                {"document_json": ev_res.content[0].text, "policy_json": pol_res.content[0].text},
            )
            assert eval_res.is_error is False
            eval_data = json.loads(eval_res.content[0].text)
            assert eval_data["compliant"] is False
            assert eval_data["summary"]["failed"] == 2

            # Missing secret & missing GCS doc -> is_error=True
            missing_secret = await session.call_tool(
                "fetch_compliance_policy",
                {"secret_id": "nonexistent-secret"},
            )
            assert missing_secret.is_error is True
            assert "not found" in missing_secret.content[0].text.lower()

            missing_doc = await session.call_tool(
                "read_audit_evidence",
                {"doc_id": "samples/missing.json"},
            )
            assert missing_doc.is_error is True
            assert "not found" in missing_doc.content[0].text.lower()
