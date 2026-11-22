import { NextResponse } from 'next/server';
import {
  BffConfigError,
  BffUpstreamError,
  callOrchestrator,
  inspectBffConfiguration,
  sanitizeErrorText,
} from '@/lib/gcp-bff';
import type { HealthResponse } from '@/lib/types';

export const dynamic = 'force-dynamic';
export const maxDuration = 120;

interface UpstreamHealthPayload {
  status: string;
  service: string;
  agents?: {
    financial?: string;
    compliance?: string;
  };
}

export async function GET(): Promise<NextResponse<HealthResponse>> {
  const checkedAt = new Date().toISOString();
  const config = inspectBffConfiguration();

  if (!config.configured) {
    return NextResponse.json<HealthResponse>(
      {
        status: 'degraded',
        service: 'vercel-bff',
        bff: {
          runtime: 'nodejs',
          auth_mode: config.authMode,
          orchestrator_configured: false,
        },
        error: config.error ?? 'BFF orchestrator configuration is incomplete',
        checked_at_utc: checkedAt,
      },
      { status: 503 },
    );
  }

  try {
    const { data, targetMode } = await callOrchestrator<UpstreamHealthPayload>('/health', {
      method: 'GET',
      timeoutMs: 10_000,
    });

    return NextResponse.json<HealthResponse>(
      {
        status: data.status === 'ok' ? 'ok' : 'degraded',
        service: 'vercel-bff',
        bff: {
          runtime: 'nodejs',
          auth_mode: targetMode,
          orchestrator_configured: true,
        },
        orchestrator: data,
        checked_at_utc: checkedAt,
      },
      { status: 200 },
    );
  } catch (err) {
    const message =
      err instanceof BffConfigError || err instanceof BffUpstreamError
        ? err.message
        : err instanceof Error
          ? sanitizeErrorText(err.message)
          : 'Orchestrator health check failed';

    console.error('[api/health]', { authMode: config.authMode, message });

    return NextResponse.json<HealthResponse>(
      {
        status: 'degraded',
        service: 'vercel-bff',
        bff: {
          runtime: 'nodejs',
          auth_mode: config.authMode,
          orchestrator_configured: true,
        },
        error: message,
        checked_at_utc: checkedAt,
      },
      { status: 503 },
    );
  }
}
