from __future__ import annotations

import ast
import json
import re
import subprocess
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[1]
OUT_JSON = ROOT / "reports" / "builder_module_migration_plan.json"
OUT_MD = ROOT / "reports" / "builder_module_migration_plan.md"

BUILDER_CANDIDATES = [
    "scripts/build_admin_truth_layer_v2.py",
    "scripts/build_estate_product_access.py",
    "scripts/build_named_access_reconciliation.py",
    "scripts/build_named_access_recovery_plan.py",
    "scripts/build_named_access_truth_v2.py",
    "scripts/build_site_registry.py",
    "scripts/build_user_footprint_source.py",
    "scripts/reconcile_named_access_truth_v2.py",
    "scripts/refresh_admin_enriched_sources.py",
    "scripts/refresh_admin_enriched_chain.py",
    "scripts/refresh_product_access_sources.py",
    "scripts/refresh_runtime_sources.py",
    "scripts/run_named_access_recovery_implementation.py",
    "scripts/run_operational_source_recovery.py",
    "scripts/run_user_footprint_unlock.py",
    "scripts/run_group_expansion_recovery.py",
]

TARGET_MAP = {
    "scripts/build_admin_truth_layer_v2.py": "app/builders/admin_truth_layer_v2.py",
    "scripts/build_estate_product_access.py": "app/builders/estate_product_access.py",
    "scripts/build_named_access_reconciliation.py": "app/access/named_access_reconciliation.py",
    "scripts/build_named_access_recovery_plan.py": "app/access/named_access_recovery_plan.py",
    "scripts/build_named_access_truth_v2.py": "app/access/named_access_truth_v2.py",
    "scripts/build_site_registry.py": "app/registry/site_registry_builder.py",
    "scripts/build_user_footprint_source.py": "app/access/user_footprint_source.py",
    "scripts/reconcile_named_access_truth_v2.py": "app/access/reconcile_named_access_truth_v2.py",
    "scripts/refresh_admin_enriched_sources.py": "app/builders/admin_enriched_sources.py",
    "scripts/refresh_admin_enriched_chain.py": "app/runtime/admin_enriched_chain.py",
    "scripts/refresh_product_access_sources.py": "app/builders/product_access_sources.py",
    "scripts/refresh_runtime_sources.py": "app/runtime/runtime_sources_refresh.py",
    "scripts/run_named_access_recovery_implementation.py": "app/access/named_access_recovery_runner.py",
    "scripts/run_operational_source_recovery.py": "app/runtime/operational_source_recovery.py",
    "scripts/run_user_footprint_unlock.py": "app/access/user_footprint_unlock_runner.py",
    "scripts/run_group_expansion_recovery.py": "app/access/group_expansion_recovery_runner.py",
}

LOWEST_RISK_FIRST = [
    "scripts/build_named_access_recovery_plan.py",
    "scripts/build_named_access_reconciliation.py",
    "scripts/reconcile_named_access_truth_v2.py",
]

MEDIUM_RISK_ACCESS = [
    "scripts/build_named_access_truth_v2.py",
    "scripts/build_user_footprint_source.py",
    "scripts/run_user_footprint_unlock.py",
    "scripts/run_group_expansion_recovery.py",
    "scripts/run_named_access_recovery_implementation.py",
]

HIGHER_RISK_RUNTIME = [
    "scripts/build_admin_truth_layer_v2.py",
    "scripts/build_estate_product_access.py",
    "scripts/refresh_admin_enriched_sources.py",
    "scripts/refresh_admin_enriched_chain.py",
    "scripts/refresh_product_access_sources.py",
    "scripts/refresh_runtime_sources.py",
    "scripts/run_operational_source_recovery.py",
]

REGISTRY_RISK = [
    "scripts/build_site_registry.py",
]

PHASES = [
    {
        "phase": "phase_0_plan_only",
        "purpose": "Map builder/runtime/access scripts without moving files.",
        "candidates": [],
        "validation": ["git status clean", "audit layer already migrated", "source reliability issue_count 0"],
    },
    {
        "phase": "phase_1_lowest_risk_access_reports",
        "purpose": "Move named-access report/reconciliation plan modules first. These are lower risk than live collector/runtime writers.",
        "candidates": LOWEST_RISK_FIRST,
        "validation": [
            "python scripts/build_named_access_recovery_plan.py",
            "python scripts/build_named_access_reconciliation.py",
            "python scripts/reconcile_named_access_truth_v2.py",
            "python scripts/source_reliability_audit.py",
        ],
    },
    {
        "phase": "phase_2_access_truth_builders",
        "purpose": "Move access truth/user footprint builders after low-risk wrappers are proven.",
        "candidates": MEDIUM_RISK_ACCESS,
        "validation": [
            "python scripts/build_named_access_truth_v2.py",
            "python scripts/build_user_footprint_source.py",
            "python scripts/source_reliability_audit.py",
            "confirm user_footprint_status remains generated",
        ],
    },
    {
        "phase": "phase_3_site_registry_builder",
        "purpose": "Move registry builder independently to reduce blast radius around monitored/unmonitored site truths.",
        "candidates": REGISTRY_RISK,
        "validation": [
            "python scripts/build_site_registry.py",
            "python scripts/route_static_reference_validation.py",
            "confirm monitored sites unchanged",
        ],
    },
    {
        "phase": "phase_4_runtime_truth_builders",
        "purpose": "Move admin/estate/product/runtime source builders only after access and registry layers are stable.",
        "candidates": HIGHER_RISK_RUNTIME,
        "validation": [
            "python scripts/build_admin_truth_layer_v2.py",
            "python scripts/build_estate_product_access.py",
            "python scripts/refresh_runtime_sources.py",
            "python scripts/source_reliability_audit.py",
            "confirm issue_count remains 0",
        ],
    },
]


