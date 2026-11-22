'use client';

import { useState } from 'react';
import {
  AlertOctagon,
  AlertTriangle,
  CheckCircle2,
  ClipboardCheck,
  Code2,
  Copy,
  FileSpreadsheet,
  ListChecks,
  ShieldAlert,
  ShieldCheck,
} from 'lucide-react';
import type { AnalyzeResponse, RiskRating } from '@/lib/types';
import { formatMetricLabel, formatMetricValue, normalizeFindingItem } from './finding-utils';

interface ExecutiveReportPanelProps {
  report: AnalyzeResponse;
}

function getRiskBadgeConfig(rating: RiskRating) {
  switch (rating) {
    case 'LOW':
      return {
        label: 'LOW RISK',
        classes: 'border-emerald-500/50 bg-emerald-950/70 text-emerald-200',
        Icon: ShieldCheck,
      };
    case 'MEDIUM':
      return {
        label: 'MEDIUM RISK',
        classes: 'border-sky-500/50 bg-sky-950/70 text-sky-200',
        Icon: AlertTriangle,
      };
    case 'HIGH':
      return {
        label: 'HIGH RISK',
        classes: 'border-amber-500/50 bg-amber-950/70 text-amber-200',
        Icon: ShieldAlert,
      };
    case 'CRITICAL':
      return {
        label: 'CRITICAL RISK',
        classes: 'border-red-500/50 bg-red-950/70 text-red-200',
        Icon: AlertOctagon,
      };
  }
}

