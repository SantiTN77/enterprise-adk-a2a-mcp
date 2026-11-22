# Video Presentation Script (3:00 Runtime)

**Target Duration**: 3 minutes 00 seconds (2.5–3.5 minute portfolio showcase)  
**Audience**: Engineering Managers, Staff/Principal Architects, Hiring Panels  

---

## Scene 1 — Hook & Enterprise Problem (0:00 – 0:25)

| Time | Visual Cue | Spoken Narration |
|---|---|---|
| `0:00` | Show the live **Enterprise Multi-Agent Risk & Compliance Console** in Chrome (`1440×900`), highlighting the header and Zero-Trust Security Posture banner. | "Most AI agent demos wire a single LLM straight to a browser with hardcoded API keys and always-on servers. In real enterprise finance and audit workflows, you need strict service isolation, deterministic compliance controls, and zero idle cloud burn." |
| `0:15` | Hover over the 5-hop architecture strip (`Browser -> Vercel OIDC BFF -> Private Cloud Run -> A2A + OIDC -> Stdio MCPServer`). | "This is an enterprise multi-agent risk and compliance system built with Google ADK, the Agent-to-Agent protocol, and MCP on private Cloud Run—fronted by a Next.js App Router BFF on Vercel." |

---

## Scene 2 — Zero-Trust Architecture & `$0` Idle Cost (0:25 – 1:05)

| Time | Visual Cue | Spoken Narration |
|---|---|---|
| `0:25` | Switch briefly to `README.md` Mermaid diagram & Terraform `cloud_run.tf` / `iam.tf` snippet (`min_instance_count = 0`, `max_instance_count = 2`, no `allUsers`). | "Every backend service runs on Cloud Run v2 with `min_instance_count = 0` and `max_instance_count = 2` for a true zero-dollar idle footprint. More importantly, zero services allow public `allUsers` traffic." |
| `0:45` | Show `web/src/lib/gcp-bff.ts` (`getIdTokenClient`) and terminal running `curl -i <CLOUD_RUN_URL>/healthz` returning `401/403`. | "Direct unauthenticated calls to Cloud Run fail closed with 401 or 403. Instead, the Vercel Node.js Fluid Compute BFF mints a scoped Google OIDC ID token server-side using `google-auth-library`—no GCP credentials ever touch the browser bundle." |

---

## Scene 3 — Live 1-Click Multi-Agent Execution (1:05 – 2:10)

| Time | Visual Cue | Spoken Narration |
|---|---|---|
| `1:05` | Return to Chrome UI. Highlight the 3 synthetic enterprise scenarios and click **Run 1-Click** on **Q3 Cloud & AI Vendor Spend Review**. | "Let's run our Q3 Cloud and AI Vendor Spend Review for Meridian Retail Analytics. Our Next.js BFF validates the payload with Zod and invokes the private ADK orchestrator." |
| `1:20` | Scroll to **Multi-Agent A2A & MCP Execution Trace** as results populate. Point to Step 1 (`financial_analysis_agent`) and Step 2 (`audit_compliance_agent`). | "In the execution trace, you can see the orchestrator delegating over A2A v1.0 with refreshing `CloudRun-OIDC-IAM` tokens to two specialized agents. Each agent spawns an embedded stdio `MCPServer`—keeping GCS financial data and Secret Manager policy rules strictly compartmentalized." |
| `1:45` | Scroll to **Executive Risk & Compliance Report** (`HIGH RISK` badge, `+28.00%` variance, `FIN-VAR-01` & `SOX-APPR-02` violations) and GCP Provenance strip (`gemini-3.8-flash (global)`). | "Using Vertex AI `gemini-3.8-flash` on the `global` endpoint paired with deterministic MCP ratio and control-matrix tools, the system flags a 28% budget overrun and a missing Finance dual-approval on a $660,000 GPU amendment." |
| `2:00` | Click **Run 1-Click** on **Treasury Wire Controls & Vendor Exception Memo** (`CRITICAL RISK`). | "Switching to the Helios FinTech treasury memo immediately surfaces a critical Segregation of Duties self-approval breach on an $840,000 wire and an unvetted payment rail missing SOC2 Type II attestation." |

---

## Scene 4 — End-to-End Verification & Clean Browser Proof (2:10 – 2:45)

| Time | Visual Cue | Spoken Narration |
|---|---|---|
| `2:10` | Click **Show Raw JSON** in the report panel, then open Chrome DevTools Console & Network tab showing `200 OK` on `/api/analyze` and zero console errors. | "Inspecting the raw JSON payload and Chrome DevTools confirms structured end-to-end provenance—including the persisted GCS report URI—with zero leaked OIDC tokens, zero console errors, and zero failed network requests." |
| `2:30` | Show terminal running `pnpm run typecheck && pnpm run lint && pnpm exec playwright test` passing cleanly. | "Automated unit tests, TypeScript checks, and Playwright browser tests verify the BFF validation, OIDC audience normalization, and UI accessibility end-to-end." |

---

## Scene 5 — Closing & Repository (2:45 – 3:00)

| Time | Visual Cue | Spoken Narration |
|---|---|---|
| `2:45` | Show GitHub repository (`enterprise-adk-a2a-mcp`) with clean commit history, `infra/terraform`, `services/`, `web/`, and `docs/`. | "The full Terraform infrastructure, ADK A2A agents, stdio MCP servers, and isolated Vercel Next.js BFF are open-source and reproducible in the repository linked below. Thanks for watching." |
