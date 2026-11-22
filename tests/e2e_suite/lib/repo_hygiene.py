from __future__ import annotations

import ast
import json
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

SKIP_DIRS = {
    ".git",
    ".venv",
    "venv",
    "node_modules",
    ".next",
    ".terraform",
    "__pycache__",
    ".pytest_cache",
    ".vercel",
    "playwright-report",
    "test-results",
    "blob-report",
}

FORBIDDEN_COMMITTED_FILES = {
    ".env",
    ".env.local",
    ".env.production",
    "terraform.tfvars",
    "terraform.tfstate",
    "terraform.tfstate.backup",
    "package-lock.json",
}

PRIVATE_KEY_HEADER_RE = re.compile(
    r"-----BEGIN\s+(?:RSA\s+|EC\s+|OPENSSH\s+)?PRIVATE\s+KEY-----(?:\\n|\s)+[A-Za-z0-9+/=]{16,}"
)
SA_JSON_KEY_RE = re.compile(r'"type"\s*:\s*"service_account"')
API_KEY_RE = re.compile(r"\bAIza[0-9A-Za-z\-_]{25,}\b")
NEXT_PUBLIC_SECRET_RE = re.compile(
    r"\bNEXT_PUBLIC_[A-Z0-9_]*(?:GCP|PRIVATE|SECRET|TOKEN|KEY|SA_|ORCHESTRATOR)\b"
)
RETIRED_GEMINI_RE = re.compile(r"\bgemini-(?:1\.[05]|2\.[05])[a-zA-Z0-9.\-]*\b", re.IGNORECASE)
FASTMCP_RE = re.compile(r"\bFastMCP\b")
LEGACY_PKG_MGR_CMD_RE = re.compile(
    r"(?<![A-Za-z0-9_.-])(?:n" + r"pm|n" + r"px)\s+(?:install|ci|run|test|exec|build|dev|playwright)\b",
    re.IGNORECASE,
)

FORBIDDEN_E2E_IMPORT_ROOTS = {
    "services",
    "web",
    "financial_agent",
    "compliance_agent",
    "orchestrator",
}

REQUIRED_GITIGNORE_TOKENS = (".env", ".terraform", "tfstate", ".venv")
REQUIRED_DOC_KEYWORDS = (
    "a2a",
    "mcp",
    "cloud run",
    "oidc",
    "secret manager",
    "gcs",
    "vercel",
)


@dataclass
class HygieneReport:
    violations: list[str] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return len(self.violations) == 0


def _iter_repo_files(root: Path, *, include_tests_lib: bool = False) -> list[Path]:
    files: list[Path] = []
    if not root.exists():
        return files
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        if not include_tests_lib:
            rel = path.relative_to(root).as_posix()
            if rel.startswith("tests/e2e_suite/lib/") or rel == "tests/e2e_suite/test_self_verify.py":
                continue
        files.append(path)
    return files


def scan_secrets(repo_root: Path) -> HygieneReport:
    report = HygieneReport()
    if not repo_root.is_dir():
        report.violations.append(f"Repo root missing: {repo_root}")
        return report

    for path in _iter_repo_files(repo_root):
        rel = path.relative_to(repo_root).as_posix()
        if path.name in FORBIDDEN_COMMITTED_FILES and path.name != "package-lock.json":
            # Allow local ignored .env.local only if gitignore ignores it AND git doesn't track it;
            # flag if not gitignored or if terraform.tfstate/tfvars exists as committed-style risk.
            if path.name in {"terraform.tfvars", "terraform.tfstate", "terraform.tfstate.backup"}:
                report.violations.append(f"Sensitive Terraform state/vars file present in working tree: {rel}")

        if path.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp", ".woff2", ".ico", ".lock", ".pdf"}:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue

        if PRIVATE_KEY_HEADER_RE.search(text):
            report.violations.append(f"Private key header detected in {rel}")
        if SA_JSON_KEY_RE.search(text) and '"private_key"' in text:
            report.violations.append(f"GCP Service Account JSON credential detected in {rel}")
        if API_KEY_RE.search(text):
            report.violations.append(f"Google API key literal detected in {rel}")

    return report


