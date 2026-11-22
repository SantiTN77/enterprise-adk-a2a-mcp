"""Embedded stdio MCP server for the Financial & Document Analysis Agent."""

from __future__ import annotations

import json
import math
import os
from collections.abc import Callable
from typing import Any

from google.api_core.exceptions import GoogleAPICallError, NotFound, PermissionDenied
from google.auth.exceptions import DefaultCredentialsError
from google.cloud import storage
from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

mcp = MCPServer("financial-analysis-mcp")

_storage_client_factory: Callable[[], storage.Client] = storage.Client
_storage_client: storage.Client | None = None


def set_storage_client_factory(factory: Callable[[], storage.Client]) -> None:
    """Override storage client creation (used by subprocess stdio test harness)."""
    global _storage_client_factory, _storage_client
    _storage_client_factory = factory
    _storage_client = None


def get_storage_client() -> storage.Client:
    """Lazily instantiate the Google Cloud Storage client."""
    global _storage_client
    if _storage_client is None:
        _storage_client = _storage_client_factory()
    return _storage_client


def _require_bucket_name() -> str:
    bucket = os.environ.get("GCS_BUCKET_NAME", "").strip()
    if not bucket:
        raise ToolError("GCS_BUCKET_NAME environment variable is not configured.")
    return bucket


def _normalize_doc_candidates(doc_id: str, bucket_name: str) -> list[str]:
    """Normalize a GCS object path or gs:// URI and generate resilient fallback paths."""
    raw = doc_id.strip()
    if raw.startswith(f"gs://{bucket_name}/"):
        clean = raw.removeprefix(f"gs://{bucket_name}/")
    elif raw.startswith("gs://"):
        without_scheme = raw.removeprefix("gs://")
        _, _, clean = without_scheme.partition("/")
    else:
        clean = raw
    clean = clean.lstrip("/")
    if not clean:
        raise ToolError("doc_id must be a non-empty GCS object path.")

    candidates = [clean]
    if "/" not in clean:
        candidates.append(f"samples/{clean}")
        if not clean.endswith(".json"):
            candidates.append(f"samples/{clean}.json")
    elif not clean.endswith(".json"):
        candidates.append(f"{clean}.json")
    return list(dict.fromkeys(candidates))


def _ensure_finite(name: str, value: float) -> float:
    numeric = float(value)
    if not math.isfinite(numeric):
        raise ToolError(f"Parameter '{name}' must be a finite number.")
    return numeric


@mcp.tool()
def list_enterprise_documents(prefix: str = "samples/") -> str:
    """List enterprise documents available in the configured GCS bucket."""
    bucket_name = _require_bucket_name()
    normalized_prefix = prefix.strip()
    try:
        client = get_storage_client()
        blobs = client.bucket(bucket_name).list_blobs(prefix=normalized_prefix)
        documents = [
            {
                "doc_id": blob.name,
                "gcs_uri": f"gs://{bucket_name}/{blob.name}",
                "size_bytes": getattr(blob, "size", None),
                "updated": blob.updated.isoformat() if getattr(blob, "updated", None) else None,
            }
            for blob in blobs
            if not blob.name.endswith("/")
        ]
        return json.dumps(
            {
                "bucket": bucket_name,
                "prefix": normalized_prefix,
                "count": len(documents),
                "documents": documents,
            }
        )
    except (NotFound, PermissionDenied, DefaultCredentialsError, GoogleAPICallError) as exc:
        raise ToolError(f"GCS list_blobs failed for gs://{bucket_name}/{normalized_prefix}: {exc}") from exc


@mcp.tool()
def read_enterprise_document(doc_id: str) -> str:
    """Read an enterprise JSON or text document from GCS by object path or gs:// URI."""
    bucket_name = _require_bucket_name()
    candidates = _normalize_doc_candidates(doc_id, bucket_name)
    try:
        client = get_storage_client()
        bucket = client.bucket(bucket_name)
        last_not_found: NotFound | None = None
        for candidate in candidates:
            try:
                text = bucket.blob(candidate).download_as_text(encoding="utf-8")
                try:
                    parsed: Any = json.loads(text)
                except json.JSONDecodeError:
                    parsed = None
                return json.dumps(
                    {
                        "bucket": bucket_name,
                        "doc_id": candidate,
                        "gcs_uri": f"gs://{bucket_name}/{candidate}",
                        "document": parsed,
                        "content": text,
                    }
                )
            except NotFound as exc:
                last_not_found = exc
        raise ToolError(f"Document not found: gs://{bucket_name}/{candidates[0]}") from last_not_found
    except ToolError:
        raise
    except (PermissionDenied, DefaultCredentialsError, GoogleAPICallError) as exc:
        raise ToolError(f"Failed to read gs://{bucket_name}/{candidates[0]}: {exc}") from exc


