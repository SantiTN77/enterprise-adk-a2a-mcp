import { NextResponse } from 'next/server';
import {
  BffConfigError,
  BffUpstreamError,
  callOrchestrator,
  sanitizeErrorText,
} from '@/lib/gcp-bff';
import { AnalyzeRequestSchema, formatZodErrors } from '@/lib/schemas';
import type { AnalyzeResponse } from '@/lib/types';

export const dynamic = 'force-dynamic';
export const maxDuration = 120;

export async function POST(request: Request): Promise<NextResponse> {
  let rawBody: unknown;
  try {
    rawBody = await request.json();
  } catch {
    return NextResponse.json(
      { error: 'Request body must be valid JSON', code: 'INVALID_JSON' },
      { status: 400 },
    );
  }

  const parsed = AnalyzeRequestSchema.safeParse(rawBody);
  if (!parsed.success) {
    return NextResponse.json(
      {
        error: 'Invalid analysis request payload',
        code: 'VALIDATION_ERROR',
        details: formatZodErrors(parsed.error),
      },
      { status: 400 },
    );
  }

  try {
    const { data } = await callOrchestrator<AnalyzeResponse>('/api/analyze', {
      method: 'POST',
      body: JSON.stringify(parsed.data),
      timeoutMs: 110_000,
    });

    return NextResponse.json<AnalyzeResponse>(data, { status: 200 });
  } catch (err) {
    if (err instanceof BffConfigError) {
      console.error('[api/analyze]', { code: 'BFF_NOT_CONFIGURED', message: err.message });
      return NextResponse.json(
        { error: sanitizeErrorText(err.message), code: 'BFF_NOT_CONFIGURED' },
        { status: 503 },
      );
    }

    if (err instanceof BffUpstreamError) {
      console.error('[api/analyze]', { status: err.status, code: err.code, message: err.message });
      return NextResponse.json(
        { error: err.message, code: err.code },
        { status: err.status },
      );
    }

    const message = err instanceof Error ? sanitizeErrorText(err.message) : 'Unexpected analyze proxy error';
    console.error('[api/analyze]', { code: 'INTERNAL_ERROR', message });
    return NextResponse.json({ error: message, code: 'INTERNAL_ERROR' }, { status: 502 });
  }
}
