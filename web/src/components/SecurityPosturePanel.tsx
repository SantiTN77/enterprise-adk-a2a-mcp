'use client';

import { AnimatePresence, motion, useReducedMotion } from 'motion/react';
import type { HealthResponse, SecurityPosture } from '@/lib/types';
import { STRINGS, useLang } from '@/lib/i18n';

const EASE = [0.16, 1, 0.3, 1] as const;

interface SecurityPosturePanelProps {
  expanded: boolean;
  health: HealthResponse | null;
  posture: SecurityPosture | null;
}


export function SecurityPosturePanel({ expanded, health, posture }: SecurityPosturePanelProps) {
  const reduce = useReducedMotion();
  const [lang] = useLang();
  const t = STRINGS[lang];
  const minInstances = posture?.min_instances ?? 0;
  const maxInstances = posture?.max_instances ?? 2;
  const iamMode = posture?.cloud_run_iam ?? 'private-oidc-enforced';

  return (
    <section id="security-posture-drawer" aria-labelledby="security-posture-heading" data-demo="posture">
      <div className="flex flex-wrap items-end justify-between gap-4 border-t border-ink pt-5">
        <div>
          <p className="eyebrow">{t.requestPath}</p>
          <h2 id="security-posture-heading" className="mt-2 text-2xl font-medium tracking-tight md:text-3xl">
            {t.postureTitle}
          </h2>
        </div>
        <ul className="flex flex-wrap gap-x-5 gap-y-1 font-mono text-[11px] text-ink-muted">
          <li>IAM: {iamMode}</li>
          <li>
            min_instances={minInstances}, max_instances={maxInstances} ($0 Idle Cost)
          </li>
          <li>Orchestrator: {health?.orchestrator?.status === 'ok' ? t.reachable : t.privateRun}</li>
        </ul>
      </div>

      <AnimatePresence initial={false}>
        {expanded ? (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.7, ease: EASE }}
            className="overflow-hidden"
          >
            <p className="mt-5 max-w-3xl text-[15px] leading-relaxed text-ink-muted">
              {t.postureLede}{' '}
              <code className="rounded bg-paper-deep px-1 font-mono text-[13px] text-ink">401/403</code>.
            </p>

            <div className="relative mt-8">
              {/* connector line with travelling packet */}
              <div className="absolute left-0 right-0 top-[11px] hidden h-px bg-line-strong md:block" />
              {!reduce ? (
                <motion.span
                  className="absolute top-[8px] hidden h-[7px] w-[7px] rounded-full bg-accent md:block"
                  animate={{ left: ['0%', '100%'] }}
                  transition={{ duration: 4.5, ease: 'easeInOut', repeat: Infinity, repeatDelay: 0.6 }}
                />
              ) : null}
              <ol className="grid gap-6 md:grid-cols-5 md:gap-4">
                {t.hops.map(([title, subtitle, detail], index) => (
                  <motion.li
                    key={title}
                    initial={reduce ? false : { opacity: 0, y: 14 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.7, ease: EASE, delay: 0.1 + index * 0.07 }}
                    className="relative"
                  >
                    <span className="relative z-10 flex h-[23px] w-[23px] items-center justify-center rounded-full border border-ink bg-paper font-mono text-[10px]">
                      {index + 1}
                    </span>
                    <h3 className="mt-3 text-sm font-medium">{title}</h3>
                    <p className="mt-0.5 font-mono text-[11px] text-accent">{subtitle}</p>
                    <p className="mt-2 text-xs leading-relaxed text-ink-muted">{detail}</p>
                  </motion.li>
                ))}
              </ol>
            </div>
          </motion.div>
        ) : null}
      </AnimatePresence>
    </section>
  );
}
