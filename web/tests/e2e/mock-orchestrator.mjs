import http from 'node:http';
import { randomUUID } from 'node:crypto';

const PORT = Number(process.env.MOCK_ORCHESTRATOR_PORT || 18080);

const SCENARIOS = [
  {
    id: 'q3_cloud_vendor_review',
    title: 'Q3 Cloud & AI Vendor Spend Review',
    doc_id: 'samples/q3_cloud_vendor_review.json',
    gcs_uri: 'gs://enterprise-adk-docs-gen-lang-client-0527325883/samples/q3_cloud_vendor_review.json',
    description:
      'FY2026 Q3 cloud infrastructure and AI vendor spend review for Meridian Retail Analytics Corp. — exhibits +28.00% budget variance overrun and missing Finance dual-approval on a $660k GPU amendment.',
    default_prompt:
      'Analyze financial variance and audit compliance controls for Q3 vendor spend in samples/q3_cloud_vendor_review.json.',
  },
  {
    id: 'series_b_revenue_audit',
    title: 'Series B Q3 Revenue Recognition & Audit Readiness',
    doc_id: 'samples/series_b_revenue_audit.json',
    gcs_uri: 'gs://enterprise-adk-docs-gen-lang-client-0527325883/samples/series_b_revenue_audit.json',
    description:
      'FY2026 Q3 ASC 606 revenue audit package for Northwind Cloud Robotics Inc. — cleanly compliant baseline with +1.43% spend variance, full dual approvals, verified vendor SOC2 reports, and intact SoD.',
    default_prompt:
      'Analyze financial ratios, ASC 606 revenue recognition quality, and SOX/SOC2 compliance controls for samples/series_b_revenue_audit.json.',
  },
  {
    id: 'treasury_controls_memo',
    title: 'Treasury Wire Controls & Vendor Exception Memo',
    doc_id: 'samples/treasury_controls_memo.json',
    gcs_uri: 'gs://enterprise-adk-docs-gen-lang-client-0527325883/samples/treasury_controls_memo.json',
    description:
      'FY2026 Q3 treasury disbursement and vendor onboarding review for Helios FinTech Payments Inc. — contains critical Segregation of Duties self-approval breach, unverified/expired vendor SOC2 reports, missing dual approvals, +22.00% overrun, and aged unreconciled suspense.',
    default_prompt:
      'Perform a full financial risk and SOX/SOC2 audit evaluation of treasury wire controls and vendor compliance in samples/treasury_controls_memo.json.',
  },
];

