from __future__ import annotations

import ast
import json
import subprocess
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[1]
OUT_JSON = ROOT / "reports" / "audit_module_migration_plan.json"
OUT_MD = ROOT / "reports" / "audit_module_migration_plan.md"

AUDIT_CANDIDATES = [
    "scripts/audit_source_freshness.py",
    "scripts/source_reliability_audit.py",
    "scripts/project_alignment_audit.py",
    "scripts/project_ownership_map.py",
    "scripts/route_static_reference_validation.py",
    "scripts/tree_final_sanity_report.py",
    "scripts/cleanup_closeout_handover.py",
    "scripts/verify_python_import_bootstrap.py",
    "scripts/health_check.ps1",
    "scripts/jom_health_check.ps1",
]

TARGET_MAP = {
    "scripts/audit_source_freshness.py": "app/audits/source_freshness.py",
    "scripts/source_reliability_audit.py": "app/audits/source_reliability.py",
    "scripts/project_alignment_audit.py": "app/audits/project_alignment.py",
    "scripts/project_ownership_map.py": "app/audits/project_ownership.py",
    "scripts/route_static_reference_validation.py": "app/audits/route_static_reference.py",
    "scripts/tree_final_sanity_report.py": "app/audits/tree_final_sanity.py",
    "scripts/cleanup_closeout_handover.py": "app/audits/cleanup_closeout.py",
    "scripts/verify_python_import_bootstrap.py": "app/audits/python_import_bootstrap_verify.py",
    "scripts/health_check.ps1": "scripts/health_check.ps1",
    "scripts/jom_health_check.ps1": "scripts/jom_health_check.ps1",
}

PHASES = [
    {
        "phase": "phase_0_plan_only",
        "purpose": "Produce migration plan only. No files moved.",
        "validation": ["git status clean before migration", "source reliability ok", "app scaffold exists"],
    },
    {
        "phase": "phase_1_lowest_risk_python_audits",
        "purpose": "Move report-only Python audit modules first and keep original scripts as wrappers.",
        "candidates": [
            "scripts/project_alignment_audit.py",
            "scripts/project_ownership_map.py",
            "scripts/route_static_reference_validation.py",
            "scripts/tree_final_sanity_report.py",
            "scripts/cleanup_closeout_handover.py",
        ],
        "validation": [
            "python scripts/project_alignment_audit.py",
            "python scripts/project_ownership_map.py",
            "python scripts/route_static_reference_validation.py",
            "python scripts/tree_final_sanity_report.py",
            "python scripts/cleanup_closeout_handover.py",
            "git status reviewed",
        ],
    },
    {
        "phase": "phase_2_runtime_source_audits",
        "purpose": "Move source freshness and reliability audits after report-only audits prove wrapper pattern.",
        "candidates": ["scripts/audit_source_freshness.py", "scripts/source_reliability_audit.py"],
        "validation": [
            "python scripts/audit_source_freshness.py",
            "python scripts/source_reliability_audit.py",
            "confirm static/data/source_reliability_status.json issue_count remains 0",
        ],
    },
    {
        "phase": "phase_3_bootstrap_verify_audit",
        "purpose": "Move bootstrap verification after core audit wrappers are stable.",
        "candidates": ["scripts/verify_python_import_bootstrap.py"],
        "validation": ["python scripts/verify_python_import_bootstrap.py", "compile_error_count remains 0"],
    },
    {
        "phase": "phase_4_powershell_health_checks_review_only",
        "purpose": "Do not move PowerShell health checks initially. Review whether they remain scripts or later become tools/maintenance.",
        "candidates": ["scripts/health_check.ps1", "scripts/jom_health_check.ps1"],
        "validation": ["No move in first audit migration pack"],
    },
]


def now_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


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
    outputs = []
    fetches = []
    errors = []
    try:
        tree = ast.parse(text)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imports.append(node.module)
    except Exception as exc:
        errors.append(str(exc))
    for token in ["reports/", "static/data/", "latest_run", "backups/"]:
        if token in text:
            outputs.append(token)
    for line in text.splitlines():
        if "OUT_" in line or "REPORT" in line or "STATUS" in line:
            if "=" in line:
                fetches.append(line.strip()[:180])
    return {
        "imports": sorted(set(imports)),
        "output_hints": sorted(set(outputs)),
        "constant_hints": fetches[:20],
        "parse_errors": errors,
    }


