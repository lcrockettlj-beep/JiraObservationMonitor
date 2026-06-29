from __future__ import annotations

import ast
import json
import re
import subprocess
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[1]
OUT_JSON = ROOT / "reports" / "folder_structure_refactor_plan.json"
OUT_MD = ROOT / "reports" / "folder_structure_refactor_plan.md"

SKIP_DIRS = {".git", "__pycache__", ".venv", "venv", "node_modules", ".pytest_cache", ".mypy_cache"}

TARGET_STRUCTURE = {
    "app/__init__.py": "Application package marker.",
    "app/collectors/": "API/data collectors. These talk to external/internal source systems and write raw/near-raw source facts.",
    "app/builders/": "Transformers/builders. These convert source facts into runtime contracts under static/data or reports.",
    "app/audits/": "Validation, reliability, source freshness, ownership, route/static audits.",
    "app/runtime/": "Runtime orchestration and snapshot/sync helpers.",
    "app/access/": "Named access, group expansion, reconciliation, user footprint logic.",
    "app/registry/": "Site discovery, site registry, monitored-site approval/orchestration logic.",
    "app/shared/": "Reusable low-level helpers shared across builders/collectors/audits.",
    "scripts/": "Thin operational wrappers only. Scripts should call app modules rather than own large logic long-term.",
    "templates/": "Flask templates retained initially to avoid route breakage. Later split may be templates/home, templates/estate, templates/admin, templates/shared.",
    "static/css/": "CSS retained initially. Later split may be static/css/home, estate, admin, shared after template references are updated.",
    "static/js/": "JS retained initially. Later split may be static/js/home, estate, admin, shared after template references are updated.",
    "static/data/": "Runtime JSON data contracts consumed by the UI. Do not move until front-end fetch paths are abstracted.",
    "reports/": "Audit/reconciliation/diagnostic outputs. Later split by reports/access, reliability, structure, registry.",
    "backups/": "Backup and rollback history. Govern by retention policy, not ad-hoc deletion.",
    "docs/": "Documentation, manuals, governance, handover.",
    "config/": "Runtime configuration, feature flags, monitored site config."
}

AREA_RULES = [
    ("access", ["named_access", "user_footprint", "group_expansion", "reconcile_named", "admin_named_access"]),
    ("registry", ["site_registry", "site_discovery", "onboarding", "monitored_sites"]),
    ("audits", ["audit", "reliability", "freshness", "validation", "health_check", "ownership_map", "alignment", "sanity", "handover"]),
    ("builders", ["build_", "refresh_", "recovery", "truth", "product_access"]),
    ("collectors", ["collector", "client", "jira_client", "admin_api", "billing_catalog", "data_collector"]),
    ("runtime", ["runtime", "snapshot", "sync", "scheduler", "scheduled", "backup_runtime"]),
    ("web", ["web.py", "templates", "static", "theme", "dashboard", "home", "estate", "reference", "site"]),
    ("config", ["config", "feature_flags", "monitored_sites"]),
]

ROOT_ACTIVE_KEEP = {
    "web.py", "main.py", "auth.py", "jira_client.py", "data_collector.py", "admin_api_client.py",
    "admin_api_enrichment.py", "admin_named_access_collector.py", "site_discovery.py", "snapshots.py",
    "billing_catalog.py", "backend_contract.py", "reporting.py", "project_counts.py", "estate_metrics.py",
    "change_detection.py", "tier_engine.py", "trends.py", "intelligence.py", "intelligence_rules_engine.py",
    "alert_rules_engine.py", "auth_verification.py"
}


def now_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def is_skipped(path: Path) -> bool:
    return any(part in SKIP_DIRS for part in path.parts)


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


def scan_files() -> List[Path]:
    files = []
    for path in ROOT.rglob("*"):
        if path.is_file() and not is_skipped(path):
            files.append(path)
    return sorted(files, key=lambda p: rel(p))


def parse_imports(path: Path) -> List[str]:
    if path.suffix.lower() != ".py":
        return []
    text = read_text(path)
    try:
        tree = ast.parse(text)
    except Exception:
        return []
    imports = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.append(node.module.split(".")[0])
    return sorted(set(imports))


def infer_area(path: Path) -> str:
    rp = rel(path).lower()
    name = path.name.lower()
    for area, hints in AREA_RULES:
        if any(h in rp or h in name for h in hints):
            return area
    parts = path.relative_to(ROOT).parts
    if not parts:
        return "root"
    first = parts[0]
    if first == "backend":
        return "runtime"
    if first == "scripts":
        return "scripts_unclassified"
    if first == "reports":
        return "reports"
    if first == "docs":
        return "docs"
    if first == "config":
        return "config"
    if first == "static":
        return "web"
    if first == "templates":
        return "web"
    if first == "backups":
        return "backups"
    return "core"