function buildAnalyzePayload(body) {
  const scenarioId = body.scenario_id || 'q3_cloud_vendor_review';
  const docId = body.doc_id || `samples/${scenarioId}.json`;
  const runId = randomUUID();
  const persistReport = body.persist_report !== false;

  const isTreasury = scenarioId === 'treasury_controls_memo';
  const isSeriesB = scenarioId === 'series_b_revenue_audit';

  const overallRiskRating = isTreasury ? 'CRITICAL' : isSeriesB ? 'LOW' : 'HIGH';

  return {
    run_id: runId,
    timestamp_utc: new Date().toISOString(),
    scenario_id: scenarioId,
    doc_id: docId,
    executive_summary: isTreasury
      ? 'CRITICAL risk detected in Helios FinTech Payments Inc. Q3 treasury controls: Segregation of Duties self-approval breach on $840k wire WIRE-2026-0891, unvetted vendor rail without SOC2 Type II/DPA, +22.00% budget overrun, and $185k aged unreconciled suspense.'
      : isSeriesB
        ? 'LOW risk verified for Northwind Cloud Robotics Inc. Q3 Series B audit package: +1.43% budget variance within 10% threshold, ASC 606 five-step verification intact, dual approvals complete, and all vendor SOC2 Type II reports current.'
        : 'HIGH risk identified in Meridian Retail Analytics Corp. Q3 Cloud & AI Vendor Spend Review: +28.00% budget variance ($896k overrun driven by uncommitted GPU burst scaling) without waiver and missing Finance dual-approval on $660k amendment AMD-2026-Q3-09.',
    overall_risk_rating: overallRiskRating,
    financial_analysis: {
      summary: isTreasury
        ? 'Operating cash flow is -$420,000 with +22.00% ($462,000) budget variance and $185,000 in unreconciled suspense.'
        : isSeriesB
          ? 'Revenue reached $18.45M with 78.40% gross margin, $5.10M operating cash flow, and +1.43% budget variance.'
          : 'Actual cloud spend reached $4,096,000 vs $3,200,000 budget (+28.00% / $896,000 variance), led by +60.00% GPU inference overrun.',
      key_metrics: isTreasury
        ? {
            revenue_usd: 9800000,
            budget_variance_pct: 22.0,
            operating_cash_flow_usd: -420000,
            unreconciled_suspense_balance_usd: 185000,
          }
        : isSeriesB
          ? {
              revenue_usd: 18450000,
              budget_variance_pct: 1.43,
              operating_cash_flow_usd: 5100000,
              gross_margin_pct: 78.4,
            }
          : {
              revenue_usd: 12600000,
              budgeted_spend_usd: 3200000,
              actual_spend_usd: 4096000,
              budget_variance_pct: 28.0,
            },
      anomalies: isSeriesB
        ? []
        : isTreasury
          ? ['+22.00% budget variance without waiver', 'Negative operating cash flow (-$420k)', '$185k unreconciled suspense aged 47 days']
          : ['+28.00% overall cloud spend overrun ($896k) exceeding 25% critical threshold', 'GPU inference cluster utilization at 46.2% with 61.5% uncommitted on-demand spend'],
      sources: [`gs://enterprise-adk-docs-gen-lang-client-0527325883/${docId}`],
    },
    compliance_audit: {
      summary: isSeriesB
        ? 'All 5 controls in ENT-COMP-POLICY-2026.3 passed with zero SOX-404, SOC2-CC6, or ASC-606 exceptions.'
        : isTreasury
          ? 'Multiple CRITICAL and HIGH control failures across TRES-SOD-04, SOC2-VEND-03, SOX-APPR-02, FIN-VAR-01, and SOX-REV-05.'
          : 'Failed FIN-VAR-01 (+28% variance without waiver) and SOX-APPR-02 (single VP_ENGINEERING approval only on $660k AMD-2026-Q3-09).',
      policy_id: 'ENT-COMP-POLICY-2026.3',
      controls_evaluated: [
        { control_id: 'FIN-VAR-01', name: 'Budget Variance Threshold Control', status: isSeriesB ? 'PASS' : 'FAIL', severity: 'HIGH' },
        { control_id: 'SOX-APPR-02', name: 'High-Value Expenditure & Wire Dual Approval', status: isSeriesB ? 'PASS' : 'FAIL', severity: 'HIGH' },
        { control_id: 'SOC2-VEND-03', name: 'Third-Party Vendor SOC2 Type II & DPA Verification', status: isTreasury ? 'FAIL' : 'PASS', severity: 'CRITICAL' },
        { control_id: 'TRES-SOD-04', name: 'Treasury & Disbursement Segregation of Duties (SoD)', status: isTreasury ? 'FAIL' : 'PASS', severity: 'CRITICAL' },
        { control_id: 'SOX-REV-05', name: 'ASC 606 Revenue Recognition & Period-Close Evidence', status: isTreasury ? 'FAIL' : 'PASS', severity: 'MEDIUM' },
      ],
      violations: isSeriesB
        ? []
        : isTreasury
          ? [
              { control_id: 'TRES-SOD-04', severity: 'CRITICAL', detail: 'emp-tres-701 prepared, self-approved, and released $840k wire WIRE-2026-0891.' },
              { control_id: 'SOC2-VEND-03', severity: 'CRITICAL', detail: 'NovaRail Clearing Partners lacks SOC2 Type II and DPA; Kestrel FX SOC2 expired 2026-03-31.' },
            ]
          : [
              { control_id: 'FIN-VAR-01', severity: 'HIGH', detail: 'Budget variance 28.0% exceeds 10.0% policy limit with no CFO waiver.' },
              { control_id: 'SOX-APPR-02', severity: 'HIGH', detail: 'Amendment AMD-2026-Q3-09 ($660,000) lacks second Finance leadership approver.' },
            ],
      compliant: isSeriesB,
    },
    recommendations: isSeriesB
      ? ['Maintain quarterly ASC 606 five-step sampling and automated vendor SOC2 expiry monitoring.']
      : isTreasury
        ? [
            'Revoke conflicting treasury RBAC privileges for emp-tres-701 and disable emergency self-override.',
            'Freeze NovaRail Clearing Partners settlement rail until valid SOC2 Type II and DPA are executed.',
            'Reconcile $185,000 aged suspense balance prior to Q3 period close.',
          ]
        : [
            'Obtain retroactive CFO budget variance waiver and convert uncommitted GPU burst to 1-year reserved capacity.',
            'Require dual Finance leadership approval (CFO / VP_FINANCE / CONTROLLER) on amendment AMD-2026-Q3-09.',
          ],
    a2a_trace: [
      {
        step: 1,
        caller: 'adk-orchestrator',
        target: 'financial_analysis_agent',
        protocol: 'A2A',
        auth: 'CloudRun-OIDC-IAM',
        mcp_tools: ['list_enterprise_documents', 'read_enterprise_document', 'compute_financial_ratios'],
        latency_ms: 842,
        status: 'SUCCESS',
      },
      {
        step: 2,
        caller: 'adk-orchestrator',
        target: 'audit_compliance_agent',
        protocol: 'A2A',
        auth: 'CloudRun-OIDC-IAM',
        mcp_tools: ['get_compliance_policy', 'read_enterprise_document', 'evaluate_control_matrix'],
        latency_ms: 765,
        status: 'SUCCESS',
      },
    ],
    gcp_provenance: {
      vertex_ai_model: 'gemini-3.8-flash',
      vertex_ai_location: 'global',
      gcs_bucket: 'enterprise-adk-docs-gen-lang-client-0527325883',
      report_gcs_uri: persistReport
        ? `gs://enterprise-adk-docs-gen-lang-client-0527325883/reports/${runId}.json`
        : null,
      secret_manager_policy: 'adk-compliance-policy-rules',
    },
    security_posture: {
      cloud_run_iam: 'private-oidc-enforced',
      min_instances: 0,
      max_instances: 2,
    },
  };
}

