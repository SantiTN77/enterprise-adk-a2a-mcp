# Demo & Verification Walkthrough

This guide provides step-by-step pre-flight verification, 1-click demo scenarios, and troubleshooting for the **Enterprise Multi-Agent Risk & Compliance Console**.

---

## 1. Pre-Flight Security & Health Checks

### A. Verify Private Cloud Run IAM Enforcement (`401/403`)
Direct unauthenticated requests to any Cloud Run service must fail closed:

```bash
curl -i https://<YOUR_ORCHESTRATOR_URL>/healthz
curl -i https://<YOUR_FINANCIAL_AGENT_URL>/.well-known/agent-card.json
curl -i https://<YOUR_COMPLIANCE_AGENT_URL>/.well-known/agent-card.json
# Expected: HTTP/2 401 or 403 (Google Cloud Run IAM)
```

### B. Verify Vercel BFF Health Endpoint (`200`)
The Next.js BFF mints a scoped OIDC ID token server-side and proxies `/healthz`:

```bash
curl -s https://<YOUR_VERCEL_URL>/api/health | jq .
```

Expected payload:
```json
{
  "status": "ok",
  "service": "vercel-bff",
  "bff": {
    "runtime": "nodejs",
    "auth_mode": "oidc-sa",
    "orchestrator_configured": true
  },
  "orchestrator": {
    "status": "ok",
    "service": "adk-orchestrator"
  }
}
```

---

## 2. 1-Click Synthetic Scenario Walkthroughs

Open `<YOUR_VERCEL_URL>` (or `http://127.0.0.1:3000` locally) in a clean Chrome profile.

### Scenario 1: `q3_cloud_vendor_review` (Meridian Retail Analytics Corp.)
1. Click **Run 1-Click** on **Q3 Cloud & AI Vendor Spend Review**.
2. **What happens under the hood**:
   - Browser posts `{ scenario_id: "q3_cloud_vendor_review", doc_id: "samples/q3_cloud_vendor_review.json", ... }` to `/api/analyze`.
   - Vercel BFF validates via Zod v4 and sends a Google OIDC ID token to `adk-orchestrator`.
   - `adk-orchestrator` delegates via A2A (`CloudRun-OIDC-IAM`) to `financial_analysis_agent` and `audit_compliance_agent`, which invoke their stdio `MCPServer` tools.
3. **Expected Output**:
   - **Risk Rating**: `HIGH RISK`
   - **Financial Metrics**: Revenue `$12,600,000`, Budgeted `$3,200,000`, Actual `$4,096,000`, Budget Variance `+28.00%` (`$896,000` overrun led by GPU burst scaling).
   - **Compliance Violations**: `FIN-VAR-01` (exceeds 10% limit without CFO waiver) and `SOX-APPR-02` (`AMD-2026-Q3-09` for `$660,000` lacks a second Finance leadership approver).
   - **A2A Trace**: 2 recorded steps (`financial_analysis_agent`, `audit_compliance_agent`) showing `A2A`, `CloudRun-OIDC-IAM`, MCP tool chips, and latencies.

### Scenario 2: `series_b_revenue_audit` (Northwind Cloud Robotics Inc.)
1. Click **Run 1-Click** on **Series B Q3 Revenue Recognition & Audit Readiness**.
2. **Expected Output**:
   - **Risk Rating**: `LOW RISK` · **Compliance Badge**: `COMPLIANT`
   - **Financial Metrics**: Revenue `$18,450,000`, `+1.43%` budget variance, `78.40%` gross margin, `$5,100,000` operating cash flow.
   - **Compliance Violations**: Zero compliance violations detected (`FIN-VAR-01`, `SOX-APPR-02`, `SOC2-VEND-03`, `TRES-SOD-04`, `SOX-REV-05` all pass).

### Scenario 3: `treasury_controls_memo` (Helios FinTech Payments Inc.)
1. Click **Run 1-Click** on **Treasury Wire Controls & Vendor Exception Memo**.
2. **Expected Output**:
   - **Risk Rating**: `CRITICAL RISK` · **Compliance Badge**: `NON-COMPLIANT`
   - **Financial Metrics**: Revenue `$9,800,000`, `+22.00%` budget variance, `-$420,000` operating cash flow, `$185,000` unreconciled suspense.
   - **Compliance Violations**: `TRES-SOD-04` (`emp-tres-701` prepared, self-approved, and released `$840,000` wire `WIRE-2026-0891`), `SOC2-VEND-03` (`NovaRail Clearing Partners` unvetted without SOC2/DPA; `Kestrel FX Settlement` SOC2 expired), `FIN-VAR-01`, `SOX-APPR-02`, `SOX-REV-05`.

### Architecture & Security Posture Verification
- Click **Architecture & Security Posture** in the top header (expanded by default) to inspect the 5-hop zero-trust path and `$0 Idle Cost` (`min_instances=0, max_instances=2`) badges.
- Click **Show Raw JSON** on any report to inspect the raw structured `AnalyzeResponse` payload and confirm zero GCP credentials or bearer tokens appear in browser payloads.

---

## 3. Troubleshooting

| Symptom | Root Cause | Resolution |
|---|---|---|
| `HTTP 502: Upstream Cloud Run IAM rejected OIDC authentication` | `CLOUD_RUN_ORCHESTRATOR_URL` contains a trailing `/` or subpath, or `vercel-bff-invoker` lacks `roles/run.invoker`. | Ensure `CLOUD_RUN_ORCHESTRATOR_URL` is exact origin (`https://...a.run.app` with no trailing slash) and verify Terraform IAM bindings. |
| `GCP_PRIVATE_KEY is malformed` | Private key pasted without PEM headers or with broken newline escapes. | Paste the full `-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----` string (both `\n` and literal newlines are normalized automatically). |
| First analysis takes 25–45 seconds | Cold start across 3 scale-to-zero Cloud Run containers (`min_instance_count=0`). | Expected `$0` idle behavior; subsequent runs within the warm window complete in a few seconds. Click **Refresh Health** first to pre-warm `adk-orchestrator`. |
| Local E2E cannot reach orchestrator | `LOCAL_DEV_ORCHESTRATOR_URL` unset or pointing to non-localhost host. | Set `LOCAL_DEV_ORCHESTRATOR_URL=http://127.0.0.1:8080` in `web/.env.local` (only active outside `NODE_ENV=production` / Vercel). |