def now_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return ""


def git(args: List[str]) -> Dict[str, Any]:
    try:
        proc = subprocess.run(["git"] + args, cwd=ROOT, capture_output=True, text=True, timeout=60)
        return {"returncode": proc.returncode, "stdout": proc.stdout.strip(), "stderr": proc.stderr.strip()}
    except Exception as exc:
        return {"returncode": None, "error": str(exc)}


def parse_python(path: Path) -> Dict[str, Any]:
    text = read_text(path)
    imports = []
    parse_errors = []
    try:
        tree = ast.parse(text)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imports.append(node.module)
    except Exception as exc:
        parse_errors.append(str(exc))

    write_targets = sorted(set(re.findall(r"(?:static[/\\]data|reports|latest_run|backups)[A-Za-z0-9_./\\-]*\.(?:json|md|txt)", text)))
    root_patterns = []
    if "Path(__file__).resolve().parents[1]" in text:
        root_patterns.append("parents[1]")
    if "Path(__file__).resolve().parents[2]" in text:
        root_patterns.append("parents[2]")
    if "ensure_project_root_on_path" in text:
        root_patterns.append("bootstrap")

    return {
        "imports": sorted(set(imports)),
        "write_targets": write_targets,
        "root_patterns": root_patterns,
        "parse_errors": parse_errors,
        "mentions_static_data": "static" in text and "data" in text,
        "mentions_reports": "reports" in text,
    }


def classify_risk(candidate: str, analysis: Dict[str, Any]) -> str:
    if candidate in LOWEST_RISK_FIRST:
        return "low"
    if candidate in MEDIUM_RISK_ACCESS:
        return "medium"
    if candidate in REGISTRY_RISK:
        return "medium_registry"
    if candidate in HIGHER_RISK_RUNTIME:
        return "high_runtime_truth"
    if analysis.get("write_targets"):
        return "review_writer"
    return "review"


def candidate_row(candidate: str) -> Dict[str, Any]:
    path = ROOT / candidate
    exists = path.exists()
    analysis = parse_python(path) if exists and path.suffix.lower() == ".py" else {}
    risk = classify_risk(candidate, analysis)
    return {
        "file": candidate,
        "exists": exists,
        "recommended_target": TARGET_MAP.get(candidate, candidate),
        "risk": risk,
        "wrapper_strategy": "retain_script_as_thin_wrapper",
        "analysis": analysis,
        "phase": next((p["phase"] for p in PHASES if candidate in p.get("candidates", [])), "unassigned"),
    }


def write_markdown(payload: Dict[str, Any]) -> None:
    lines = []
    lines.append("# Builder Module Migration Plan")
    lines.append("")
    lines.append(f"Generated: `{payload['generated_at_utc']}`")
    lines.append("")
    lines.append("## Mode")
    lines.append("")
    lines.append("Report-only. No files were moved and no imports were changed.")
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    for key, value in payload["summary"].items():
        lines.append(f"- {key}: **{value}**")
    lines.append("")
    lines.append("## Recommended Migration Phases")
    lines.append("")
    for phase in payload["phases"]:
        lines.append(f"### {phase['phase']}")
        lines.append(phase["purpose"])
        lines.append("")
        if phase.get("candidates"):
            lines.append("Candidates:")
            for item in phase["candidates"]:
                lines.append(f"- `{item}` → `{TARGET_MAP.get(item, item)}`")
            lines.append("")
        lines.append("Validation:")
        for item in phase["validation"]:
            lines.append(f"- {item}")
        lines.append("")
    lines.append("## Candidate Map")
    lines.append("")
    for row in payload["candidates"]:
        lines.append(f"- `{row['file']}` → `{row['recommended_target']}` | risk `{row['risk']}` | phase `{row['phase']}`")
    lines.append("")
    lines.append("## Safety Rules")
    lines.append("")
    for rule in payload["safety_rules"]:
        lines.append(f"- {rule}")
    OUT_MD.parent.mkdir(parents=True, exist_ok=True)
    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    candidates = [candidate_row(item) for item in BUILDER_CANDIDATES]
    risk_counts = Counter(row["risk"] for row in candidates)
    phase_counts = Counter(row["phase"] for row in candidates)
    payload: Dict[str, Any] = {
        "schema": "jom-builder-module-migration-plan-v1",
        "generated_at_utc": now_utc(),
        "mode": "report-only-no-file-moves",
        "summary": {
            "candidate_count": len(candidates),
            "existing_count": sum(1 for row in candidates if row["exists"]),
            "risk_counts": dict(sorted(risk_counts.items())),
            "phase_counts": dict(sorted(phase_counts.items())),
            "git_status_short": git(["status", "--short"]).get("stdout"),
        },
        "phases": PHASES,
        "candidates": candidates,
        "wrapper_pattern": "scripts/<name>.py remains wrapper; app/<area>/<name>.py owns implementation.",
        "safety_rules": [
            "Do not move runtime-truth builders first.",
            "Use the proven wrapper pattern from app/audits migration.",
            "Repair ROOT path to parents[2] for modules moved under app/<area>/.",
            "Keep static/data output paths unchanged.",
            "Validate source reliability after each builder family.",
            "Commit each family separately.",
        ],
        "next_action": "Build Builder Module Migration Pack v1 for phase_1_lowest_risk_access_reports only.",
    }
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    write_markdown(payload)
    print(json.dumps({
        "status": "ok",
        "mode": payload["mode"],
        "candidate_count": len(candidates),
        "existing_count": payload["summary"]["existing_count"],
        "json": str(OUT_JSON),
        "report": str(OUT_MD),
        "next_action": payload["next_action"],
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