const server = http.createServer((req, res) => {
  const url = req.url || '/';

  if (req.method === 'GET' && (url === '/healthz' || url === '/health' || url === '/api/health')) {
    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.end(
      JSON.stringify({
        status: 'ok',
        service: 'adk-orchestrator',
        agents: {
          financial: 'http://127.0.0.1:8001',
          compliance: 'http://127.0.0.1:8002',
        },
      }),
    );
    return;
  }

  if (req.method === 'GET' && url === '/api/scenarios') {
    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({ scenarios: SCENARIOS }));
    return;
  }

  if (req.method === 'POST' && url === '/api/analyze') {
    const chunks = [];
    req.on('data', (chunk) => chunks.push(chunk));
    req.on('end', () => {
      try {
        const parsed = JSON.parse(Buffer.concat(chunks).toString('utf8'));
        res.writeHead(200, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify(buildAnalyzePayload(parsed)));
      } catch {
        res.writeHead(400, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ detail: 'Invalid JSON request body' }));
      }
    });
    return;
  }

  res.writeHead(404, { 'Content-Type': 'application/json' });
  res.end(JSON.stringify({ detail: 'Not found' }));
});

server.listen(PORT, '127.0.0.1', () => {
  console.log(`[mock-orchestrator] listening on http://127.0.0.1:${PORT}`);
});
