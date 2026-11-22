from __future__ import annotations

from pathlib import Path

import pytest

from lib.tf_policy import (
    evaluate_terraform_directory,
    run_terraform_cli_checks,
)

pytestmark = [pytest.mark.tier1, pytest.mark.static_repo, pytest.mark.terraform]


def test_t1_f8_01_terraform_hcl_parse_and_cli_validate(repo_root: Path) -> None:
    tf_dir = repo_root / "infra" / "terraform"
    report = evaluate_terraform_directory(tf_dir)
    assert len(report.tf_files) > 0, f"Expected .tf files in {tf_dir}, violations={report.violations}"
    ok, msg = run_terraform_cli_checks(tf_dir)
    assert ok, msg


def test_t1_f8_02_cloud_run_zero_idle_and_deletion_protection_false(repo_root: Path) -> None:
    tf_dir = repo_root / "infra" / "terraform"
    report = evaluate_terraform_directory(tf_dir)
    scaling_violations = [
        v
        for v in report.violations
        if "min_instance_count" in v or "max_instance_count" in v or "deletion_protection" in v or "Expected >=" in v
    ]
    assert not scaling_violations, f"Zero-idle / scaling violations: {scaling_violations}"


def test_t1_f8_03_no_public_cloud_run_iam_principals(repo_root: Path) -> None:
    tf_dir = repo_root / "infra" / "terraform"
    report = evaluate_terraform_directory(tf_dir)
    public_violations = [v for v in report.violations if "public" in v.lower() or "allUsers" in v]
    assert not public_violations, f"Public Cloud Run IAM violation: {public_violations}"


def test_t1_f8_04_least_privilege_service_accounts_and_invokers(repo_root: Path) -> None:
    tf_dir = repo_root / "infra" / "terraform"
    report = evaluate_terraform_directory(tf_dir)
    assert len(report.service_accounts) >= 4, (
        f"Expected >= 4 least-privilege google_service_account resources, got {report.service_accounts}"
    )
    iam_violations = [v for v in report.violations if "iam" in v.lower() or "roles/run.invoker" in v]
    assert not iam_violations, f"IAM policy violations: {iam_violations}"


def test_t1_f8_05_zero_always_on_paid_endpoints(repo_root: Path) -> None:
    tf_dir = repo_root / "infra" / "terraform"
    report = evaluate_terraform_directory(tf_dir)
    always_on = [v for v in report.violations if "always-on" in v]
    assert not always_on, f"Always-on paid resources forbidden: {always_on}"
