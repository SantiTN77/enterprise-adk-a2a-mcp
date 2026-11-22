"""ASGI TestClient tests for financial_agent /healthz, Agent Card, and A2A JSON-RPC."""

from __future__ import annotations

import json
from unittest.mock import patch

from fastapi.testclient import TestClient
from google.adk.events.event import Event
from google.adk.runners import Runner
from google.genai import types

from financial_agent.app import FINANCIAL_AGENT_NAME, FINANCIAL_MCP_TOOLS, create_app


def test_healthz_and_local_agent_card_with_mcp_skills(monkeypatch) -> None:
    monkeypatch.setenv("PUBLIC_HOST", "localhost")
    monkeypatch.setenv("PUBLIC_PORT", "8001")
    monkeypatch.setenv("PUBLIC_PROTOCOL", "http")
    app = create_app()

    with TestClient(app) as client:
        health = client.get("/healthz")
        assert health.status_code == 200
        assert health.json() == {
            "status": "ok",
            "agent": FINANCIAL_AGENT_NAME,
            "mcp_tools": FINANCIAL_MCP_TOOLS,
        }

        card_resp = client.get("/.well-known/agent-card.json")
        assert card_resp.status_code == 200
        card = card_resp.json()
        assert card["name"] == FINANCIAL_AGENT_NAME
        assert card["supportedInterfaces"][0]["url"] == "http://localhost:8001"
        skill_names = {skill["name"] for skill in card.get("skills", [])}
        assert set(FINANCIAL_MCP_TOOLS).issubset(skill_names)


def test_cloud_run_public_url_override_on_agent_card() -> None:
    app = create_app(
        public_host="adk-financial-agent-123456.us-central1.run.app",
        public_port=443,
        public_protocol="https",
    )
    with TestClient(app) as client:
        card_resp = client.get("/.well-known/agent-card.json")
        assert card_resp.status_code == 200
        card = card_resp.json()
        assert (
            card["supportedInterfaces"][0]["url"]
            == "https://adk-financial-agent-123456.us-central1.run.app:443"
        )


def test_a2a_jsonrpc_v1_and_v03_routing() -> None:
    structured_payload = json.dumps(
        {
            "summary": "Q3 vendor spend exceeded budget by 28.0%.",
            "doc_id": "samples/q3_cloud_vendor_review.json",
            "findings": ["GPU cluster spend +60% over budget"],
            "metrics": {"budget_variance_pct": 28.0},
            "anomalies": [],
            "mcp_tools_called": ["read_enterprise_document", "compute_financial_ratios"],
            "gcs_sources": ["gs://bucket/samples/q3_cloud_vendor_review.json"],
        }
    )

    async def fake_run_async(self, *, user_id, session_id, new_message, **kwargs):
        yield Event(
            invocation_id="inv-fin-1",
            author=FINANCIAL_AGENT_NAME,
            content=types.Content(role="model", parts=[types.Part(text=structured_payload)]),
        )

    app = create_app(public_host="localhost", public_port=8001, public_protocol="http")
    with patch.object(Runner, "run_async", new=fake_run_async):
        with TestClient(app) as client:
            # A2A v1.0 SendMessage
            v1_resp = client.post(
                "/",
                headers={"A2A-Version": "1.0"},
                json={
                    "jsonrpc": "2.0",
                    "id": "req-v1",
                    "method": "SendMessage",
                    "params": {
                        "message": {
                            "messageId": "msg-v1",
                            "role": "ROLE_USER",
                            "parts": [{"text": "Analyze Q3 vendor review"}],
                        }
                    },
                },
            )
            assert v1_resp.status_code == 200
            v1_body = v1_resp.json()
            assert "result" in v1_body
            assert v1_body["result"]["task"]["status"]["state"] == "TASK_STATE_COMPLETED"
            v1_text = v1_body["result"]["task"]["artifacts"][0]["parts"][0]["text"]
            assert json.loads(v1_text)["doc_id"] == "samples/q3_cloud_vendor_review.json"

            # A2A v0.3 compat message/send
            v03_resp = client.post(
                "/",
                json={
                    "jsonrpc": "2.0",
                    "id": "req-v03",
                    "method": "message/send",
                    "params": {
                        "message": {
                            "messageId": "msg-v03",
                            "role": "user",
                            "parts": [{"kind": "text", "text": "Analyze Q3 vendor review"}],
                        }
                    },
                },
            )
            assert v03_resp.status_code == 200
            v03_body = v03_resp.json()
            assert "result" in v03_body
            assert v03_body["result"]["status"]["state"] == "completed"
            v03_text = v03_body["result"]["artifacts"][0]["parts"][0]["text"]
            assert json.loads(v03_text)["summary"] == "Q3 vendor spend exceeded budget by 28.0%."
