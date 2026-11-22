from __future__ import annotations

import base64
import json
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any


def make_fake_jwt(audience: str, *, email: str = "e2e-caller@example.iam.gserviceaccount.com") -> str:
    """Create a syntactically valid unsigned test JWT for offline mock verification only."""
    header = base64.urlsafe_b64encode(json.dumps({"alg": "RS256", "typ": "JWT"}).encode()).rstrip(b"=").decode()
    payload = base64.urlsafe_b64encode(
        json.dumps({"aud": audience, "email": email, "iss": "https://accounts.google.com"}).encode()
    ).rstrip(b"=").decode()
    return f"{header}.{payload}.mock_signature"


def decode_fake_jwt_aud(token: str) -> str | None:
    parts = token.split(".")
    if len(parts) != 3:
        return None
    pad = "=" * (-len(parts[1]) % 4)
    try:
        payload = json.loads(base64.urlsafe_b64decode(parts[1] + pad).decode("utf-8"))
        return payload.get("aud")
    except Exception:
        return None


@dataclass
class FaultConfig:
    allow_unauth: bool = False
    retired_model: bool = False
    missing_compliance_trace: bool = False
    leak_secret_in_api: bool = False
    leak_secret_in_bundle: bool = False
    ui_console_error: bool = False
    ui_direct_run_app_call: bool = False
    bff_upstream_502: bool = False


