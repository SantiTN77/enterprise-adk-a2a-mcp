from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import hcl2

FORBIDDEN_PUBLIC_PRINCIPALS = {"allUsers", "allAuthenticatedUsers"}
FORBIDDEN_ALWAYS_ON_RESOURCES = {
    "google_vertex_ai_index_endpoint",
    "google_container_cluster",
    "google_sql_database_instance",
    "google_compute_instance",
    "google_redis_instance",
    "google_memcache_instance",
    "google_vpc_access_connector",
}
RETIRED_MODEL_MARKERS = ("gemini-2.0", "gemini-2.5", "gemini-1.")


@dataclass
class TerraformPolicyReport:
    tf_files: list[Path] = field(default_factory=list)
    cloud_run_services: list[str] = field(default_factory=list)
    service_accounts: list[str] = field(default_factory=list)
    iam_members: list[dict[str, Any]] = field(default_factory=list)
    violations: list[str] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return len(self.violations) == 0


def _unquote(val: Any) -> Any:
    if isinstance(val, str) and len(val) >= 2 and val.startswith('"') and val.endswith('"'):
        return val[1:-1]
    return val


def _normalize_hcl(obj: Any) -> Any:
    """Normalize python-hcl2 v6/v7/v8 ASTs (stripping v8 quoted keys/strings and __is_block__)."""
    if isinstance(obj, dict):
        out: dict[str, Any] = {}
        for k, v in obj.items():
            nk = _unquote(k)
            if nk == "__is_block__":
                continue
            out[nk] = _normalize_hcl(v)
        return out
    if isinstance(obj, list):
        return [_normalize_hcl(item) for item in obj]
    return _unquote(obj)


def _unwrap_list_item(val: Any) -> Any:
    if isinstance(val, list) and len(val) == 1:
        return val[0]
    return val


def _extract_scaling(service_body: dict[str, Any]) -> tuple[Any, Any]:
    template = _unwrap_list_item(service_body.get("template"))
    if not isinstance(template, dict):
        return None, None
    scaling = _unwrap_list_item(template.get("scaling"))
    if not isinstance(scaling, dict):
        return None, None
    return scaling.get("min_instance_count"), scaling.get("max_instance_count")


def _flatten_strings(obj: Any) -> list[str]:
    found: list[str] = []
    if isinstance(obj, str):
        found.append(obj)
    elif isinstance(obj, dict):
        for k, v in obj.items():
            found.append(str(k))
            found.extend(_flatten_strings(v))
    elif isinstance(obj, list):
        for item in obj:
            found.extend(_flatten_strings(item))
    return found


def evaluate_terraform_directory(tf_dir: Path) -> TerraformPolicyReport:
    report = TerraformPolicyReport()
    if not tf_dir.is_dir():
        report.violations.append(f"Terraform directory missing: {tf_dir}")
        return report

    tf_files = sorted(tf_dir.glob("*.tf"))
    if not tf_files:
        report.violations.append(f"No .tf files found in {tf_dir}")
        return report
    report.tf_files = tf_files

    parsed_docs: list[tuple[Path, dict[str, Any]]] = []
    for path in tf_files:
        try:
            with path.open("r", encoding="utf-8") as fh:
                parsed_docs.append((path, _normalize_hcl(hcl2.load(fh))))
        except Exception as exc:  # noqa: BLE001
            report.violations.append(f"HCL parse error in {path.name}: {exc}")

    # Track variable defaults from variables.tf and *.tfvars.example
    var_defaults: dict[str, Any] = {}
    for path, doc in parsed_docs:
        for var_block in doc.get("variable", []):
            if isinstance(var_block, dict):
                for var_name, body in var_block.items():
                    if isinstance(body, dict) and "default" in body:
                        var_defaults[var_name] = body["default"]

        raw_text = path.read_text(encoding="utf-8", errors="replace")
        # Strip HCL line/block comments before raw-text scans so explanatory comments
        # like "# ZERO allUsers" or "# Never gemini-2.0" do not trigger false positives.
        code_lines = [
            ln for ln in raw_text.splitlines() if not ln.lstrip().startswith(("#", "//"))
        ]
        code_only = "\n".join(code_lines)
        for retired in RETIRED_MODEL_MARKERS:
            if retired in code_only.lower():
                report.violations.append(f"Retired Gemini model {retired!r} found in {path.name}")
        for public_principal in FORBIDDEN_PUBLIC_PRINCIPALS:
            if public_principal in code_only:
                report.violations.append(
                    f"Forbidden public IAM principal {public_principal!r} referenced in {path.name}"
                )

    for path, doc in parsed_docs:
        for res_block in doc.get("resource", []):
            if not isinstance(res_block, dict):
                continue
            for res_type, instances in res_block.items():
                if res_type in FORBIDDEN_ALWAYS_ON_RESOURCES:
                    report.violations.append(
                        f"Forbidden always-on paid resource {res_type!r} in {path.name}"
                    )

                if not isinstance(instances, dict):
                    continue

                for res_name, body in instances.items():
                    if not isinstance(body, dict):
                        continue

                    if res_type == "google_service_account":
                        report.service_accounts.append(res_name)

                    if res_type == "google_cloud_run_v2_service":
                        report.cloud_run_services.append(res_name)

                        deletion_prot = body.get("deletion_protection")
                        if deletion_prot is not False:
                            report.violations.append(
                                f"{path.name}:{res_name} must explicitly set deletion_protection = false "
                                f"(found {deletion_prot!r})"
                            )

                        min_inst, max_inst = _extract_scaling(body)
                        if isinstance(min_inst, str) and min_inst.startswith("${var."):
                            vname = min_inst[6:-1]
                            min_inst = var_defaults.get(vname, min_inst)
                        if isinstance(max_inst, str) and max_inst.startswith("${var."):
                            vname = max_inst[6:-1]
                            max_inst = var_defaults.get(vname, max_inst)

                        if min_inst != 0:
                            report.violations.append(
                                f"{path.name}:{res_name} must enforce min_instance_count = 0 (found {min_inst!r})"
                            )
                        if not isinstance(max_inst, int) or max_inst < 1 or max_inst > 2:
                            report.violations.append(
                                f"{path.name}:{res_name} must enforce 1 <= max_instance_count <= 2 "
                                f"(found {max_inst!r})"
                            )

                        # Check template-level env vars for retired models
                        for s in _flatten_strings(body):
                            low = s.lower()
                            for retired in RETIRED_MODEL_MARKERS:
                                if retired in low:
                                    report.violations.append(
                                        f"{path.name}:{res_name} references retired Gemini model {retired!r}"
                                    )

                    if res_type in {
                        "google_cloud_run_v2_service_iam_member",
                        "google_cloud_run_v2_service_iam_binding",
                        "google_cloud_run_v2_service_iam_policy",
                    }:
                        all_vals = _flatten_strings(body)
                        for s in all_vals:
                            if any(pub in s for pub in FORBIDDEN_PUBLIC_PRINCIPALS):
                                report.violations.append(
                                    f"{path.name}:{res_name} grants public Cloud Run IAM access ({s!r})"
                                )
                        role = body.get("role")
                        if res_type == "google_cloud_run_v2_service_iam_member":
                            report.iam_members.append(
                                {
                                    "resource": res_name,
                                    "role": role,
                                    "member": body.get("member"),
                                    "name": body.get("name"),
                                }
                            )
                            if role in {"roles/run.admin", "roles/owner", "roles/editor"}:
                                report.violations.append(
                                    f"{path.name}:{res_name} uses overly permissive role {role!r}"
                                )
                        else:
                            report.violations.append(
                                f"{path.name}:{res_name} uses authoritative {res_type}; "
                                "use least-privilege google_cloud_run_v2_service_iam_member instead"
                            )

    if len(report.cloud_run_services) < 3:
        report.violations.append(
            f"Expected >= 3 google_cloud_run_v2_service resources (orchestrator + 2 agents), "
            f"found {len(report.cloud_run_services)}: {report.cloud_run_services}"
        )

    invoker_bindings = [m for m in report.iam_members if m.get("role") == "roles/run.invoker"]
    if len(invoker_bindings) < 3:
        report.violations.append(
            f"Expected >= 3 least-privilege roles/run.invoker bindings across Cloud Run services, "
            f"found {len(invoker_bindings)}"
        )

    return report


