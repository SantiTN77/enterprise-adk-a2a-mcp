"""Unit tests for compliance_agent evaluate_control_matrix and edge cases."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from compliance_agent.mcp_server import evaluate_control_matrix

REPO_ROOT = Path(__file__).resolve().parents[3]
SYNTHETIC_DIR = REPO_ROOT / "data" / "synthetic"


def test_evaluate_control_matrix_invalid_json_graceful() -> None:
    bad_doc = json.loads(evaluate_control_matrix("{not-valid-json", "{}"))
    assert bad_doc["compliant"] is False
    assert "Invalid document_json" in bad_doc["error"]
    assert bad_doc["controls_evaluated"] == []

    bad_pol = json.loads(evaluate_control_matrix('{"doc_id": "x"}', "{bad-policy"))
    assert bad_pol["compliant"] is False
    assert bad_pol["document_id"] == "x"
    assert "Invalid policy_json" in bad_pol["error"]


def test_evaluate_control_matrix_envelope_unwrapping_and_custom_rules() -> None:
    doc_envelope = json.dumps(
        {
            "doc_id": "samples/custom.json",
            "gcs_uri": "gs://bucket/samples/custom.json",
            "evidence": {
                "doc_id": "samples/custom.json",
                "report_date": "2026-10-15",
                "financial_summary": {
                    "budgeted_spend_usd": 100_000.0,
                    "actual_spend_usd": 105_000.0,
                },
                "preparer": "alice",
                "approvers": ["alice", "bob"],
                "security": {"mfa_enabled": False},
            },
        }
    )
    policy_envelope = json.dumps(
        {
            "secret_id": "adk-compliance-policy-rules",
            "policy": {
                "policy_id": "CUSTOM-POL-1",
                "version": "1.2.0",
                "thresholds": {"max_budget_variance_pct": 10.0, "dual_approval_threshold_usd": 50_000.0},
                "controls": [
                    {"control_id": "FIN-VAR-01", "name": "Variance", "severity": "HIGH"},
                    {"control_id": "TRES-SOD-04", "name": "SoD", "severity": "CRITICAL"},
                    {
                        "control_id": "SEC-MFA-01",
                        "name": "MFA Required",
                        "framework": "SOC2",
                        "severity": "CRITICAL",
                        "field": "security.mfa_enabled",
                        "operator": "eq",
                        "value": True,
                    },
                ],
            },
        }
    )

    result = json.loads(evaluate_control_matrix(doc_envelope, policy_envelope))
    assert result["policy_id"] == "CUSTOM-POL-1"
    assert result["policy_version"] == "1.2.0"
    assert result["document_id"] == "samples/custom.json"
    statuses = {c["control_id"]: c["status"] for c in result["controls_evaluated"]}
    assert statuses["FIN-VAR-01"] == "PASS"
    assert statuses["TRES-SOD-04"] == "FAIL"
    assert statuses["SEC-MFA-01"] == "FAIL"
    assert result["compliant"] is False
    assert result["summary"]["highest_violation_severity"] == "CRITICAL"


def test_evaluate_control_matrix_missing_evidence_never_passes() -> None:
    minimal_doc = json.dumps({"doc_id": "empty_doc.json"})
    policy = json.dumps(
        {
            "policy_id": "STRICT-POL",
            "controls": [
                {"control_id": "FIN-VAR-01", "name": "Variance", "severity": "HIGH"},
                {"control_id": "SOX-APPR-02", "name": "Dual Approval", "severity": "HIGH"},
                {"control_id": "TRES-SOD-04", "name": "SoD", "severity": "CRITICAL"},
                {"control_id": "SOX-REV-05", "name": "ASC 606", "severity": "MEDIUM"},
            ],
        }
    )
    result = json.loads(evaluate_control_matrix(minimal_doc, policy))
    assert result["compliant"] is False
    assert result["summary"]["passed"] == 0
    assert result["summary"]["failed"] == 4


def test_evaluate_control_matrix_vendor_po_and_expiry_checks() -> None:
    doc = json.dumps(
        {
            "doc_id": "vendor_edge.json",
            "report_date": "2026-10-15",
            "vendor_contracts": [
                {
                    "vendor_id": "VND-1",
                    "annual_value_usd": 40_000.0,
                    "soc2_type2_verified": True,
                    "soc2_report_expiry": "2026-09-01",
                    "dpa_signed": True,
                    "po_number": None,
                }
            ],
        }
    )
    policy = json.dumps(
        {
            "policy_id": "VEND-POL",
            "controls": [{"control_id": "SOC2-VEND-03", "name": "Vendor SOC2", "severity": "CRITICAL"}],
        }
    )
    result = json.loads(evaluate_control_matrix(doc, policy))
    assert result["compliant"] is False
    rationale = result["violations"][0]["rationale"]
    assert "expired" in rationale
    assert "missing purchase order" in rationale


def test_evaluate_control_matrix_against_real_synthetic_files() -> None:
    if not SYNTHETIC_DIR.exists():
        pytest.skip("data/synthetic directory not present")

    policy_raw = (SYNTHETIC_DIR / "compliance_policy_rules.json").read_text(encoding="utf-8")

    # 1. Clean baseline: series_b_revenue_audit.json -> all 5 PASS
    baseline_raw = (SYNTHETIC_DIR / "series_b_revenue_audit.json").read_text(encoding="utf-8")
    baseline = json.loads(evaluate_control_matrix(baseline_raw, policy_raw))
    assert baseline["compliant"] is True
    assert baseline["summary"]["passed"] == 5
    assert baseline["summary"]["failed"] == 0

    # 2. Q3 cloud vendor review -> FIN-VAR-01 & SOX-APPR-02 FAIL; other 3 PASS
    q3_raw = (SYNTHETIC_DIR / "q3_cloud_vendor_review.json").read_text(encoding="utf-8")
    q3 = json.loads(evaluate_control_matrix(q3_raw, policy_raw))
    assert q3["compliant"] is False
    q3_statuses = {c["control_id"]: c["status"] for c in q3["controls_evaluated"]}
    assert q3_statuses == {
        "FIN-VAR-01": "FAIL",
        "SOX-APPR-02": "FAIL",
        "SOC2-VEND-03": "PASS",
        "TRES-SOD-04": "PASS",
        "SOX-REV-05": "PASS",
    }

    # 3. Treasury controls memo -> all 5 FAIL
    treasury_raw = (SYNTHETIC_DIR / "treasury_controls_memo.json").read_text(encoding="utf-8")
    treasury = json.loads(evaluate_control_matrix(treasury_raw, policy_raw))
    assert treasury["compliant"] is False
    assert treasury["summary"]["failed"] == 5
    assert treasury["summary"]["highest_violation_severity"] == "CRITICAL"
