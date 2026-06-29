from __future__ import annotations

import ast
import json
import re
import subprocess
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
OUT_JSON = ROOT / "reports" / "runtime_truth_builder_migration_plan.json"
OUT_MD = ROOT / "reports" / "runtime_truth_builder_migration_plan.md"

CANDIDATES = [
    "scripts/build_admin_truth_layer_v2.py",
    "scripts/build_estate_product_access.py",
    "scripts/refresh_admin_enriched_sources.py",
    "scripts/refresh_product_access_sources.py",
    "scripts/refresh_runtime_sources.py",
    "scripts/refresh_admin_enriched_chain.py",
    "scripts/run_operational_source_recovery.py",
    "scripts/backup_runtime_chain.py",
    "scripts/snapshot_controller.py",
    "scripts/sync_runtime.py",
]

TARGET_MAP = {
    "scripts/build_admin_truth_layer_v2.py": "app/builders/admin_truth_layer_v2.py",
    "scripts/build_estate_product_access.py": "app/builders/estate_product_access.py",
    "scripts/refresh_admin_enriched_sources.py": "app/builders/admin_enriched_sources.py",
    "scripts/refresh_product_access_sources.py": "app/builders/product_access_sources.py",
    "scripts/refresh_runtime_sources.py": "app/runtime/runtime_sources_refresh.py",
    "scripts/refresh_admin_enriched_chain.py": "app/runtime/admin_enriched_chain.py",
    "scripts/run_operational_source_recovery.py": "app/runtime/operational_source_recovery.py",
    "scripts/backup_runtime_chain.py": "app/runtime/runtime_backup_chain.py",
    "scripts/snapshot_controller.py": "app/runtime/snapshot_controller.py",
    "scripts/sync_runtime.py": "app/runtime/sync_runtime.py",
}

PHASES = [
    {
        "phase": "phase_0_plan_only",
        "purpose": "Map runtime truth builders and runtime orchestration scripts. No file moves.",
        "candidates": [],
        "validation": [
            "git status clean before movement",
            "python scripts/run_operational_snapshot.py",
            "python scripts/source_reliability_audit.py",
        ],
    },
    {
        "phase": "phase_1_reportable_truth_builders",
        "purpose": "Move relatively bounded truth builders first, keeping scripts as wrappers.",
        "candidates": [
            "scripts/build_admin_truth_layer_v2.py",
            "scripts/build_estate_product_access.py",
        ],
        "validation": [
            "python scripts/build_admin_truth_layer_v2.py",
            "python scripts/build_estate_product_access.py",
            "python scripts/run_operational_snapshot.py",
            "python scripts/source_reliability_audit.py",
        ],
    },
    {
        "phase": "phase_2_source_refresh_builders",
        "purpose": "Move source refresh builders after bounded builders are stable.",
        "candidates": [
            "scripts/refresh_admin_enriched_sources.py",
            "scripts/refresh_product_access_sources.py",
            "scripts/refresh_runtime_sources.py",
        ],
        "validation": [
            "python scripts/refresh_admin_enriched_sources.py",
            "python scripts/refresh_product_access_sources.py",
            "python scripts/refresh_runtime_sources.py",
            "python scripts/run_operational_snapshot.py",
            "confirm issue_count remains 0",
        ],
    },
    {
        "phase": "phase_3_runtime_chain_orchestration",
        "purpose": "Move orchestration/runtime chain scripts only after builders and refresh scripts are stable.",
        "candidates": [
            "scripts/refresh_admin_enriched_chain.py",
            "scripts/run_operational_source_recovery.py",
            "scripts/backup_runtime_chain.py",
        ],
        "validation": [
            "compile checks",
            "controlled runtime smoke tests",
            "no over-refresh / no scheduler changes",
        ],
    },
    {
        "phase": "phase_4_snapshot_and_scheduler_review",
        "purpose": "Review snapshot_controller.py and sync_runtime.py with scheduled execution before moving.",
        "candidates": [
            "scripts/snapshot_controller.py",
            "scripts/sync_runtime.py",
        ],
        "validation": [
            "scheduled task path review",
            "interval confirmation remains 3600 seconds where applicable",
            "manual snapshot remains functional",
        ],
    },
]

STATIC_OUTPUT_HINTS = [
    "admin_truth_v2.json",
    "estate_product_access.json",
    "estate_access_truth.json",
    "latest_run_admin_enriched.json",
    "latest_run_admin_enriched_pretty.json",
    "source_reliability_status.json",
    "source_freshness_audit.json",
    "runtime_refresh_status.json",
    "product_access_refresh_status.json",
    "admin_enriched_refresh_status.json",
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


def run(cmd: list[str]) -> dict[str, Any]:
    try:
        p = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, timeout=120)
        return {"cmd": " ".join(cmd), "returncode": p.returncode, "stdout": p.stdout.strip(), "stderr": p.stderr.strip()}
    except Exception as exc:
        return {"cmd": " ".join(cmd), "returncode": None, "error": str(exc)}