def target_for(path: Path, area: str) -> Dict[str, Any]:
    rp = rel(path)
    name = path.name
    parts = path.relative_to(ROOT).parts
    suffix = path.suffix.lower()

    if parts and parts[0] in {"backups", "docs", "reports", "static", "templates", "config"}:
        return {
            "target": rp,
            "move_phase": "retain_initially",
            "reason": "Retain existing externally referenced path until references are abstracted or validated in a dedicated move phase."
        }

    if parts and parts[0] == "scripts":
        if area == "access": target = f"app/access/{name}"
        elif area == "registry": target = f"app/registry/{name}"
        elif area == "audits": target = f"app/audits/{name}"
        elif area == "builders": target = f"app/builders/{name}"
        elif area == "collectors": target = f"app/collectors/{name}"
        elif area == "runtime": target = f"app/runtime/{name}"
        else: target = f"app/shared/{name}"
        return {
            "target": target,
            "move_phase": "phase_2_logic_move_with_wrapper",
            "reason": "Move implementation into app package later, leaving a thin script wrapper at original path."
        }

    if len(parts) == 1 and suffix == ".py" and name in ROOT_ACTIVE_KEEP:
        if area == "collectors": target = f"app/collectors/{name}"
        elif area == "runtime": target = f"app/runtime/{name}"
        elif area == "access": target = f"app/access/{name}"
        elif area == "registry": target = f"app/registry/{name}"
        else: target = f"app/shared/{name}"
        return {
            "target": target,
            "move_phase": "phase_3_root_module_move_with_compatibility_shim",
            "reason": "Root Python module likely imported elsewhere. Move only with compatibility shim or import update pack."
        }

    if len(parts) == 1 and suffix in {".json", ".txt", ".zip"}:
        return {
            "target": rp,
            "move_phase": "retain_or_archive_by_policy",
            "reason": "Root runtime/support artifact. Archive or move only after source contract review."
        }

    return {
        "target": rp,
        "move_phase": "review",
        "reason": "No automatic move recommendation. Requires manual owner decision."
    }


def build_file_plan(files: List[Path]) -> List[Dict[str, Any]]:
    rows = []
    for path in files:
        area = infer_area(path)
        target = target_for(path, area)
        imports = parse_imports(path)
        rows.append({
            "file": rel(path),
            "area": area,
            "suffix": path.suffix.lower() or "<none>",
            "current_bucket": path.relative_to(ROOT).parts[0] if path.relative_to(ROOT).parts else "root",
            "recommended_target": target["target"],
            "move_phase": target["move_phase"],
            "reason": target["reason"],
            "python_imports": imports,
        })
    return rows


def migration_phases() -> List[Dict[str, Any]]:
    return [
        {
            "phase": "phase_0_no_moves_baseline",
            "purpose": "Keep current tree stable. Use reports to agree target structure.",
            "changes": ["No file moves", "No route changes", "No import changes"],
            "validation": ["git status clean", "source reliability ok", "python bootstrap safe"]
        },
        {
            "phase": "phase_1_create_empty_app_package",
            "purpose": "Add app package folders only, no code movement.",
            "changes": ["Create app/__init__.py", "Create app/collectors, builders, audits, runtime, access, registry, shared"],
            "validation": ["No runtime file paths changed", "Flask still starts", "scheduled task unaffected"]
        },
        {
            "phase": "phase_2_move_scripts_logic_with_wrappers",
            "purpose": "Move implementation logic from scripts into app modules, keep scripts as stable entry-point wrappers.",
            "changes": ["One family at a time", "access first or audits first", "scripts keep original filenames as wrappers"],
            "validation": ["Run affected script", "source reliability audit", "git commit after each family"]
        },
        {
            "phase": "phase_3_move_root_modules_with_shims",
            "purpose": "Move root Python modules into app package while keeping compatibility shims at root initially.",
            "changes": ["Move one module group", "Root file imports from app.<area>", "Update direct imports gradually"],
            "validation": ["py_compile all scripts", "collector smoke tests", "web.py smoke test"]
        },
        {
            "phase": "phase_4_web_layer_split",
            "purpose": "Split web.py routes/templates/static only after app logic is stable.",
            "changes": ["Blueprints/routes", "Template grouping", "Static path abstraction if needed"],
            "validation": ["Route/static validation", "manual UI smoke test Home/Estate/Admin/Site"]
        },
        {
            "phase": "phase_5_backup_retention_policy",
            "purpose": "Reduce backup volume with explicit retention rules.",
            "changes": ["Keep gold baselines", "Compress or prune old runtime history", "Never remove _project_cleanup_archive without confirmation"],
            "validation": ["Rollback scripts retained", "backups/latest_runtime/current retained"]
        }
    ]