@dataclass
class MockStack:
    faults: FaultConfig = field(default_factory=FaultConfig)
    _servers: list[ThreadingHTTPServer] = field(default_factory=list)
    _threads: list[threading.Thread] = field(default_factory=list)
    financial_url: str = ""
    compliance_url: str = ""
    orchestrator_url: str = ""
    web_url: str = ""

    def __enter__(self) -> "MockStack":
        self.start()
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        self.stop()

    def start(self) -> None:
        stack = self

        def _check_iam(handler: BaseHTTPRequestHandler, expected_aud: str) -> bool:
            if stack.faults.allow_unauth:
                return True
            auth = handler.headers.get("Authorization", "")
            if not auth.startswith("Bearer "):
                handler.send_response(401)
                handler.end_headers()
                return False
            tok = auth[7:].strip()
            if not tok or tok.startswith("ya29."):
                handler.send_response(401)
                handler.end_headers()
                return False
            aud = decode_fake_jwt_aud(tok)
            if aud != expected_aud:
                handler.send_response(403)
                handler.end_headers()
                return False
            return True

        def _send_json(handler: BaseHTTPRequestHandler, code: int, payload: Any) -> None:
            raw = json.dumps(payload).encode("utf-8")
            handler.send_response(code)
            handler.send_header("Content-Type", "application/json")
            handler.send_header("Content-Length", str(len(raw)))
            handler.end_headers()
            handler.wfile.write(raw)

        def _read_json(handler: BaseHTTPRequestHandler) -> tuple[Any, str | None]:
            length = int(handler.headers.get("Content-Length", "0") or "0")
            body = handler.rfile.read(length) if length > 0 else b""
            try:
                return json.loads(body.decode("utf-8")), None
            except Exception as exc:
                return None, str(exc)

        class AgentHandler(BaseHTTPRequestHandler):
            agent_name = ""
            base_url = ""
            mcp_tools: list[str] = []

            def log_message(self, fmt: str, *args: Any) -> None:
                return

            def do_GET(self) -> None:
                if not _check_iam(self, self.base_url):
                    return
                if self.path == "/healthz":
                    _send_json(
                        self,
                        200,
                        {"status": "ok", "agent": self.agent_name, "mcp_tools": self.mcp_tools},
                    )
                    return
                if self.path == "/.well-known/agent-card.json":
                    _send_json(
                        self,
                        200,
                        {
                            "name": self.agent_name,
                            "description": f"Mock {self.agent_name}",
                            "version": "0.0.1",
                            "capabilities": {"streaming": True},
                            "defaultInputModes": ["text/plain"],
                            "defaultOutputModes": ["text/plain"],
                            "skills": [
                                {
                                    "id": self.agent_name,
                                    "name": "analyze",
                                    "description": f"Run {self.agent_name}",
                                }
                            ],
                            "supportedInterfaces": [
                                {
                                    "url": self.base_url,
                                    "protocolBinding": "JSONRPC",
                                    "protocolVersion": "1.0",
                                }
                            ],
                        },
                    )
                    return
                _send_json(self, 404, {"detail": "Not Found"})

            def do_POST(self) -> None:
                if not _check_iam(self, self.base_url):
                    return
                if self.path != "/":
                    _send_json(self, 404, {"detail": "Not Found"})
                    return
                data, err = _read_json(self)
                if err is not None or not isinstance(data, dict):
                    _send_json(self, 400, {"jsonrpc": "2.0", "error": {"code": -32700, "message": "Parse error"}})
                    return
                method = data.get("method")
                if method not in {"SendMessage", "message/send"}:
                    _send_json(
                        self,
                        400,
                        {"jsonrpc": "2.0", "id": data.get("id"), "error": {"code": -32601, "message": "Method not found"}},
                    )
                    return
                _send_json(
                    self,
                    200,
                    {
                        "jsonrpc": "2.0",
                        "id": data.get("id", "1"),
                        "result": {
                            "summary": f"{self.agent_name} completed analysis.",
                            "findings": ["Variance evaluated"],
                            "mcp_tools_called": self.mcp_tools,
                            "gcs_sources": ["samples/q3_cloud_vendor_review.json"],
                        },
                    },
                )

        # Start Financial & Compliance agents first so Orchestrator knows their URLs
        class FinHandler(AgentHandler):
            agent_name = "financial_analysis_agent"
            mcp_tools = [
                "list_enterprise_documents",
                "read_enterprise_document",
                "compute_financial_ratios",
            ]

        class CompHandler(AgentHandler):
            agent_name = "audit_compliance_agent"
            mcp_tools = [
                "read_compliance_policy",
                "read_audit_evidence",
                "evaluate_control_matrix",
            ]

        fin_srv = ThreadingHTTPServer(("127.0.0.1", 0), FinHandler)
        FinHandler.base_url = f"http://127.0.0.1:{fin_srv.server_port}"
        self.financial_url = FinHandler.base_url

        comp_srv = ThreadingHTTPServer(("127.0.0.1", 0), CompHandler)
        CompHandler.base_url = f"http://127.0.0.1:{comp_srv.server_port}"
        self.compliance_url = CompHandler.base_url

        def _build_analyze_response(body: dict[str, Any]) -> dict[str, Any]:
            scenario_id = str(body.get("scenario_id") or "adhoc")
            doc_id = str(body.get("doc_id") or "adhoc/inline")
            doc_text = str(body.get("document_text") or "")
            persist = bool(body.get("persist_report", True))
            run_id = str(uuid.uuid4())
            is_violation = (
                "treasury" in scenario_id
                or "vendor" in scenario_id
                or "unapproved" in doc_text.lower()
                or "sole-source" in doc_text.lower()
            )
            risk = "HIGH" if is_violation else "LOW"
            model = "gemini-2.0-flash" if stack.faults.retired_model else "gemini-3.8-flash"
            summary = "Executive multi-agent assessment completed."
            if stack.faults.leak_secret_in_api:
                summary += " -----BEGIN " + "PRIVATE KEY----- MIIEvQIBADANBgkqhkiG9w0BAQEFAASCBKcw"

            trace = [
                {
                    "step": 1,
                    "caller": "adk-orchestrator",
                    "target": "financial_analysis_agent",
                    "protocol": "A2A",
                    "auth": "CloudRun-OIDC-IAM",
                    "mcp_tools": ["list_enterprise_documents", "read_enterprise_document", "compute_financial_ratios"],
                    "latency_ms": 142,
                    "status": "SUCCESS",
                }
            ]
            if not stack.faults.missing_compliance_trace:
                trace.append(
                    {
                        "step": 2,
                        "caller": "adk-orchestrator",
                        "target": "audit_compliance_agent",
                        "protocol": "A2A",
                        "auth": "CloudRun-OIDC-IAM",
                        "mcp_tools": ["read_compliance_policy", "evaluate_control_matrix"],
                        "latency_ms": 185,
                        "status": "SUCCESS",
                    }
                )

            return {
                "run_id": run_id,
                "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                "scenario_id": scenario_id,
                "doc_id": doc_id,
                "executive_summary": summary,
                "overall_risk_rating": risk,
                "financial_analysis": {
                    "summary": "Budget variance and unit ratios computed cleanly.",
                    "key_metrics": {"variance_pct": 24.5 if is_violation else 1.2, "total_spend": 480000 if "480,000" in doc_text else 125000},
                    "anomalies": ["Unapproved spend spike"] if is_violation else [],
                    "sources": [doc_id],
                },
                "compliance_audit": {
                    "summary": "Evaluated against Secret Manager compliance rules.",
                    "policy_id": "adk-compliance-policy-rules",
                    "controls_evaluated": [{"control": "DUAL_APPROVAL", "status": "FAIL" if is_violation else "PASS"}],
                    "violations": ["Missing dual CFO/VP approval"] if is_violation else [],
                    "compliant": not is_violation,
                },
                "recommendations": ["Require dual CFO sign-off"] if is_violation else ["Maintain baseline controls"],
                "a2a_trace": trace,
                "gcp_provenance": {
                    "vertex_ai_model": model,
                    "vertex_ai_location": "global",
                    "gcs_bucket": "enterprise-adk-docs-gen-lang-client-0527325883",
                    "report_gcs_uri": f"gs://enterprise-adk-docs-gen-lang-client-0527325883/reports/{run_id}.json" if persist else None,
                    "secret_manager_policy": "adk-compliance-policy-rules",
                },
                "security_posture": {
                    "cloud_run_iam": "private-oidc-enforced",
                    "min_instances": 0,
                    "max_instances": 2,
                },
            }

        class OrchHandler(BaseHTTPRequestHandler):
            base_url = ""

            def log_message(self, fmt: str, *args: Any) -> None:
                return

            def do_GET(self) -> None:
                if not _check_iam(self, self.base_url):
                    return
                if self.path == "/healthz":
                    _send_json(
                        self,
                        200,
                        {
                            "status": "ok",
                            "service": "adk-orchestrator",
                            "agents": {
                                "financial": stack.financial_url,
                                "compliance": stack.compliance_url,
                            },
                        },
                    )
                    return
                if self.path == "/api/scenarios":
                    _send_json(
                        self,
                        200,
                        {
                            "scenarios": [
                                {
                                    "id": "q3_cloud_vendor_review",
                                    "title": "Q3 Cloud Vendor Spend Review",
                                    "doc_id": "samples/q3_cloud_vendor_review.json",
                                    "gcs_uri": "gs://enterprise-adk-docs-gen-lang-client-0527325883/samples/q3_cloud_vendor_review.json",
                                    "description": "Review Q3 cloud vendor spend anomalies and procurement approvals.",
                                    "default_prompt": "Analyze financial variance and audit compliance controls for Q3 vendor spend.",
                                },
                                {
                                    "id": "series_b_revenue_audit",
                                    "title": "Series B Revenue Audit",
                                    "doc_id": "samples/series_b_revenue_audit.json",
                                    "gcs_uri": "gs://enterprise-adk-docs-gen-lang-client-0527325883/samples/series_b_revenue_audit.json",
                                    "description": "Audit Series B ARR recognition and margin ratios.",
                                    "default_prompt": "Verify Series B revenue recognition ratios and compliance controls.",
                                },
                                {
                                    "id": "treasury_controls_memo",
                                    "title": "Treasury Controls Memo",
                                    "doc_id": "samples/treasury_controls_memo.json",
                                    "gcs_uri": "gs://enterprise-adk-docs-gen-lang-client-0527325883/samples/treasury_controls_memo.json",
                                    "description": "Evaluate treasury dual-approval controls and policy compliance.",
                                    "default_prompt": "Audit treasury control approvals against policy rules.",
                                },
                            ]
                        },
                    )
                    return
                _send_json(self, 404, {"detail": "Not Found"})

            def do_POST(self) -> None:
                if not _check_iam(self, self.base_url):
                    return
                if self.path != "/api/analyze":
                    _send_json(self, 404, {"detail": "Not Found"})
                    return
                ctype = (self.headers.get("Content-Type") or "").lower()
                if "application/json" not in ctype:
                    _send_json(self, 415, {"detail": "Content-Type must be application/json"})
                    return
                data, err = _read_json(self)
                if err is not None or not isinstance(data, dict):
                    _send_json(self, 422, {"detail": "Malformed JSON payload"})
                    return
                if not data.get("doc_id") and not data.get("document_text"):
                    _send_json(self, 422, {"detail": "Either doc_id or document_text is required"})
                    return
                _send_json(self, 200, _build_analyze_response(data))

        orch_srv = ThreadingHTTPServer(("127.0.0.1", 0), OrchHandler)
        OrchHandler.base_url = f"http://127.0.0.1:{orch_srv.server_port}"
        self.orchestrator_url = OrchHandler.base_url

        class WebHandler(BaseHTTPRequestHandler):
            def log_message(self, fmt: str, *args: Any) -> None:
                return

            def do_GET(self) -> None:
                if self.path == "/favicon.ico":
                    self.send_response(204)
                    self.end_headers()
                    return
                if self.path == "/":
                    html = """<!doctype html>
<html lang="en">
<head><meta charset="utf-8"><title>Enterprise ADK A2A & MCP</title></head>
<body>
  <main>
    <h1>Enterprise Multi-Agent Financial & Compliance Console</h1>
    <form id="analyze-form">
      <label for="scenario">Scenario</label>
      <select id="scenario" data-testid="scenario-select">
        <option value="q3_cloud_vendor_review">Q3 Cloud Vendor Spend Review</option>
        <option value="series_b_revenue_audit">Series B Revenue Audit</option>
        <option value="treasury_controls_memo">Treasury Controls Memo</option>
      </select>
      <label for="prompt">Prompt</label>
      <textarea id="prompt" data-testid="prompt-input">Analyze financial variance and audit compliance controls.</textarea>
      <label for="adhoc">Document</label>
      <textarea id="adhoc" data-testid="adhoc-doc-input"></textarea>
      <button type="submit" data-testid="analyze-submit">Analyze</button>
    </form>
    <div id="error" role="alert" data-testid="error-banner" hidden></div>
    <section data-testid="security-posture">private-oidc-enforced | min_instances: 0 | max_instances: 2</section>
    <section id="results" hidden>
      <div data-testid="risk-rating" id="risk-rating"></div>
      <div data-testid="executive-summary" id="executive-summary"></div>
      <div data-testid="financial-analysis" id="financial-analysis"></div>
      <div data-testid="compliance-audit" id="compliance-audit"></div>
      <div data-testid="a2a-trace" id="a2a-trace"></div>
    </section>
  </main>
  <script src="/_next/static/app.js"></script>
</body>
</html>"""
                    raw = html.encode("utf-8")
                    self.send_response(200)
                    self.send_header("Content-Type", "text/html; charset=utf-8")
                    self.send_header("Content-Length", str(len(raw)))
                    self.end_headers()
                    self.wfile.write(raw)
                    return

                if self.path == "/_next/static/app.js":
                    leak_line = (
                        'const leaked = "-----BEGIN ' + 'PRIVATE KEY----- MIIEvQIBADANBgkqhkiG9w0B";'
                        if stack.faults.leak_secret_in_bundle
                        else ""
                    )
                    err_line = (
                        'console.error("Injected UI console error");'
                        if stack.faults.ui_console_error
                        else ""
                    )
                    run_app_line = (
                        'fetch("https://adk-orchestrator-fake.a.run.app/healthz").catch(() => {});'
                        if stack.faults.ui_direct_run_app_call
                        else ""
                    )
                    js = f"""
{leak_line}
{err_line}
{run_app_line}
document.getElementById('analyze-form').addEventListener('submit', async (e) => {{
  e.preventDefault();
  const scenario = document.getElementById('scenario').value;
  const prompt = document.getElementById('prompt').value;
  const documentText = document.getElementById('adhoc').value;
  const resp = await fetch('/api/analyze', {{
    method: 'POST',
    headers: {{ 'Content-Type': 'application/json' }},
    body: JSON.stringify({{ scenario_id: scenario, doc_id: 'samples/' + scenario + '.json', prompt, document_text: documentText || undefined }})
  }});
  if (!resp.ok) {{
    const err = document.getElementById('error');
    err.hidden = false;
    err.textContent = 'Upstream service error (' + resp.status + ')';
    return;
  }}
  const data = await resp.json();
  document.getElementById('results').hidden = false;
  document.getElementById('risk-rating').textContent = data.overall_risk_rating;
  document.getElementById('executive-summary').textContent = data.executive_summary;
  document.getElementById('financial-analysis').textContent = JSON.stringify(data.financial_analysis);
  document.getElementById('compliance-audit').textContent = JSON.stringify(data.compliance_audit);
  document.getElementById('a2a-trace').textContent = JSON.stringify(data.a2a_trace);
}});
"""
                    raw = js.encode("utf-8")
                    self.send_response(200)
                    self.send_header("Content-Type", "application/javascript")
                    self.send_header("Content-Length", str(len(raw)))
                    self.end_headers()
                    self.wfile.write(raw)
                    return

                if self.path == "/api/health":
                    _send_json(self, 200, {"status": "ok", "bff": "vercel-oidc", "orchestrator": "ok"})
                    return

                if self.path == "/api/scenarios":
                    _send_json(
                        self,
                        200,
                        {
                            "scenarios": [
                                {
                                    "id": "q3_cloud_vendor_review",
                                    "title": "Q3 Cloud Vendor Spend Review",
                                    "doc_id": "samples/q3_cloud_vendor_review.json",
                                    "gcs_uri": "gs://enterprise-adk-docs-gen-lang-client-0527325883/samples/q3_cloud_vendor_review.json",
                                    "description": "Review Q3 cloud vendor spend anomalies.",
                                    "default_prompt": "Analyze Q3 vendor spend.",
                                }
                            ]
                        },
                    )
                    return

                if self.path == "/api/analyze":
                    _send_json(self, 405, {"error": "Method Not Allowed"})
                    return

                _send_json(self, 404, {"error": "Not Found"})

            def do_POST(self) -> None:
                if self.path != "/api/analyze":
                    _send_json(self, 404, {"error": "Not Found"})
                    return
                if stack.faults.bff_upstream_502:
                    _send_json(self, 502, {"error": "Upstream orchestrator unavailable"})
                    return
                data, err = _read_json(self)
                if err is not None or not isinstance(data, dict):
                    _send_json(self, 400, {"error": "Invalid JSON body"})
                    return
                if not data.get("doc_id") and not data.get("document_text"):
                    _send_json(self, 400, {"error": "Validation error: doc_id or document_text required"})
                    return
                _send_json(self, 200, _build_analyze_response(data))

        web_srv = ThreadingHTTPServer(("127.0.0.1", 0), WebHandler)
        self.web_url = f"http://127.0.0.1:{web_srv.server_port}"

        for srv in (fin_srv, comp_srv, orch_srv, web_srv):
            t = threading.Thread(target=srv.serve_forever, daemon=True)
            t.start()
            self._servers.append(srv)
            self._threads.append(t)

    def stop(self) -> None:
        for srv in self._servers:
            srv.shutdown()
            srv.server_close()
        self._servers.clear()
        self._threads.clear()