def check_terraform_defaults(tf_dir: Path) -> list[str]:
    violations: list[str] = []
    vars_file = tf_dir / "variables.tf"
    if not vars_file.is_file():
        return [f"Missing {vars_file}"]

    with vars_file.open("r", encoding="utf-8") as fh:
        doc = _normalize_hcl(hcl2.load(fh))

    raw_vars = vars_file.read_text(encoding="utf-8")
    for retired in RETIRED_MODEL_MARKERS:
        if retired in raw_vars.lower():
            violations.append(f"Retired Gemini model {retired!r} in variables.tf")
    if "BEGIN PRIVATE KEY" in raw_vars:
        violations.append("Private key literal found in variables.tf")

    tfvars_example = tf_dir / "terraform.tfvars.example"
    if not tfvars_example.is_file():
        violations.append(f"Missing {tfvars_example}")
    else:
        ex_text = tfvars_example.read_text(encoding="utf-8")
        for retired in RETIRED_MODEL_MARKERS:
            if retired in ex_text.lower():
                violations.append(f"Retired Gemini model {retired!r} in terraform.tfvars.example")
        if "BEGIN PRIVATE KEY" in ex_text:
            violations.append("Private key literal found in terraform.tfvars.example")

    defaults: dict[str, Any] = {}
    for var_block in doc.get("variable", []):
        if isinstance(var_block, dict):
            for k, v in var_block.items():
                if isinstance(v, dict) and "default" in v:
                    defaults[k] = v["default"]

    # Check location/model defaults if declared
    for key, val in defaults.items():
        if isinstance(val, str):
            low = val.lower()
            if "model" in key.lower() and any(r in low for r in RETIRED_MODEL_MARKERS):
                violations.append(f"Variable {key} defaults to retired model {val!r}")
    return violations


def run_terraform_cli_checks(tf_dir: Path) -> tuple[bool, str]:
    """Run terraform fmt -check and terraform validate if terraform CLI is installed."""
    tf_bin = shutil.which("terraform")
    if not tf_bin:
        return True, "SKIPPED_CLI: terraform binary not installed on PATH; HCL AST checks executed."

    fmt_proc = subprocess.run(
        [tf_bin, f"-chdir={tf_dir}", "fmt", "-check", "-recursive"],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    if fmt_proc.returncode != 0:
        return False, f"terraform fmt -check failed: {fmt_proc.stdout} {fmt_proc.stderr}"

    init_proc = subprocess.run(
        [tf_bin, f"-chdir={tf_dir}", "init", "-backend=false", "-input=false"],
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    if init_proc.returncode != 0:
        return False, f"terraform init -backend=false failed: {init_proc.stdout} {init_proc.stderr}"

    val_proc = subprocess.run(
        [tf_bin, f"-chdir={tf_dir}", "validate"],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    if val_proc.returncode != 0:
        return False, f"terraform validate failed: {val_proc.stdout} {val_proc.stderr}"

    return True, "terraform fmt -check and terraform validate passed."