def candidate_row(candidate: str) -> Dict[str, Any]:
    path = ROOT / candidate
    exists = path.exists()
    suffix = path.suffix.lower()
    kind = "powershell" if suffix == ".ps1" else "python" if suffix == ".py" else "other"
    target = TARGET_MAP.get(candidate, candidate)
    wrapper_strategy = "retain_script_as_thin_wrapper" if kind == "python" and target != candidate else "retain_in_scripts_initially"
    analysis = parse_python(path) if exists and kind == "python" else {"imports": [], "output_hints": [], "constant_hints": [], "parse_errors": []}
    risk = "low"
    if candidate in {"scripts/audit_source_freshness.py", "scripts/source_reliability_audit.py"}:
        risk = "medium"
    if kind == "powershell":
        risk = "review_only"
    return {
        "file": candidate,
        "exists": exists,
        "kind": kind,
        "recommended_target": target,
        "wrapper_strategy": wrapper_strategy,
        "risk": risk,
        "analysis": analysis,
        "reason": "Audit/report module candidate for first controlled migration." if kind == "python" else "PowerShell health/scheduler-adjacent script; review before moving.",
    }


def write_markdown(payload: Dict[str, Any]) -> None:
    lines = []
    lines.append("# Audit Module Migration Plan")
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
    lines.append("## Recommended Migration Sequence")
    lines.append("")
    for phase in payload["phases"]:
        lines.append(f"### {phase['phase']}")
        lines.append(phase["purpose"])
        if "candidates" in phase:
            lines.append("")
            lines.append("Candidates:")
            for item in phase["candidates"]:
                lines.append(f"- `{item}`")
        lines.append("")
        lines.append("Validation:")
        for item in phase["validation"]:
            lines.append(f"- {item}")
        lines.append("")
    lines.append("## Candidate Map")
    lines.append("")
    for row in payload["candidates"]:
        lines.append(f"- `{row['file']}` → `{row['recommended_target']}` | risk: `{row['risk']}` | wrapper: `{row['wrapper_strategy']}`")
    lines.append("")
    lines.append("## Next Action")
    lines.append("")
    lines.append(payload["next_action"])
    OUT_MD.parent.mkdir(parents=True, exist_ok=True)
    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    candidates = [candidate_row(item) for item in AUDIT_CANDIDATES]
    kind_counts = Counter(row["kind"] for row in candidates)
    risk_counts = Counter(row["risk"] for row in candidates)
    payload: Dict[str, Any] = {
        "schema": "jom-audit-module-migration-plan-v1",
        "generated_at_utc": now_utc(),
        "mode": "report-only-no-file-moves",
        "summary": {
            "candidate_count": len(candidates),
            "existing_count": sum(1 for row in candidates if row["exists"]),
            "python_candidates": kind_counts.get("python", 0),
            "powershell_candidates": kind_counts.get("powershell", 0),
            "low_risk": risk_counts.get("low", 0),
            "medium_risk": risk_counts.get("medium", 0),
            "review_only": risk_counts.get("review_only", 0),
            "git_status_short": git(["status", "--short"]).get("stdout"),
        },
        "phases": PHASES,
        "candidates": candidates,
        "wrapper_pattern": {
            "description": "Move implementation to app/audits but keep scripts/<name>.py as the entry point wrapper.",
            "example_wrapper": "from app.audits.project_alignment import main\n\nif __name__ == '__main__':\n    raise SystemExit(main())\n",
        },
        "safety_rules": [
            "Move one group only, then validate and commit.",
            "Do not move PowerShell scripts in the first migration pack.",
            "Keep script filenames stable because scheduled/manual commands may call scripts directly.",
            "Do not move static/data output locations.",
            "After migration, run source freshness, source reliability, ownership map, and route/static validation.",
        ],
        "next_action": "Build Audit Module Migration Pack v1 for phase_1_lowest_risk_python_audits only, after this report is reviewed and committed.",
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
