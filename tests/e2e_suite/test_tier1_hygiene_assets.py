from __future__ import annotations

from pathlib import Path

import pytest

from lib.repo_hygiene import (
    check_e2e_ast_opaque_box,
    check_gitignore,
    check_pnpm_exclusively,
    check_synthetic_data,
    check_video_and_walkthrough_assets,
    scan_secrets,
)

pytestmark = [pytest.mark.tier1, pytest.mark.static_repo, pytest.mark.hygiene]


def test_t1_f9_01_repo_secret_scan_clean(repo_root: Path) -> None:
    report = scan_secrets(repo_root)
    assert report.passed, f"Secret hygiene violations: {report.violations}"


def test_t1_f9_02_gitignore_and_vercel_isolation(repo_root: Path) -> None:
    report = check_gitignore(repo_root)
    assert report.passed, f".gitignore hygiene violations: {report.violations}"


def test_t1_f9_03_video_script_and_demo_walkthrough_complete(repo_root: Path) -> None:
    report = check_video_and_walkthrough_assets(repo_root)
    assert report.passed, f"Video/walkthrough asset violations: {report.violations}"


def test_t1_f9_04_readme_exists_without_placeholders(repo_root: Path) -> None:
    readme = repo_root / "README.md"
    assert readme.is_file(), f"Missing {readme}"
    text = readme.read_text(encoding="utf-8", errors="ignore")
    assert len(text.strip()) >= 150
    assert "TODO" not in text and "TBD" not in text


def test_t1_f9_05_synthetic_data_valid_json_zero_pii(repo_root: Path) -> None:
    report = check_synthetic_data(repo_root)
    assert report.passed, f"Synthetic data violations: {report.violations}"


def test_t1_f9_06_pnpm_exclusively_enforced(repo_root: Path) -> None:
    report = check_pnpm_exclusively(repo_root)
    assert report.passed, f"pnpm-only constraint violations: {report.violations}"
    ast_report = check_e2e_ast_opaque_box(repo_root / "tests" / "e2e_suite")
    assert ast_report.passed, f"Opaque-box AST violations: {ast_report.violations}"