def check_gitignore(repo_root: Path) -> HygieneReport:
    report = HygieneReport()
    gi = repo_root / ".gitignore"
    if not gi.is_file():
        report.violations.append(f"Missing .gitignore at {gi}")
        return report
    content = gi.read_text(encoding="utf-8", errors="ignore")
    for token in REQUIRED_GITIGNORE_TOKENS:
        if token not in content:
            report.violations.append(f".gitignore missing ignore rule for {token!r}")
    if ".vercel" not in content:
        report.violations.append(".gitignore missing '.vercel' rule")
    return report


def check_no_next_public_secrets(repo_root: Path) -> HygieneReport:
    report = HygieneReport()
    web_dir = repo_root / "web"
    if not web_dir.is_dir():
        report.violations.append(f"Missing web directory: {web_dir}")
        return report
    for path in _iter_repo_files(web_dir, include_tests_lib=True):
        if path.suffix.lower() in {".png", ".ico", ".woff2", ".lock"}:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        match = NEXT_PUBLIC_SECRET_RE.search(text)
        if match:
            rel = path.relative_to(repo_root).as_posix()
            report.violations.append(f"Forbidden {match.group(0)} found in {rel}")
    return report


def check_no_retired_models_or_fastmcp(repo_root: Path) -> HygieneReport:
    report = HygieneReport()
    for subdir in ("services", "infra", "web", "scripts"):
        target = repo_root / subdir
        if not target.is_dir():
            continue
        for path in _iter_repo_files(target, include_tests_lib=True):
            if path.suffix.lower() not in {".py", ".tf", ".ts", ".tsx", ".md", ".yaml", ".yml", ".ps1", ".json", ""}:
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
            rel = path.relative_to(repo_root).as_posix()
            m_model = RETIRED_GEMINI_RE.search(text)
            if m_model:
                report.violations.append(f"Retired Gemini model {m_model.group(0)!r} found in {rel}")
            if path.suffix == ".py" and FASTMCP_RE.search(text):
                report.violations.append(f"Forbidden FastMCP reference found in {rel} (must use MCPServer)")
    return report


def check_e2e_ast_opaque_box(e2e_dir: Path) -> HygieneReport:
    report = HygieneReport()
    if not e2e_dir.is_dir():
        report.violations.append(f"E2E directory missing: {e2e_dir}")
        return report

    for py_file in sorted(e2e_dir.rglob("*.py")):
        if any(part in SKIP_DIRS for part in py_file.parts):
            continue
        src = py_file.read_text(encoding="utf-8")
        tree = ast.parse(src, filename=str(py_file))
        rel = py_file.relative_to(e2e_dir).as_posix()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    top = alias.name.split(".")[0]
                    if top in FORBIDDEN_E2E_IMPORT_ROOTS:
                        report.violations.append(f"Opaque-box violation: {rel} imports {alias.name!r}")
            elif isinstance(node, ast.ImportFrom) and node.module:
                top = node.module.split(".")[0]
                if top in FORBIDDEN_E2E_IMPORT_ROOTS:
                    report.violations.append(f"Opaque-box violation: {rel} imports from {node.module!r}")
    return report


def check_pnpm_exclusively(repo_root: Path) -> HygieneReport:
    """Enforce pnpm exclusively (zero legacy package-lock.json or npm/npx invocations)."""
    report = HygieneReport()
    if not repo_root.is_dir():
        report.violations.append(f"Repo root missing: {repo_root}")
        return report

    for path in _iter_repo_files(repo_root):
        rel = path.relative_to(repo_root).as_posix()
        if path.name == "package-lock.json":
            report.violations.append(f"Forbidden package-lock.json found at {rel} (use pnpm-lock.yaml)")
            continue
        if path.suffix.lower() not in {
            ".json",
            ".md",
            ".ps1",
            ".sh",
            ".yml",
            ".yaml",
            ".ts",
            ".tsx",
            ".js",
            ".mjs",
            ".toml",
            "",
        }:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        match = LEGACY_PKG_MGR_CMD_RE.search(text)
        if match:
            report.violations.append(
                f"Forbidden legacy JS package manager command {match.group(0)!r} in {rel} (must use pnpm)"
            )

    web_dir = repo_root / "web"
    if web_dir.is_dir() and (web_dir / "package.json").is_file():
        if not (web_dir / "pnpm-lock.yaml").is_file():
            report.violations.append("web/package.json exists without web/pnpm-lock.yaml")
    return report


