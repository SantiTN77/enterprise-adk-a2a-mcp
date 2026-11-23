# Test Infrastructure & E2E Test Plan (`enterprise-adk-a2a-mcp`)

> **Project**: Project 1 — Enterprise Multi-Agent System (ADK + A2A + MCP on Cloud Run + Vercel Next.js OIDC BFF)  
> **Milestone**: `M5-e2e-testing-track`  
> **Target Repository**: `c:\Users\someb\Projects\enterprise-adk-a2a-mcp`  
> **Suite Location**: `c:\Users\someb\Projects\enterprise-adk-a2a-mcp\tests\e2e_suite\`

---

## 1. Test Philosophy

1. **Opaque-Box & Requirement-Driven**: Every test validates external system behavior strictly against `ORIGINAL_REQUEST.md` (R1, R4, Guardrails, Acceptance Criteria) and `PROJECT.md` (Invariants 1–7, Feature Inventory rows 1–11, Interface Contracts 1–4). The suite **never** imports internal Python modules from `services/` or TypeScript modules from `web/` (enforced via Python `ast` static hygiene checks).
2. **Systematic Test Design Methodology**:
   - **Category-Partition Testing (Tier 1)**: Partitions each functional area into equivalence classes covering valid inputs, IAM authentication states, A2A discovery/RPC formats, MCP tool execution, BFF OIDC proxying, UI rendering, Terraform zero-idle policy, and repository hygiene.
   - **Boundary Value Analysis & Adversarial Inputs (Tier 2)**: Targets edge conditions—malformed/expired/wrong-audience JWTs, trailing-slash audience mismatches, zero-denominator budgets, negative credit memos, path-traversal `doc_id`s, prompt-injection attempts, oversized payloads, unreachable upstream `502` UI handling, and negative HCL/repo fixtures.
   - **Pairwise Cross-Feature Integration (Tier 3)**: Tests interactions across feature boundaries (`IAM × A2A`, `IAM × BFF`, `A2A × Financial MCP`, `A2A × Compliance MCP`, `Financial × Compliance`, `Orchestrator × Agents`, `BFF × UI`, `Terraform × Live Security Posture`, `UI × Orchestrator`).
   - **Real-World Workload & Chaos Scenarios (Tier 4)**: Exercises full end-to-end enterprise workflows in real headless Chromium (`WEB_URL -> BFF -> OIDC -> Orchestrator -> A2A -> Financial/Compliance MCP -> Vertex AI Gemini / GCS / Secret Manager -> Chrome UI`) plus concurrent BFF load and security lockdown probing.
3. **Dual-Mode Honesty Rules (Anti-Cheat Guarantee)**:
   - `live` mode (`-m "live_e2e or static_repo"`) runs **strictly** against real deployed `ORCHESTRATOR_URL`, `FINANCIAL_AGENT_URL`, `COMPLIANCE_AGENT_URL`, and `WEB_URL`. Missing/invalid URLs or attempts to import `_harness` trigger an immediate fail-fast exit (`returncode = 2`).
   - `self-verify` mode (`-m self_verify`) explicitly deselects all `live_e2e` and `static_repo` tests so mocks **never** masquerade as passing live tests. It validates collection invariants, tier counts, schema/auth/policy/hygiene logic (positive + fault-injected negative cases), and real Chromium Playwright assertions against local ephemeral HTML pages.
   - `static-infra` mode (`-m static_repo`) validates Terraform HCL zero-idle policy (`F8-TF-ZERO-IDLE`) and repository/asset hygiene (`F9-HYGIENE-ASSETS`) against the on-disk repository without requiring live Cloud Run/Vercel endpoints.

---

## 2. Feature Inventory & Full Traceability Matrix (`PROJECT.md` Rows 1–11)

Every active Project 1 row in `PROJECT.md § Feature Inventory` (rows 1–11; rows 12–13 are `GATED-P2` / `GATED-P3` and explicitly out of scope) maps to the 9 E2E feature areas below:

| `PROJECT.md` Row | System Feature | E2E Feature ID(s) | Verification Mode | Tier 1 | Tier 2 | Tier 3 | Tier 4 |
|---|---|---|---|---:|---:|---|---|
| **1** | Local Tooling & Auth Bootstrap (`uv`, `pnpm`, `terraform`, `gcloud`, `vercel`, `gh`) | Pre-flight Gate + `F9-HYGIENE-ASSETS` | `live` / `static-infra` | ✓ | ✓ | — | — |
| **2** | Terraform GCP Provisioning ($0 Idle, private IAM, 4 SAs, 3 Cloud Run v2) | `F8-TF-ZERO-IDLE`, `F1-IAM` | `static-infra` + `live_e2e` | ✓ | ✓ | ✓ | ✓ |
| **3** | Synthetic Enterprise Sample Docs & Compliance Policy Rules | `F3-FIN-MCP`, `F4-COMP-MCP`, `F5-ORCH-VERTEX`, `F9-HYGIENE-ASSETS` | `static-infra` + `live_e2e` | ✓ | ✓ | ✓ | ✓ |
| **4** | Financial Analysis A2A Agent + MCP Server (`MCPServer` stdio + GCS + ratios) | `F1-IAM`, `F2-A2A-DISC`, `F3-FIN-MCP` | `live_e2e` | ✓ | ✓ | ✓ | ✓ |
| **5** | Audit & Compliance A2A Agent + MCP Server (`MCPServer` + Secret Manager + GCS) | `F1-IAM`, `F2-A2A-DISC`, `F4-COMP-MCP` | `live_e2e` | ✓ | ✓ | ✓ | ✓ |
| **6** | ADK + FastAPI Orchestrator + OIDC A2A Client + Vertex AI (`gemini-3.8-flash`) | `F1-IAM`, `F2-A2A-DISC`, `F5-ORCH-VERTEX` | `live_e2e` | ✓ | ✓ | ✓ | ✓ |
| **7** | Next.js Web UI & Server-Side OIDC BFF (Node.js Fluid Compute, zero browser creds) | `F6-BFF-OIDC`, `F7-WEB-UI` | `live_e2e` (HTTP + Playwright) | ✓ | ✓ | ✓ | ✓ |
| **8** | Opaque-Box E2E Test Suite (Tiers 1–4) | `tests/e2e_suite/**` (`self_verify` + `live_e2e`) | `self-verify` + `live` | ✓ | ✓ | ✓ | ✓ |
| **9** | Live Cloud Build + GCP + Vercel Deployment | Cross-cutting Live Gate (`F1`–`F7`) | `live` | ✓ | ✓ | ✓ | ✓ |
| **10** | Public GitHub Repo & Secret Hygiene (`0` leaked secrets, `.gitignore`, `pnpm` exclusively) | `F9-HYGIENE-ASSETS` | `static-infra` + `live` | ✓ | ✓ | — | — |
| **11** | Video Presentation Assets & Chrome Verification | `F7-WEB-UI` (Chrome 0-error), `F9-HYGIENE-ASSETS` | `static-infra` + `live` | ✓ | ✓ | ✓ | ✓ |
| **12–13** | Project 2 (`GATED-P2`) & Project 3 (`GATED-P3`) | **Out of Scope (Gated)** | N/A | — | — | — | — |

### E2E Feature Areas (`F1`–`F9`)

| Feature ID | Name | Core Contract Verified |
|---|---|---|
| `F1-IAM` | Cloud Run Private IAM Enforcement | Unauth/malformed/access-token/wrong-aud rejected (`401`/`403`) on all 3 services; cross-SA least-privilege (`vercel-bff-invoker` rejected on specialized agents). |
| `F2-A2A-DISC` | A2A Discovery & Agent Health | `GET /healthz` and `GET /.well-known/agent-card.json` (`supportedInterfaces[0].url`, `JSONRPC`, `1.0`) + `POST /` JSON-RPC (`SendMessage` & `message/send`). |
| `F3-FIN-MCP` | Financial Analysis Agent + MCP + GCS | A2A delegation trace to `financial_analysis_agent`, MCP tool execution (`list_enterprise_documents`, `read_enterprise_document`, `compute_financial_ratios`), variance/ratio accuracy. |
| `F4-COMP-MCP` | Audit & Compliance Agent + MCP + Secret Manager | A2A delegation trace to `audit_compliance_agent`, Secret Manager policy `adk-compliance-policy-rules`, control matrix evaluation, violation detection, secret non-leakage. |
| `F5-ORCH-VERTEX` | Orchestrator ADK + Vertex AI Gemini | `/api/scenarios`, `/api/analyze` strict `AnalyzeResponse` schema, `gemini-3.8-flash` / `global` (rejecting `gemini-2.0-*`/`2.5-*`), `security_posture`, optional GCS report URI. |
| `F6-BFF-OIDC` | Vercel Next.js BFF Server-Side OIDC | `/api/health`, `/api/scenarios`, `/api/analyze` proxied via `google-auth-library`, Zod `400`/`422` validation, sanitized upstream errors, zero creds in HTML/JS/headers. |
| `F7-WEB-UI` | Next.js Web UI & Browser E2E (Playwright) | Headless Chromium DOM rendering, 1-click scenarios, A2A trace/report display, 0 `console.error`, 0 `pageerror`, 0 `>=400` responses, 0 direct `*.run.app` browser calls. |
| `F8-TF-ZERO-IDLE` | Terraform Zero-Idle-Cost & Infra Policy | `python-hcl2` AST + optional `terraform validate`: `min_instance_count=0`, `max_instance_count<=2`, `deletion_protection=false`, zero `allUsers`/`allAuthenticatedUsers`, zero always-on paid endpoints. |
| `F9-HYGIENE-ASSETS` | Repo Secret Hygiene, Tooling & Video Assets | Zero leaked secrets/keys, `.gitignore` rules, `NEXT_PUBLIC_*` absence, zero retired models / `FastMCP`, `pnpm`-only JS tooling & `pnpm-lock.yaml` enforcement, AST opaque-box check, `docs/VIDEO_SCRIPT.md`, `docs/DEMO_WALKTHROUGH.md`, `data/synthetic/*.json`. |

---

## 3. Test Architecture

### 3.1 Runner & Dependencies
- **Python**: `>=3.12,<3.13` managed via `uv` (`[tool.uv] package = false`) with pinned `uv.lock` (`uv sync --frozen`).
- **Packages**: `httpx>=0.28.1`, `google-auth[requests]>=2.38.0`, `pytest>=8.3.0`, `playwright>=1.50.0`, `pytest-playwright>=0.7.0`, `pydantic>=2.10.0`, `python-hcl2>=6.1.1`.
- **Shell Runner**: `tests/e2e_suite/run_e2e.ps1` — strictly **Windows PowerShell 5.1** compatible (no `&&`, `||`, `??`, `?:`; `$ErrorActionPreference` guarded around native `uv` calls).
- **Package Manager Policy**: Python dependencies managed strictly via `uv`; all JS/TS tooling in the repository uses `pnpm` exclusively (`pnpm install`, `pnpm build`, `pnpm dev`, `pnpm test`, `pnpm-lock.yaml`).

### 3.2 Environment Variables

| Variable | Required In | Purpose |
|---|---|---|
| `ORCHESTRATOR_URL` | `live` | Base URL of `adk-orchestrator` Cloud Run service (exact origin, no trailing `/`). |
| `FINANCIAL_AGENT_URL` | `live` | Base URL of `adk-financial-agent` Cloud Run service (no trailing `/`). |
| `COMPLIANCE_AGENT_URL` | `live` | Base URL of `adk-compliance-agent` Cloud Run service (no trailing `/`). |
| `WEB_URL` | `live` | Base URL of Vercel Next.js application (no trailing `/`). |
| `GCP_SA_KEY_JSON` / `GOOGLE_APPLICATION_CREDENTIALS` | `live` (optional if ADC/impersonation used) | Service account JSON path or raw JSON for minting OIDC ID tokens (`aud = base_url`). |
| `E2E_IMPERSONATE_SA` / `E2E_AGENT_IMPERSONATE_SA` | `live` (optional) | Target SA email for IAM impersonation (`adk-orchestrator` SA for direct agent A2A tests). |
| `E2E_BFF_SA_KEY_JSON` | `live` (optional) | `vercel-bff-invoker` SA key to verify `403` isolation against specialized agents. |
| `E2E_OAUTH_ACCESS_TOKEN` | `live` (optional) | OAuth2 `ya29.*` access token for negative `401` IAM boundary verification. |
| `VERCEL_AUTOMATION_BYPASS_SECRET` | `live` (optional) | Optional bypass header for Vercel Preview deployments. |
| `E2E_ALLOW_LOCALHOST` | `live` (optional) | Set to `1` (or pass `-AllowLocalhost` to `run_e2e.ps1`) to test local services before deploy. |
| `E2E_STRICT_LIVE` | `live` (optional) | Set to `1` to fail instead of skip if optional impersonation/cross-SA test creds are absent. |

### 3.3 Directory Layout

```text
tests/e2e_suite/
├── pyproject.toml
├── uv.lock
├── pytest.ini
├── TEST_PLAN.md                 # Exact mirror of worker_r1_1/TEST_INFRA.md
├── run_e2e.ps1                  # Windows PowerShell 5.1 runner (-Mode live | self-verify | static-infra)
├── conftest.py                  # Anti-cheat live guard, shared clients, OIDC minter, Playwright browser
├── lib/
│   ├── __init__.py
│   ├── config.py                # Strict URL normalization & mode configuration
│   ├── oidc_client.py           # SA key / impersonation / gcloud OIDC ID token minter + httpx client
│   ├── schemas.py               # Pydantic v2 contracts (AgentCard, Healthz, Scenarios, AnalyzeResponse)
│   ├── tf_policy.py             # python-hcl2 AST policy validator + optional terraform validate
│   ├── repo_hygiene.py          # Secret scan, .gitignore, NEXT_PUBLIC_*, retired models, AST import, pnpm check
│   └── ui_runner.py             # Sync Playwright runner (console, pageerror, network >=400, bundle/DOM leak checks)
├── _harness/
│   ├── __init__.py
│   └── mock_stack.py            # Ephemeral local mock servers (strictly forbidden in live_e2e mode)
├── test_tier1_iam.py
├── test_tier1_a2a_discovery.py
├── test_tier1_financial_mcp.py
├── test_tier1_compliance_mcp.py
├── test_tier1_orchestrator.py
├── test_tier1_bff_oidc.py
├── test_tier1_web_ui.py
├── test_tier1_terraform_policy.py
├── test_tier1_hygiene_assets.py
├── test_tier2_boundaries.py
├── test_tier3_pairwise.py
├── test_tier4_scenarios.py
└── test_self_verify.py
```

---

## 4. Coverage Thresholds & Tier Breakdown

| Tier | Description | Target Minimum | Implemented Count | Markers |
|---|---|---:|---:|---|
| **Tier 1** | Feature Coverage (`F1`–`F9`) | `>= 5` per feature (`>= 45`) | **49** (`5–6` per feature) | `tier1`, `live_e2e` / `static_repo` |
| **Tier 2** | Boundary, Negative & Adversarial Cases | `>= 5` per feature (`>= 45`) | **46** (`5–6` per feature) | `tier2`, `live_e2e` / `static_repo` |
| **Tier 3** | Cross-Feature Pairwise Combinations | `>= 8` | **9** | `tier3`, `live_e2e` |
| **Tier 4** | Real-World Enterprise Scenarios | `>= 5` | **6** | `tier4`, `live_e2e` |
| **Self-Verify** | Offline Harness, Fault Injection & Chromium Check | Full coverage of libs & tier invariants | **10** | `self_verify` |

---

## 5. Tier 4 Real-World Application Scenarios

1. **`T4-SC-01` — Q3 Cloud Vendor Spend Review (Full Browser E2E)**:
   - User opens `WEB_URL` in Chrome, selects `q3_cloud_vendor_review`, runs analysis -> BFF mints OIDC token -> Orchestrator delegates via A2A to Financial (`read_enterprise_document`, `compute_financial_ratios`) and Compliance (`adk-compliance-policy-rules`) -> GCS report persisted -> UI renders `executive_summary`, `overall_risk_rating`, `a2a_trace`, and `security_posture` with `0` console errors, `0` page errors, `0` failed requests (`>=400`), and `0` direct `*.run.app` calls.
2. **`T4-SC-02` — Series B Revenue Audit (Live Multi-Doc Variance & Provenance)**:
   - Executes `series_b_revenue_audit` end-to-end via BFF -> verifies distinct revenue recognition metrics, GCS source provenance (`series_b_revenue_audit.json`), Secret Manager policy citation, and `gemini-3.8-flash` / `global` provenance.
3. **`T4-SC-03` — Treasury Controls Memo (Policy Violation Detection in Chrome)**:
   - Runs `treasury_controls_memo` in Playwright Chromium -> verifies dual-approval control violation surfaced in `compliance_audit` (`compliant == false`, non-empty `violations`), remediation `recommendations`, and both A2A trace steps rendered cleanly.
4. **`T4-SC-04` — Ad-Hoc Clean Enterprise Procurement Memo**:
   - Submits compliant ad-hoc procurement memo (dual CFO/VP sign-off, competitive 3-bid RFP, within budget) -> verifies `compliant == true`, `violations == []`, and `overall_risk_rating in {"LOW", "MEDIUM"}`.
5. **`T4-SC-05` — Concurrent BFF Requests & High-Risk Sole-Source Expenditure**:
   - Fires concurrent `/api/analyze` BFF requests (including a `$480,000` sole-source `+62%` variance expenditure without dual sign-off) -> verifies independent unique `run_id`s, zero cross-request state bleed, `compliant == false`, and `HIGH`/`CRITICAL` risk rating.
6. **`T4-SC-06` — Security Auditor Lockdown & Zero-Leakage Verification**:
   - Simultaneously probes all 3 Cloud Run services unauthenticated (`401`/`403`) while executing a full Playwright browser workflow on `WEB_URL` and asserting zero leaked secrets in HTML, client JS bundles, `localStorage`, `sessionStorage`, cookies, `__NEXT_DATA__`, or HTTP headers.

---

## 6. Recommended UI Semantic Selectors & `data-testid` Hooks (for M4 Alignment)

`lib/ui_runner.py` resolves elements using accessible ARIA roles/labels (`get_by_role`, `get_by_label`, `<select>`, `<textarea>`, `<button>`) **and** prefers the following `data-testid` hooks if provided by `web/`:

- `data-testid="scenario-select"` — Scenario `<select>` dropdown (`q3_cloud_vendor_review`, `series_b_revenue_audit`, `treasury_controls_memo`)
- `data-testid="prompt-input"` — Prompt `<textarea>` or `<input>`
- `data-testid="adhoc-doc-input"` — Optional ad-hoc document text `<textarea>`
- `data-testid="analyze-submit"` — Primary Run / Analyze `<button>`
- `data-testid="executive-summary"` — Executive summary container
- `data-testid="risk-rating"` — Overall risk rating badge (`LOW` | `MEDIUM` | `HIGH` | `CRITICAL`)
- `data-testid="financial-analysis"` — Financial analysis results panel
- `data-testid="compliance-audit"` — Compliance audit & violations panel
- `data-testid="a2a-trace"` — A2A & MCP delegation trace viewer
- `data-testid="security-posture"` — Architecture & zero-idle security posture panel (`min_instances: 0`, `max_instances: 2`, `private-oidc-enforced`)
- `data-testid="error-banner"` — Sanitized error alert banner (`role="alert"`)