def risk_register(file_plan: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [
        {
            "risk": "Python import breakage",
            "why_it_matters": "Root modules and scripts currently import each other directly.",
            "mitigation": "Use scripts/_project_bootstrap.py, move one module family at a time, keep wrappers/shims until all imports are updated."
        },
        {
            "risk": "Flask template/static path breakage",
            "why_it_matters": "Templates and JS/CSS paths are referenced by web.py and browser fetch/link tags.",
            "mitigation": "Do not move templates/static in early phases. Run route_static_reference_validation before and after any move."
        },
        {
            "risk": "Scheduled task points at old path",
            "why_it_matters": "JOM_Sync_Runtime executes scripts/run_sync_for_scheduler.cmd.",
            "mitigation": "Keep scheduler wrapper path stable; update scheduled task only in a dedicated scheduler pack."
        },
        {
            "risk": "Runtime JSON contract breakage",
            "why_it_matters": "UI reads static/data JSON files directly.",
            "mitigation": "Do not move static/data until fetch paths are centralised or the UI data loader is abstracted."
        },
        {
            "risk": "Backup rollback loss",
            "why_it_matters": "Recent cleanup relies on rollback scripts in backups/_project_cleanup_archive.",
            "mitigation": "Do not prune cleanup archives until a new gold baseline has existed for multiple successful runs."
        }
    ]


def write_markdown(payload: Dict[str, Any]) -> None:
    lines = []
    lines.append("# Folder Structure Refactor Plan")
    lines.append("")
    lines.append(f"Generated: `{payload['generated_at_utc']}`")
    lines.append("")
    lines.append("## Mode")
    lines.append("")
    lines.append("This is a report-only plan. No files were moved by this pack.")
    lines.append("")
    lines.append("## Current Summary")
    lines.append("")
    for key, value in payload["summary"].items():
        if isinstance(value, dict):
            continue
        lines.append(f"- {key}: **{value}**")
    lines.append("")
    lines.append("## Target Structure")
    lines.append("")
    for folder, purpose in payload["target_structure"].items():
        lines.append(f"- `{folder}` — {purpose}")
    lines.append("")
    lines.append("## Migration Phases")
    lines.append("")
    for phase in payload["migration_phases"]:
        lines.append(f"### {phase['phase']}")
        lines.append("")
        lines.append(phase["purpose"])
        lines.append("")
        lines.append("Changes:")
        for change in phase["changes"]:
            lines.append(f"- {change}")
        lines.append("")
        lines.append("Validation:")
        for check in phase["validation"]:
            lines.append(f"- {check}")
        lines.append("")
    lines.append("## Risk Register")
    lines.append("")
    for risk in payload["risk_register"]:
        lines.append(f"- **{risk['risk']}** — {risk['why_it_matters']} Mitigation: {risk['mitigation']}")
    lines.append("")
    lines.append("## Recommended First Actual Change")
    lines.append("")
    lines.append("Create the empty `app/` package structure only. Do not move logic until the empty-package commit is stable.")
    lines.append("")
    lines.append("## High-Value Move Candidates")
    lines.append("")
    candidates = [row for row in payload["file_plan"] if row["move_phase"] in {"phase_2_logic_move_with_wrapper", "phase_3_root_module_move_with_compatibility_shim"}]
    for row in candidates[:80]:
        lines.append(f"- `{row['file']}` → `{row['recommended_target']}` ({row['move_phase']})")
    OUT_MD.parent.mkdir(parents=True, exist_ok=True)
    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    files = scan_files()
    file_plan = build_file_plan(files)
    area_counts = Counter(row["area"] for row in file_plan)
    phase_counts = Counter(row["move_phase"] for row in file_plan)
    payload: Dict[str, Any] = {
        "schema": "jom-folder-structure-refactor-plan-v1",
        "generated_at_utc": now_utc(),
        "mode": "report-only-no-file-moves",
        "summary": {
            "files_scanned": len(files),
            "area_counts": dict(sorted(area_counts.items())),
            "move_phase_counts": dict(sorted(phase_counts.items())),
            "git_status_short": git(["status", "--short"]).get("stdout"),
        },
        "target_structure": TARGET_STRUCTURE,
        "migration_phases": migration_phases(),
        "risk_register": risk_register(file_plan),
        "file_plan": file_plan,
        "next_action": "Build Empty App Package Scaffold Pack only after this report is reviewed and committed.",
    }
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    write_markdown(payload)
    print(json.dumps({
        "status": "ok",
        "mode": payload["mode"],
        "files_scanned": len(files),
        "json": str(OUT_JSON),
        "report": str(OUT_MD),
        "next_action": payload["next_action"],
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
