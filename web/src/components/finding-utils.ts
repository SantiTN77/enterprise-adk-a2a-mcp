import type { FindingItem, MetricValue } from '@/lib/types';

export interface NormalizedFinding {
  title: string;
  detail?: string;
  badge?: string;
  severity?: string;
  remediation?: string;
}

export function normalizeFindingItem(item: FindingItem): NormalizedFinding {
  if (typeof item === 'string') {
    return { title: item };
  }

  const primaryTitle =
    item.title ??
    item.name ??
    item.control_id ??
    item.reason ??
    item.description ??
    'Finding';

  const detailParts: string[] = [];
  if (item.detail && item.detail !== primaryTitle) {
    detailParts.push(item.detail);
  }
  if (item.description && item.description !== primaryTitle) {
    detailParts.push(item.description);
  }
  if (item.reason && item.reason !== primaryTitle) {
    detailParts.push(item.reason);
  }

  return {
    title: String(primaryTitle),
    detail: detailParts.length > 0 ? detailParts.join(' — ') : undefined,
    badge: item.control_id && item.control_id !== primaryTitle ? String(item.control_id) : item.status ? String(item.status) : undefined,
    severity: item.severity ? String(item.severity) : undefined,
    remediation: item.remediation ? String(item.remediation) : undefined,
  };
}

export function formatMetricLabel(key: string): string {
  return key
    .replace(/_usd$/i, ' (USD)')
    .replace(/_pct$/i, ' (%)')
    .replace(/_/g, ' ')
    .replace(/\b\w/g, (char) => char.toUpperCase());
}

export function formatMetricValue(key: string, value: MetricValue): string {
  if (value === null || value === undefined) {
    return 'N/A';
  }
  if (typeof value === 'boolean') {
    return value ? 'Yes' : 'No';
  }
  if (typeof value === 'number') {
    if (key.endsWith('_usd')) {
      return new Intl.NumberFormat('en-US', {
        style: 'currency',
        currency: 'USD',
        maximumFractionDigits: 0,
      }).format(value);
    }
    if (key.endsWith('_pct')) {
      return `${value.toFixed(2)}%`;
    }
    return new Intl.NumberFormat('en-US', {
      maximumFractionDigits: 2,
    }).format(value);
  }
  return String(value);
}
