'use client';

import { useState } from 'react';
import { AnimatePresence, motion, useReducedMotion } from 'motion/react';
import { Check, ClipboardCheck, Code2, Copy } from 'lucide-react';
import type { AnalyzeResponse, RiskRating } from '@/lib/types';
import { formatMetricLabel, formatMetricValue, normalizeFindingItem } from './finding-utils';

const EASE = [0.16, 1, 0.3, 1] as const;

const RISK: Record<RiskRating, { label: string; bg: string; text: string; level: number }> = {
  LOW: { label: 'LOW RISK', bg: 'bg-ok', text: 'text-ok', level: 1 },
  MEDIUM: { label: 'MEDIUM RISK', bg: 'bg-ink-muted', text: 'text-ink-muted', level: 2 },
  HIGH: { label: 'HIGH RISK', bg: 'bg-warn', text: 'text-warn', level: 3 },
  CRITICAL: { label: 'CRITICAL RISK', bg: 'bg-bad', text: 'text-bad', level: 4 },
};

export function ExecutiveReportPanel({ report }: { report: AnalyzeResponse }) {
  const reduce = useReducedMotion();
  const [showRawJson, setShowRawJson] = useState(false);
  const [copied, setCopied] = useState(false);
  const risk = RISK[report.overall_risk_rating];
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

  const rise = (d = 0) =>
    reduce ? {} : { initial: { opacity: 0, y: 18 }, animate: { opacity: 1, y: 0 }, transition: { duration: 0.8, ease: EASE, delay: d } };

  return (
    <section aria-labelledby="executive-report-heading" data-demo="report">
      <div className="flex flex-col gap-4 border-t border-ink pt-5 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <p className="eyebrow">Synthesised by the orchestrator</p>
          <h2 id="executive-report-heading" className="mt-2 text-2xl font-medium tracking-tight md:text-3xl">
            Executive Risk &amp; Compliance Report
          </h2>
          <p className="mt-2 font-mono text-[11px] text-ink-muted">
            {report.run_id} · {report.scenario_id} · {report.doc_id} · {report.timestamp_utc}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2 text-sm">
          <button
            type="button"
            onClick={() => setShowRawJson((p) => !p)}
            aria-expanded={showRawJson}
            aria-controls="raw-json-panel"
            className="inline-flex items-center gap-2 rounded-full border border-line-strong px-4 py-2 transition-colors hover:border-ink"
          >
            <Code2 className="h-4 w-4" aria-hidden="true" />
            {showRawJson ? 'Hide Raw JSON' : 'Show Raw JSON'}
          </button>
          <button
            type="button"
            onClick={handleCopyJson}
            aria-label="Copy full analysis JSON report to clipboard"
            className="inline-flex items-center gap-2 rounded-full border border-line-strong px-4 py-2 transition-colors hover:border-ink"
          >
            {copied ? <ClipboardCheck className="h-4 w-4 text-ok" aria-hidden="true" /> : <Copy className="h-4 w-4" aria-hidden="true" />}
            {copied ? 'Copied JSON' : 'Copy JSON'}
          </button>
        </div>
      </div>

      {/* verdict */}
      <motion.div {...rise()} className="mt-8 grid gap-8 lg:grid-cols-12">
        <div className="lg:col-span-4">
          <span
            data-testid="risk-rating-badge"
            className={`inline-flex items-center gap-2 rounded-full px-3.5 py-1.5 text-xs font-semibold tracking-wide text-paper ${risk.bg}`}
          >
            {risk.label}
          </span>
          <div className="mt-5 flex gap-1.5" aria-hidden="true">
            {[1, 2, 3, 4].map((n) => (
              <motion.span
                key={n}
                initial={reduce ? false : { scaleY: 0.2, opacity: 0.3 }}
                animate={{ scaleY: 1, opacity: 1 }}
                transition={{ duration: 0.6, ease: EASE, delay: 0.2 + n * 0.08 }}
                className={`h-10 flex-1 origin-bottom rounded-sm ${n <= risk.level ? risk.bg : 'bg-line'}`}
              />
            ))}
          </div>
          <p className="mt-2 flex justify-between font-mono text-[10px] text-ink-faint">
            <span>low</span>
            <span>critical</span>
          </p>
        </div>
        <div className="lg:col-span-8">
          <p className="eyebrow">Executive summary</p>
          <p className="mt-3 text-pretty text-xl leading-relaxed text-ink md:text-[22px]">{report.executive_summary}</p>
        </div>
      </motion.div>

      {/* two columns */}
      <div className="mt-12 grid gap-6 lg:grid-cols-2">
        <motion.article {...rise(0.1)} className="card p-5 sm:p-6">
          <p className="eyebrow">financial_analysis_agent</p>
          <h3 className="mt-2 text-xl font-medium tracking-tight">Financial Analysis</h3>
          <p className="mt-2 text-sm leading-relaxed text-ink-muted">{report.financial_analysis.summary}</p>

          {metricEntries.length > 0 ? (
            <dl className="mt-5 grid grid-cols-2 gap-px overflow-hidden rounded-xl border border-line bg-line [&>*:last-child:nth-child(odd)]:col-span-2">
              {metricEntries.map(([key, value]) => (
                <div key={key} className="bg-card p-3">
                  <dt className="text-[11px] text-ink-muted">{formatMetricLabel(key)}</dt>
                  <dd className="mt-1 font-serif text-2xl leading-none">{formatMetricValue(key, value)}</dd>
                </div>
              ))}
            </dl>
          ) : null}

          <h4 className="eyebrow mt-6">Financial anomalies</h4>
          {report.financial_analysis.anomalies.length > 0 ? (
            <ul className="mt-2 divide-y divide-line">
              {report.financial_analysis.anomalies.map((item, idx) => {
                const n = normalizeFindingItem(item);
                return (
                  <li key={`${n.title}-${idx}`} className="flex gap-3 py-3 text-sm">
                    <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-warn" />
                    <span>
                      <span className="font-medium">{n.title}</span>
                      {n.detail ? <span className="mt-0.5 block text-xs leading-relaxed text-ink-muted">{n.detail}</span> : null}
                    </span>
                  </li>
                );
              })}
            </ul>
          ) : (
            <p className="mt-2 text-sm text-ok">No material financial anomalies flagged.</p>
          )}

          {report.financial_analysis.sources.length > 0 ? (
            <div className="mt-5 border-t border-line pt-3">
              <h4 className="eyebrow !text-[10px]">Sources</h4>
              <ul className="mt-1.5 space-y-1">
                {report.financial_analysis.sources.map((src) => (
                  <li key={src} className="break-all font-mono text-[11px] text-ink-muted">
                    {src}
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
        </motion.article>

        <motion.article {...rise(0.18)} className="card p-5 sm:p-6">
          <div className="flex flex-wrap items-start justify-between gap-2">
            <div>
              <p className="eyebrow">audit_compliance_agent</p>
              <h3 className="mt-2 text-xl font-medium tracking-tight">Compliance &amp; Controls Audit</h3>
            </div>
            <span
              className={`rounded-full px-3 py-1 text-xs font-semibold ${
                report.compliance_audit.compliant ? 'bg-ok-soft text-ok' : 'bg-bad-soft text-bad'
              }`}
            >
              {report.compliance_audit.compliant ? 'COMPLIANT' : 'NON-COMPLIANT'}
            </span>
          </div>
          <p className="mt-1 font-mono text-[11px] text-ink-muted">Policy ID: {report.compliance_audit.policy_id}</p>
          <p className="mt-2 text-sm leading-relaxed text-ink-muted">{report.compliance_audit.summary}</p>

          <h4 className="eyebrow mt-6">Controls evaluated ({report.compliance_audit.controls_evaluated.length})</h4>
          {report.compliance_audit.controls_evaluated.length > 0 ? (
            <ul className="mt-2 divide-y divide-line">
              {report.compliance_audit.controls_evaluated.map((item, idx) => {
                const n = normalizeFindingItem(item);
                return (
                  <li key={`${n.title}-${idx}`} className="py-2.5 text-sm">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <span className="font-medium">{n.title}</span>
                      {n.badge ? <span className="font-mono text-[11px] text-ink-muted">{n.badge}</span> : null}
                    </div>
                    {n.detail ? <p className="mt-0.5 text-xs leading-relaxed text-ink-muted">{n.detail}</p> : null}
                  </li>
                );
              })}
            </ul>
          ) : (
            <p className="mt-2 text-sm text-ink-muted">No individual controls listed.</p>
          )}

          <h4 className="eyebrow mt-6">Control violations</h4>
          {report.compliance_audit.violations.length > 0 ? (
            <ul className="mt-2 space-y-2">
              {report.compliance_audit.violations.map((item, idx) => {
                const n = normalizeFindingItem(item);
                return (
                  <li key={`${n.title}-${idx}`} className="rounded-xl border border-bad/25 bg-bad-soft/50 p-3 text-sm">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <span className="font-medium text-bad">{n.title}</span>
                      {n.severity ? <span className="font-mono text-[11px] font-semibold text-bad">{n.severity}</span> : null}
                    </div>
                    {n.detail ? <p className="mt-1 text-xs leading-relaxed text-ink-soft">{n.detail}</p> : null}
                  </li>
                );
              })}
            </ul>
          ) : (
            <p className="mt-2 text-sm text-ok">Zero compliance violations detected.</p>
          )}
        </motion.article>
      </div>

      <motion.div {...rise(0.25)} className="mt-10">
        <p className="eyebrow">Actionable recommendations</p>
        {report.recommendations.length > 0 ? (
          <ol className="mt-3 border-b border-line">
            {report.recommendations.map((item, idx) => {
              const n = normalizeFindingItem(item);
              return (
                <li key={`${n.title}-${idx}`} className="grid grid-cols-[40px_1fr] gap-2 border-t border-line py-4 text-[15px] leading-relaxed">
                  <span className="font-mono text-xs text-accent">{String(idx + 1).padStart(2, '0')}</span>
                  <span>
                    <span className="font-medium">{n.title}</span>
                    {n.detail ? <span className="text-ink-muted"> — {n.detail}</span> : null}
                  </span>
                </li>
              );
            })}
          </ol>
        ) : (
          <p className="mt-2 flex items-center gap-2 text-sm text-ink-muted">
            <Check className="h-4 w-4 text-ok" /> No remediation actions required.
          </p>
        )}
      </motion.div>

      <AnimatePresence initial={false}>
        {showRawJson ? (
          <motion.div
            id="raw-json-panel"
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.6, ease: EASE }}
            className="overflow-hidden"
          >
            <div className="mt-6 rounded-[14px] bg-ink p-5">
              <p className="font-mono text-[10px] uppercase tracking-[0.14em] text-paper/50">Raw orchestrator JSON response</p>
              <pre className="mt-3 max-h-96 overflow-auto font-mono text-xs leading-relaxed text-paper/85">
                {JSON.stringify(report, null, 2)}
              </pre>
            </div>
          </motion.div>
        ) : null}
      </AnimatePresence>
    </section>
  );
}