export function ExecutiveReportPanel({ report }: ExecutiveReportPanelProps) {
  const [showRawJson, setShowRawJson] = useState(false);
  const [copied, setCopied] = useState(false);

  const riskConfig = getRiskBadgeConfig(report.overall_risk_rating);
  const RiskIcon = riskConfig.Icon;
  const metricEntries = Object.entries(report.financial_analysis.key_metrics ?? {});

  async function handleCopyJson() {
    try {
      await navigator.clipboard.writeText(JSON.stringify(report, null, 2));
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      setCopied(false);
    }
  }

  return (
    <section
      aria-labelledby="executive-report-heading"
      className="rounded-2xl border border-slate-800 bg-[#111827] p-5 shadow-lg"
    >
      <div className="flex flex-col gap-4 border-b border-slate-800 pb-4 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <div className="flex flex-wrap items-center gap-3">
            <h2 id="executive-report-heading" className="text-lg font-semibold text-slate-50">
              Executive Risk &amp; Compliance Report
            </h2>
            <span
              data-testid="risk-rating-badge"
              className={`inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs font-bold tracking-wide ${riskConfig.classes}`}
            >
              <RiskIcon className="h-4 w-4" aria-hidden="true" />
              <span>{riskConfig.label}</span>
            </span>
          </div>
          <p className="mt-1.5 font-mono text-xs text-slate-400">
            Run: {report.run_id} · Scenario: {report.scenario_id} · Doc: {report.doc_id} ·{' '}
            {report.timestamp_utc}
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <button
            type="button"
            onClick={() => setShowRawJson((prev) => !prev)}
            aria-expanded={showRawJson}
            aria-controls="raw-json-panel"
            className="inline-flex min-h-[48px] items-center gap-2 rounded-lg border border-slate-700 bg-slate-900 px-3.5 py-2 text-sm font-medium text-slate-100 transition-colors hover:border-slate-500 hover:bg-slate-800 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-400 focus-visible:ring-offset-2 focus-visible:ring-offset-[#111827] motion-reduce:transition-none"
          >
            <Code2 className="h-4 w-4 text-sky-300" aria-hidden="true" />
            <span>{showRawJson ? 'Hide Raw JSON' : 'Show Raw JSON'}</span>
          </button>

          <button
            type="button"
            onClick={handleCopyJson}
            aria-label="Copy full analysis JSON report to clipboard"
            className="inline-flex min-h-[48px] items-center gap-2 rounded-lg border border-slate-700 bg-slate-900 px-3.5 py-2 text-sm font-medium text-slate-100 transition-colors hover:border-slate-500 hover:bg-slate-800 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-400 focus-visible:ring-offset-2 focus-visible:ring-offset-[#111827] motion-reduce:transition-none"
          >
            {copied ? (
              <ClipboardCheck className="h-4 w-4 text-emerald-300" aria-hidden="true" />
            ) : (
              <Copy className="h-4 w-4 text-slate-300" aria-hidden="true" />
            )}
            <span>{copied ? 'Copied JSON' : 'Copy JSON'}</span>
          </button>
        </div>
      </div>

      <div className="mt-4 rounded-xl border border-slate-800 bg-[#0B101B] p-4">
        <h3 className="text-xs font-semibold uppercase tracking-wider text-sky-300">Executive Summary</h3>
        <p className="mt-2 text-sm leading-relaxed text-slate-100">{report.executive_summary}</p>
      </div>

      <div className="mt-4 grid gap-4 lg:grid-cols-2">
        {/* Financial Analysis Card */}
        <article className="rounded-xl border border-slate-800 bg-[#0B101B] p-4">
          <div className="flex items-center gap-2">
            <FileSpreadsheet className="h-5 w-5 text-sky-300" aria-hidden="true" />
            <h3 className="text-base font-semibold text-slate-50">Financial Analysis</h3>
          </div>
          <p className="mt-2 text-sm leading-relaxed text-slate-300">{report.financial_analysis.summary}</p>

          {metricEntries.length > 0 ? (
            <dl className="mt-4 grid grid-cols-2 gap-2.5">
              {metricEntries.map(([key, value]) => (
                <div key={key} className="rounded-lg border border-slate-800 bg-slate-900/70 p-2.5">
                  <dt className="text-xs text-slate-400">{formatMetricLabel(key)}</dt>
                  <dd className="mt-0.5 font-mono text-sm font-semibold text-slate-100">
                    {formatMetricValue(key, value)}
                  </dd>
                </div>
              ))}
            </dl>
          ) : null}

          <div className="mt-4">
            <h4 className="text-xs font-semibold uppercase tracking-wider text-slate-300">
              Financial Anomalies
            </h4>
            {report.financial_analysis.anomalies.length > 0 ? (
              <ul className="mt-2 space-y-2">
                {report.financial_analysis.anomalies.map((item, idx) => {
                  const normalized = normalizeFindingItem(item);
                  return (
                    <li
                      key={`${normalized.title}-${idx}`}
                      className="rounded-lg border border-amber-500/30 bg-amber-950/30 p-2.5 text-sm text-amber-100"
                    >
                      <span className="font-medium">{normalized.title}</span>
                      {normalized.detail ? (
                        <p className="mt-1 text-xs text-amber-200/90">{normalized.detail}</p>
                      ) : null}
                    </li>
                  );
                })}
              </ul>
            ) : (
              <p className="mt-2 text-xs text-emerald-300">No material financial anomalies flagged.</p>
            )}
          </div>

          {report.financial_analysis.sources.length > 0 ? (
            <div className="mt-4 border-t border-slate-800 pt-3">
              <h4 className="text-xs font-semibold uppercase tracking-wider text-slate-400">Sources</h4>
              <ul className="mt-1.5 space-y-1">
                {report.financial_analysis.sources.map((src) => (
                  <li key={src} className="break-all font-mono text-xs text-slate-300">
                    {src}
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
        </article>

        {/* Compliance & Audit Card */}
        <article className="rounded-xl border border-slate-800 bg-[#0B101B] p-4">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div className="flex items-center gap-2">
              <ShieldCheck className="h-5 w-5 text-emerald-300" aria-hidden="true" />
              <h3 className="text-base font-semibold text-slate-50">Compliance &amp; Controls Audit</h3>
            </div>
            <span
              className={`inline-flex items-center gap-1 rounded-full border px-2.5 py-0.5 text-xs font-semibold ${
                report.compliance_audit.compliant
                  ? 'border-emerald-500/40 bg-emerald-950/60 text-emerald-200'
                  : 'border-red-500/40 bg-red-950/60 text-red-200'
              }`}
            >
              {report.compliance_audit.compliant ? (
                <CheckCircle2 className="h-3.5 w-3.5" aria-hidden="true" />
              ) : (
                <AlertOctagon className="h-3.5 w-3.5" aria-hidden="true" />
              )}
              <span>{report.compliance_audit.compliant ? 'COMPLIANT' : 'NON-COMPLIANT'}</span>
            </span>
          </div>

          <p className="mt-1 font-mono text-xs text-slate-400">
            Policy ID: {report.compliance_audit.policy_id}
          </p>
          <p className="mt-2 text-sm leading-relaxed text-slate-300">{report.compliance_audit.summary}</p>

          <div className="mt-4">
            <h4 className="text-xs font-semibold uppercase tracking-wider text-slate-300">
              Controls Evaluated ({report.compliance_audit.controls_evaluated.length})
            </h4>
            {report.compliance_audit.controls_evaluated.length > 0 ? (
              <ul className="mt-2 space-y-2">
                {report.compliance_audit.controls_evaluated.map((item, idx) => {
                  const normalized = normalizeFindingItem(item);
                  return (
                    <li
                      key={`${normalized.title}-${idx}`}
                      className="rounded-lg border border-slate-800 bg-slate-900/70 p-2.5 text-sm text-slate-200"
                    >
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <span className="font-medium text-slate-100">{normalized.title}</span>
                        {normalized.badge ? (
                          <span className="rounded border border-slate-700 bg-slate-800 px-2 py-0.5 font-mono text-xs text-sky-300">
                            {normalized.badge}
                          </span>
                        ) : null}
                      </div>
                      {normalized.detail ? (
                        <p className="mt-1 text-xs text-slate-300">{normalized.detail}</p>
                      ) : null}
                    </li>
                  );
                })}
              </ul>
            ) : (
              <p className="mt-2 text-xs text-slate-400">No individual controls listed.</p>
            )}
          </div>

          <div className="mt-4">
            <h4 className="text-xs font-semibold uppercase tracking-wider text-slate-300">
              Control Violations
            </h4>
            {report.compliance_audit.violations.length > 0 ? (
              <ul className="mt-2 space-y-2">
                {report.compliance_audit.violations.map((item, idx) => {
                  const normalized = normalizeFindingItem(item);
                  return (
                    <li
                      key={`${normalized.title}-${idx}`}
                      className="rounded-lg border border-red-500/40 bg-red-950/40 p-2.5 text-sm text-red-100"
                    >
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <span className="font-semibold">{normalized.title}</span>
                        {normalized.severity ? (
                          <span className="rounded border border-red-500/40 bg-red-900/60 px-2 py-0.5 font-mono text-xs font-bold text-red-200">
                            {normalized.severity}
                          </span>
                        ) : null}
                      </div>
                      {normalized.detail ? (
                        <p className="mt-1 text-xs text-red-200/90">{normalized.detail}</p>
                      ) : null}
                    </li>
                  );
                })}
              </ul>
            ) : (
              <p className="mt-2 text-xs text-emerald-300">Zero compliance violations detected.</p>
            )}
          </div>
        </article>
      </div>

      {/* Actionable Recommendations */}
      <div className="mt-4 rounded-xl border border-slate-800 bg-[#0B101B] p-4">
        <div className="flex items-center gap-2">
          <ListChecks className="h-5 w-5 text-emerald-300" aria-hidden="true" />
          <h3 className="text-base font-semibold text-slate-50">Actionable Recommendations</h3>
        </div>
        {report.recommendations.length > 0 ? (
          <ol className="mt-3 list-decimal space-y-2 pl-5 text-sm text-slate-200">
            {report.recommendations.map((item, idx) => {
              const normalized = normalizeFindingItem(item);
              return (
                <li key={`${normalized.title}-${idx}`} className="leading-relaxed">
                  <span className="font-medium text-slate-100">{normalized.title}</span>
                  {normalized.detail ? (
                    <span className="text-slate-300"> — {normalized.detail}</span>
                  ) : null}
                </li>
              );
            })}
          </ol>
        ) : (
          <p className="mt-2 text-sm text-slate-400">No remediation actions required.</p>
        )}
      </div>

      {showRawJson ? (
        <div id="raw-json-panel" className="mt-4 rounded-xl border border-slate-800 bg-[#060911] p-4">
          <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-400">
            Raw Orchestrator JSON Response
          </h3>
          <pre className="mt-2 max-h-96 overflow-auto font-mono text-xs leading-relaxed text-emerald-200">
            {JSON.stringify(report, null, 2)}
          </pre>
        </div>
      ) : null}
    </section>
  );
}
