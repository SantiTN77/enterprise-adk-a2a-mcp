import { NextResponse } from 'next/server';
import {
  BffConfigError,
  BffUpstreamError,
  callOrchestrator,
  sanitizeErrorText,
} from '@/lib/gcp-bff';
import type { ScenariosResponse } from '@/lib/types';

export const dynamic = 'force-dynamic';
export const maxDuration = 120;

export async function GET(): Promise<NextResponse> {
  try {
    const { data } = await callOrchestrator<ScenariosResponse>('/api/scenarios', {
      method: 'GET',
      timeoutMs: 15_000,
    });

    return NextResponse.json<ScenariosResponse>(data, { status: 200 });
  } catch (err) {
    if (err instanceof BffConfigError) {
      console.error('[api/scenarios]', { code: 'BFF_NOT_CONFIGURED', message: err.message });
      return NextResponse.json(
        { error: sanitizeErrorText(err.message), code: 'BFF_NOT_CONFIGURED' },
        { status: 503 },
      );
    }

    if (err instanceof BffUpstreamError) {
      console.error('[api/scenarios]', { status: err.status, code: err.code, message: err.message });
      return NextResponse.json(
        { error: err.message, code: err.code },
        { status: err.status },
      );
    }

    const message = err instanceof Error ? sanitizeErrorText(err.message) : 'Unexpected scenarios proxy error';
    console.error('[api/scenarios]', { code: 'INTERNAL_ERROR', message });
    return NextResponse.json({ error: message, code: 'INTERNAL_ERROR' }, { status: 502 });
  }
}