def parse_python(path: Path) -> dict[str, Any]:
    text = read_text(path)
    imports, funcs, parse_errors = [], [], []
    try:
        tree = ast.parse(text)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imports.append(node.module)
            elif isinstance(node, ast.FunctionDef):
                funcs.append(node.name)
    except Exception as exc:
        parse_errors.append(str(exc))

    output_hints = [hint for hint in STATIC_OUTPUT_HINTS if hint in text]
    path_hints = sorted(set(re.findall(r"(?:static[/\\]data|reports|latest_run|backups|snapshots)[A-Za-z0-9_./\\-]*\.(?:json|md|txt)", text)))
    root_patterns = []
    if "parents[1]" in text: root_patterns.append("parents[1]")
    if "parents[2]" in text: root_patterns.append("parents[2]")
    if "ensure_project_root_on_path" in text: root_patterns.append("bootstrap")
    main_style = "has_main" if "def main" in text else "script_style"
    return {
        "imports": sorted(set(imports)),
        "functions": funcs[:80],
        "parse_errors": parse_errors,
        "line_count": len(text.splitlines()),
        "output_hints": sorted(set(output_hints)),
        "path_hints": path_hints,
        "root_patterns": root_patterns,
        "main_style": main_style,
    }


def phase_for(candidate: str) -> str:
    for phase in PHASES:
        if candidate in phase.get("candidates", []):
            return phase["phase"]
    return "phase_0_plan_only"


def risk_for(candidate: str, analysis: dict[str, Any]) -> str:
    if candidate in {"scripts/build_admin_truth_layer_v2.py", "scripts/build_estate_product_access.py"}:
        return "high_truth_builder"
    if candidate in {"scripts/refresh_admin_enriched_sources.py", "scripts/refresh_product_access_sources.py", "scripts/refresh_runtime_sources.py"}:
        return "high_source_refresh"
    if candidate in {"scripts/refresh_admin_enriched_chain.py", "scripts/run_operational_source_recovery.py", "scripts/backup_runtime_chain.py"}:
        return "very_high_runtime_orchestration"
    if candidate in {"scripts/snapshot_controller.py", "scripts/sync_runtime.py"}:
        return "scheduler_runtime_review"
    return "review"


def row(candidate: str) -> dict[str, Any]:
    path = ROOT / candidate
    analysis = parse_python(path) if path.exists() else {}
    return {
        "file": candidate,
        "exists": path.exists(),
        "recommended_target": TARGET_MAP.get(candidate, candidate),
        "phase": phase_for(candidate),
        "risk": risk_for(candidate, analysis),
        "wrapper_strategy": "retain_script_entry_point_as_wrapper",
        "analysis": analysis,
    }


def write_md(payload: dict[str, Any]) -> None:
    lines = ["# Runtime Truth Builder Migration Plan", "", f"Generated: `{payload['generated_at_utc']}`", "", "## Mode", "", "Report-only. No files were moved.", "", "## Summary", ""]
    for k, v in payload["summary"].items():
        lines.append(f"- {k}: **{v}**")
    lines += ["", "## Recommended Phases", ""]
    for phase in payload["phases"]:
        lines.append(f"### {phase['phase']}")
        lines.append(phase["purpose"])
        if phase.get("candidates"):
            lines.append("")
            lines.append("Candidates:")
            for item in phase["candidates"]:
                lines.append(f"- `{item}` → `{TARGET_MAP.get(item, item)}`")
        lines.append("")
        lines.append("Validation:")
        for item in phase["validation"]:
            lines.append(f"- {item}")
        lines.append("")
    lines += ["## Candidate Map", ""]
    for r in payload["candidates"]:
        lines.append(f"- `{r['file']}` → `{r['recommended_target']}` | risk `{r['risk']}` | phase `{r['phase']}`")
    lines += ["", "## Safety Rules", ""]
    for rule in payload["safety_rules"]:
        lines.append(f"- {rule}")
    OUT_MD.parent.mkdir(parents=True, exist_ok=True)
    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    candidates = [row(c) for c in CANDIDATES]
    risk_counts = Counter(c["risk"] for c in candidates)
    phase_counts = Counter(c["phase"] for c in candidates)
    git_status = run(["git", "status", "--short"]).get("stdout", "")
    payload = {
        "schema": "jom-runtime-truth-builder-migration-plan-v1",
        "generated_at_utc": now_utc(),
        "mode": "report-only-no-file-moves",
        "summary": {
            "candidate_count": len(candidates),
            "existing_count": sum(1 for c in candidates if c["exists"]),
            "risk_counts": dict(sorted(risk_counts.items())),
            "phase_counts": dict(sorted(phase_counts.items())),
            "git_status_short": git_status,
        },
        "phases": PHASES,
        "candidates": candidates,
        "safety_rules": [
            "Do not move runtime-orchestration scripts before truth builders and source refresh builders are stable.",
            "Keep scripts/* entry points as wrappers after movement.",
            "Repair project-root path calculation to parents[2] for modules moved under app/*.",
            "Run operational snapshot after each migration family.",
            "Require source reliability issue_count = 0 after each migration family.",
            "Do not alter scheduler interval or scheduled task target in this migration plan.",
            "Commit each migration family separately.",
        ],
        "next_action": "Build Runtime Truth Builder Migration Pack v1 for phase_1_reportable_truth_builders only, after this plan is committed.",
    }
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    write_md(payload)
    print(json.dumps({"status": "ok", "mode": payload["mode"], "candidate_count": len(candidates), "existing_count": payload["summary"]["existing_count"], "json": str(OUT_JSON), "report": str(OUT_MD), "next_action": payload["next_action"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