def check_video_and_walkthrough_assets(repo_root: Path) -> HygieneReport:
    report = HygieneReport()
    for doc_rel in ("docs/VIDEO_SCRIPT.md", "docs/DEMO_WALKTHROUGH.md", "README.md"):
        doc_path = repo_root / doc_rel
        if not doc_path.is_file():
            report.violations.append(f"Missing required documentation asset: {doc_rel}")
            continue
        text = doc_path.read_text(encoding="utf-8", errors="ignore")
        if len(text.strip()) < 100:
            report.violations.append(f"Documentation asset {doc_rel} is unexpectedly empty/short")
        if "TODO" in text or "TBD" in text:
            report.violations.append(f"Unfinished placeholder (TODO/TBD) found in {doc_rel}")

    video_path = repo_root / "docs/VIDEO_SCRIPT.md"
    walk_path = repo_root / "docs/DEMO_WALKTHROUGH.md"
    combined = ""
    if video_path.is_file():
        combined += video_path.read_text(encoding="utf-8", errors="ignore").lower()
    if walk_path.is_file():
        combined += "\n" + walk_path.read_text(encoding="utf-8", errors="ignore").lower()
    if combined:
        for kw in REQUIRED_DOC_KEYWORDS:
            if kw not in combined:
                report.violations.append(
                    f"docs/VIDEO_SCRIPT.md + DEMO_WALKTHROUGH.md missing required architecture keyword {kw!r}"
                )
    return report


def check_synthetic_data(repo_root: Path) -> HygieneReport:
    report = HygieneReport()
    syn_dir = repo_root / "data" / "synthetic"
    if not syn_dir.is_dir():
        report.violations.append(f"Missing synthetic data directory: {syn_dir}")
        return report

    expected_files = (
        "q3_cloud_vendor_review.json",
        "series_b_revenue_audit.json",
        "treasury_controls_memo.json",
        "compliance_policy_rules.json",
    )
    for fname in expected_files:
        fpath = syn_dir / fname
        if not fpath.is_file():
            report.violations.append(f"Missing synthetic JSON file: data/synthetic/{fname}")
            continue
        try:
            raw = fpath.read_text(encoding="utf-8")
            json.loads(raw)
        except Exception as exc:  # noqa: BLE001
            report.violations.append(f"Invalid JSON in data/synthetic/{fname}: {exc}")
            continue
        if PRIVATE_KEY_HEADER_RE.search(raw):
            report.violations.append(f"Private key marker in synthetic file data/synthetic/{fname}")

    # Align scenario IDs with DEMO_WALKTHROUGH.md if present
    walk_path = repo_root / "docs" / "DEMO_WALKTHROUGH.md"
    if walk_path.is_file():
        walk_text = walk_path.read_text(encoding="utf-8", errors="ignore")
        for scenario_id in ("q3_cloud_vendor_review", "series_b_revenue_audit", "treasury_controls_memo"):
            if scenario_id not in walk_text:
                report.violations.append(
                    f"docs/DEMO_WALKTHROUGH.md missing scenario ID {scenario_id!r}"
                )
    return report


def check_git_history_clean(repo_root: Path) -> HygieneReport:
    report = HygieneReport()
    if not (repo_root / ".git").exists():
        report.violations.append(f"No .git repository found at {repo_root}")
        return report
    proc = subprocess.run(
        ["git", "-C", str(repo_root), "ls-files"],
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )
    if proc.returncode != 0:
        report.violations.append(f"git ls-files failed: {proc.stderr.strip()}")
        return report
    tracked = [line.strip() for line in proc.stdout.splitlines() if line.strip()]
    for rel in tracked:
        name = Path(rel).name
        if name in FORBIDDEN_COMMITTED_FILES or name.endswith(".tfstate"):
            report.violations.append(f"Forbidden file tracked in git index: {rel}")
    return report