@mcp.tool()
def compute_financial_ratios(
    revenue: float,
    operating_expenses: float,
    liabilities: float,
    assets: float,
    cash_flow: float,
    budgeted_spend: float = 0.0,
    actual_spend: float = 0.0,
) -> str:
    """Compute deterministic profitability, leverage, liquidity, and budget variance ratios with anomaly flags."""
    rev = _ensure_finite("revenue", revenue)
    opex = _ensure_finite("operating_expenses", operating_expenses)
    liab = _ensure_finite("liabilities", liabilities)
    ast = _ensure_finite("assets", assets)
    ocf = _ensure_finite("cash_flow", cash_flow)
    b_spend = _ensure_finite("budgeted_spend", budgeted_spend)
    a_spend = _ensure_finite("actual_spend", actual_spend)

    operating_income = round(rev - opex, 2)
    net_equity = round(ast - liab, 2)

    operating_margin_pct = round((operating_income / rev) * 100.0, 2) if rev > 0.0 else None
    expense_to_revenue_ratio = round(opex / rev, 4) if rev > 0.0 else None
    debt_to_assets_ratio = round(liab / ast, 4) if ast > 0.0 else None
    debt_to_equity_ratio = round(liab / net_equity, 4) if net_equity > 0.0 else None
    cash_to_liabilities_ratio = round(ocf / liab, 4) if liab > 0.0 else None
    cash_flow_margin_pct = round((ocf / rev) * 100.0, 2) if rev > 0.0 else None

    budget_variance_usd = round(a_spend - b_spend, 2) if (b_spend != 0.0 or a_spend != 0.0) else 0.0
    budget_variance_pct = round(((a_spend - b_spend) / b_spend) * 100.0, 2) if b_spend > 0.0 else None

    anomalies: list[dict[str, Any]] = []

    if budget_variance_pct is not None and budget_variance_pct > 25.0:
        anomalies.append(
            {
                "code": "BUDGET_OVERRUN_CRITICAL",
                "severity": "CRITICAL",
                "metric": "budget_variance_pct",
                "value": budget_variance_pct,
                "threshold": "> 25.0%",
                "message": f"Actual spend exceeds budget by {budget_variance_pct:.2f}% (${budget_variance_usd:,.2f}), breaching critical 25% threshold.",
            }
        )
    elif budget_variance_pct is not None and budget_variance_pct > 10.0:
        anomalies.append(
            {
                "code": "BUDGET_OVERRUN_HIGH",
                "severity": "HIGH",
                "metric": "budget_variance_pct",
                "value": budget_variance_pct,
                "threshold": "> 10.0%",
                "message": f"Actual spend exceeds budget by {budget_variance_pct:.2f}% (${budget_variance_usd:,.2f}), breaching 10% policy tolerance.",
            }
        )

    if operating_margin_pct is not None and operating_margin_pct < 0.0:
        anomalies.append(
            {
                "code": "NEGATIVE_OPERATING_MARGIN",
                "severity": "HIGH",
                "metric": "operating_margin_pct",
                "value": operating_margin_pct,
                "threshold": "< 0.0%",
                "message": f"Operating margin is negative ({operating_margin_pct:.2f}%).",
            }
        )

    if debt_to_assets_ratio is not None and debt_to_assets_ratio > 0.70:
        anomalies.append(
            {
                "code": "HIGH_LEVERAGE_RATIO",
                "severity": "HIGH",
                "metric": "debt_to_assets_ratio",
                "value": debt_to_assets_ratio,
                "threshold": "> 0.70",
                "message": f"Debt-to-assets ratio ({debt_to_assets_ratio:.4f}) exceeds 0.70 leverage threshold.",
            }
        )

    if ast > 0.0 and net_equity <= 0.0:
        anomalies.append(
            {
                "code": "NEGATIVE_EQUITY",
                "severity": "CRITICAL",
                "metric": "net_equity_usd",
                "value": net_equity,
                "threshold": "<= 0.0",
                "message": f"Total liabilities (${liab:,.2f}) meet or exceed total assets (${ast:,.2f}).",
            }
        )

    if ocf < 0.0:
        anomalies.append(
            {
                "code": "NEGATIVE_CASH_FLOW",
                "severity": "HIGH",
                "metric": "operating_cash_flow_usd",
                "value": ocf,
                "threshold": "< 0.0",
                "message": f"Operating cash flow is negative (${ocf:,.2f}).",
            }
        )
    elif cash_to_liabilities_ratio is not None and cash_to_liabilities_ratio < 0.20:
        anomalies.append(
            {
                "code": "LOW_CASH_COVERAGE",
                "severity": "MEDIUM",
                "metric": "cash_to_liabilities_ratio",
                "value": cash_to_liabilities_ratio,
                "threshold": "< 0.20",
                "message": f"Operating cash flow to liabilities coverage ({cash_to_liabilities_ratio:.4f}) is below 0.20.",
            }
        )

    return json.dumps(
        {
            "inputs": {
                "revenue_usd": rev,
                "operating_expenses_usd": opex,
                "total_liabilities_usd": liab,
                "total_assets_usd": ast,
                "operating_cash_flow_usd": ocf,
                "budgeted_spend_usd": b_spend,
                "actual_spend_usd": a_spend,
            },
            "metrics": {
                "operating_income_usd": operating_income,
                "net_equity_usd": net_equity,
                "operating_margin_pct": operating_margin_pct,
                "expense_to_revenue_ratio": expense_to_revenue_ratio,
                "debt_to_assets_ratio": debt_to_assets_ratio,
                "debt_to_equity_ratio": debt_to_equity_ratio,
                "cash_to_liabilities_ratio": cash_to_liabilities_ratio,
                "cash_ratio": cash_to_liabilities_ratio,
                "cash_flow_margin_pct": cash_flow_margin_pct,
                "budget_variance_usd": budget_variance_usd,
                "budget_variance_pct": budget_variance_pct,
            },
            "anomalies": anomalies,
            "anomaly_count": len(anomalies),
        }
    )


if __name__ == "__main__":
    mcp.run(transport="stdio")
