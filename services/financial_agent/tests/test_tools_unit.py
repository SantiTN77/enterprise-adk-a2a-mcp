"""Unit tests for financial_agent MCP tools and deterministic financial ratios."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from mcp.server.mcpserver.exceptions import ToolError

from financial_agent.mcp_server import compute_financial_ratios

REPO_ROOT = Path(__file__).resolve().parents[3]
SYNTHETIC_DIR = REPO_ROOT / "data" / "synthetic"


def test_compute_financial_ratios_healthy_baseline() -> None:
    raw = compute_financial_ratios(
        revenue=18_450_000.0,
        operating_expenses=14_200_000.0,
        liabilities=19_200_000.0,
        assets=68_500_000.0,
        cash_flow=5_100_000.0,
        budgeted_spend=14_000_000.0,
        actual_spend=14_200_000.0,
    )
    data = json.loads(raw)
    metrics = data["metrics"]
    assert metrics["operating_income_usd"] == 4_250_000.0
    assert metrics["net_equity_usd"] == 49_300_000.0
    assert metrics["operating_margin_pct"] == pytest.approx(23.04, abs=0.01)
    assert metrics["debt_to_assets_ratio"] == pytest.approx(0.2803, abs=0.0001)
    assert metrics["cash_to_liabilities_ratio"] == pytest.approx(0.2656, abs=0.0001)
    assert metrics["budget_variance_usd"] == 200_000.0
    assert metrics["budget_variance_pct"] == pytest.approx(1.43, abs=0.01)
    assert data["anomaly_count"] == 0
    assert data["anomalies"] == []


def test_compute_financial_ratios_zero_denominators_no_crash() -> None:
    raw = compute_financial_ratios(
        revenue=0.0,
        operating_expenses=100_000.0,
        liabilities=0.0,
        assets=0.0,
        cash_flow=0.0,
        budgeted_spend=0.0,
        actual_spend=50_000.0,
    )
    data = json.loads(raw)
    metrics = data["metrics"]
    assert metrics["operating_income_usd"] == -100_000.0
    assert metrics["operating_margin_pct"] is None
    assert metrics["expense_to_revenue_ratio"] is None
    assert metrics["debt_to_assets_ratio"] is None
    assert metrics["debt_to_equity_ratio"] is None
    assert metrics["cash_to_liabilities_ratio"] is None
    assert metrics["cash_flow_margin_pct"] is None
    assert metrics["budget_variance_usd"] == 50_000.0
    assert metrics["budget_variance_pct"] is None


def test_compute_financial_ratios_variance_bands_and_anomalies() -> None:
    # 15% overrun -> BUDGET_OVERRUN_HIGH; negative margin, high leverage, negative equity, negative cash flow
    raw = compute_financial_ratios(
        revenue=1_000_000.0,
        operating_expenses=1_250_000.0,
        liabilities=2_500_000.0,
        assets=2_000_000.0,
        cash_flow=-150_000.0,
        budgeted_spend=100_000.0,
        actual_spend=115_000.0,
    )
    data = json.loads(raw)
    codes = {item["code"] for item in data["anomalies"]}
    assert {
        "BUDGET_OVERRUN_HIGH",
        "NEGATIVE_OPERATING_MARGIN",
        "HIGH_LEVERAGE_RATIO",
        "NEGATIVE_EQUITY",
        "NEGATIVE_CASH_FLOW",
    }.issubset(codes)
    assert data["metrics"]["debt_to_equity_ratio"] is None

    # >25% overrun -> BUDGET_OVERRUN_CRITICAL + LOW_CASH_COVERAGE
    raw_crit = compute_financial_ratios(
        revenue=5_000_000.0,
        operating_expenses=4_000_000.0,
        liabilities=2_000_000.0,
        assets=4_000_000.0,
        cash_flow=100_000.0,
        budgeted_spend=1_000_000.0,
        actual_spend=1_300_000.0,
    )
    crit_codes = {item["code"] for item in json.loads(raw_crit)["anomalies"]}
    assert "BUDGET_OVERRUN_CRITICAL" in crit_codes
    assert "LOW_CASH_COVERAGE" in crit_codes


def test_compute_financial_ratios_rejects_non_finite() -> None:
    with pytest.raises(ToolError):
        compute_financial_ratios(
            revenue=float("nan"),
            operating_expenses=100.0,
            liabilities=100.0,
            assets=200.0,
            cash_flow=50.0,
        )


def test_compute_financial_ratios_aligned_with_synthetic_docs() -> None:
    if not SYNTHETIC_DIR.exists():
        pytest.skip("data/synthetic directory not present")

    q3_doc = json.loads((SYNTHETIC_DIR / "q3_cloud_vendor_review.json").read_text(encoding="utf-8"))
    fs_q3 = q3_doc["financial_summary"]
    q3_res = json.loads(
        compute_financial_ratios(
            revenue=fs_q3["revenue_usd"],
            operating_expenses=fs_q3["operating_expenses_usd"],
            liabilities=fs_q3["total_liabilities_usd"],
            assets=fs_q3["total_assets_usd"],
            cash_flow=fs_q3["operating_cash_flow_usd"],
            budgeted_spend=fs_q3["budgeted_spend_usd"],
            actual_spend=fs_q3["actual_spend_usd"],
        )
    )
    assert q3_res["metrics"]["budget_variance_pct"] == fs_q3["budget_variance_pct"]
    assert q3_res["metrics"]["operating_income_usd"] == fs_q3["operating_income_usd"]
    assert any(a["code"] == "BUDGET_OVERRUN_CRITICAL" for a in q3_res["anomalies"])

    treasury_doc = json.loads((SYNTHETIC_DIR / "treasury_controls_memo.json").read_text(encoding="utf-8"))
    fs_tr = treasury_doc["financial_summary"]
    tr_res = json.loads(
        compute_financial_ratios(
            revenue=fs_tr["revenue_usd"],
            operating_expenses=fs_tr["operating_expenses_usd"],
            liabilities=fs_tr["total_liabilities_usd"],
            assets=fs_tr["total_assets_usd"],
            cash_flow=fs_tr["operating_cash_flow_usd"],
            budgeted_spend=fs_tr["budgeted_spend_usd"],
            actual_spend=fs_tr["actual_spend_usd"],
        )
    )
    tr_codes = {a["code"] for a in tr_res["anomalies"]}
    assert {"BUDGET_OVERRUN_HIGH", "HIGH_LEVERAGE_RATIO", "NEGATIVE_CASH_FLOW"}.issubset(tr_codes)
