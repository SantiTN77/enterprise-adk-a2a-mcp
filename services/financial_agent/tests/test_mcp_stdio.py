"""Genuine OS-pipe stdio IPC tests for financial_agent MCP server."""

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
async def test_production_mcp_stdio_entrypoint_list_and_compute() -> None:
    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "financial_agent.mcp_server"],
        env=_stdio_env(),
    )
    async with stdio_client(params) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            tools_result = await session.list_tools()
            tool_names = {tool.name for tool in tools_result.tools}
            assert tool_names == {
                "list_enterprise_documents",
                "read_enterprise_document",
                "compute_financial_ratios",
            }

            call_result = await session.call_tool(
                "compute_financial_ratios",
                {
                    "revenue": 1000.0,
                    "operating_expenses": 750.0,
                    "liabilities": 400.0,
                    "assets": 1000.0,
                    "cash_flow": 300.0,
                    "budgeted_spend": 500.0,
                    "actual_spend": 650.0,
                },
            )
            assert call_result.is_error is False
            payload = json.loads(call_result.content[0].text)
            assert payload["metrics"]["operating_income_usd"] == 250.0
            assert payload["metrics"]["budget_variance_pct"] == 30.0
            assert payload["anomalies"][0]["code"] == "BUDGET_OVERRUN_CRITICAL"


@pytest.mark.asyncio
async def test_harness_mcp_stdio_gcs_tools_and_not_found() -> None:
    params = StdioServerParameters(
        command=sys.executable,
        args=[str(HARNESS_PATH)],
        env=_stdio_env({"GCS_BUCKET_NAME": "test-enterprise-bucket"}),
    )
    async with stdio_client(params) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()

            listed = await session.call_tool("list_enterprise_documents", {"prefix": "samples/"})
            assert listed.is_error is False
            listed_data = json.loads(listed.content[0].text)
            assert listed_data["count"] == 2
            assert listed_data["documents"][0]["doc_id"] == "samples/q3_cloud_vendor_review.json"

            # Direct gs:// URI stripping and short name fallback
            read_gs = await session.call_tool(
                "read_enterprise_document",
                {"doc_id": "gs://test-enterprise-bucket/samples/q3_cloud_vendor_review.json"},
            )
            assert read_gs.is_error is False
            read_gs_data = json.loads(read_gs.content[0].text)
            assert read_gs_data["doc_id"] == "samples/q3_cloud_vendor_review.json"
            assert read_gs_data["document"]["financial_summary"]["revenue_usd"] == 12600000.0

            read_short = await session.call_tool(
                "read_enterprise_document",
                {"doc_id": "series_b_revenue_audit"},
            )
            assert read_short.is_error is False
            assert json.loads(read_short.content[0].text)["doc_id"] == "samples/series_b_revenue_audit.json"

            missing = await session.call_tool(
                "read_enterprise_document",
                {"doc_id": "samples/does_not_exist.json"},
            )
            assert missing.is_error is True
            assert "Document not found" in missing.content[0].text
