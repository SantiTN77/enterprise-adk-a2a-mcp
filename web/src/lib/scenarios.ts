import type { ScenarioItem } from './types';

export const DEFAULT_SCENARIOS: ScenarioItem[] = [
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

export interface ScenarioBadgeMeta {
  company: string;
  expectedSignal: string;
  tone: 'warning' | 'success' | 'critical';
}

export const SCENARIO_UI_META: Record<string, ScenarioBadgeMeta> = {
  q3_cloud_vendor_review: {
    company: 'Meridian Retail Analytics Corp.',
    expectedSignal: 'HIGH RISK · +28% Variance / Dual-Approval Gap',
    tone: 'warning',
  },
  series_b_revenue_audit: {
    company: 'Northwind Cloud Robotics Inc.',
    expectedSignal: 'LOW RISK · Clean ASC 606 / SOC2 Baseline',
    tone: 'success',
  },
  treasury_controls_memo: {
    company: 'Helios FinTech Payments Inc.',
    expectedSignal: 'CRITICAL RISK · SoD Self-Approval & Unvetted Rail',
    tone: 'critical',
  },
};
