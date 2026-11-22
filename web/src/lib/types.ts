export type RiskRating = 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL';

export interface ScenarioItem {
  id: string;
  title: string;
  doc_id: string;
  gcs_uri: string;
  description: string;
  default_prompt: string;
}

export interface ScenariosResponse {
  scenarios: ScenarioItem[];
}

export interface AnalyzeRequest {
  scenario_id: string;
  doc_id?: string;
  prompt: string;
  document_text?: string;
  persist_report?: boolean;
}

export type MetricValue = string | number | boolean | null;

export interface StructuredFinding {
  title?: string;
  name?: string;
  control_id?: string;
  severity?: string;
  status?: string;
  detail?: string;
  description?: string;
  reason?: string;
  remediation?: string;
  [key: string]: unknown;
}

export type FindingItem = string | StructuredFinding;

export interface FinancialAnalysis {
  summary: string;
  key_metrics: Record<string, MetricValue>;
  anomalies: FindingItem[];
  sources: string[];
}

export interface ComplianceAudit {
  summary: string;
  policy_id: string;
  controls_evaluated: FindingItem[];
  violations: FindingItem[];
  compliant: boolean;
}

export interface A2ATraceStep {
  step: number;
  caller: string;
  target: string;
  protocol: string;
  auth: string;
  mcp_tools: string[];
  latency_ms: number;
  status: string;
}

export interface GcpProvenance {
  vertex_ai_model: string;
  vertex_ai_location: string;
  gcs_bucket: string;
  report_gcs_uri: string | null;
  secret_manager_policy: string;
}

export interface SecurityPosture {
  cloud_run_iam: string;
  min_instances: number;
  max_instances: number;
}

export interface AnalyzeResponse {
  run_id: string;
  timestamp_utc: string;
  scenario_id: string;
  doc_id: string;
  executive_summary: string;
  overall_risk_rating: RiskRating;
  financial_analysis: FinancialAnalysis;
  compliance_audit: ComplianceAudit;
  recommendations: FindingItem[];
  a2a_trace: A2ATraceStep[];
  gcp_provenance: GcpProvenance;
  security_posture: SecurityPosture;
}

export interface HealthResponse {
  status: 'ok' | 'degraded' | 'error';
  service: string;
  bff: {
    runtime: 'nodejs';
    auth_mode: 'oidc-sa' | 'local-dev' | 'unconfigured';
    orchestrator_configured: boolean;
  };
  orchestrator?: {
    status: string;
    service: string;
    agents?: {
      financial?: string;
      compliance?: string;
    };
  };
  error?: string;
  checked_at_utc: string;
}
