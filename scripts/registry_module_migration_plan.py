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
OUT_JSON = ROOT / "reports" / "registry_module_migration_plan.json"
OUT_MD = ROOT / "reports" / "registry_module_migration_plan.md"

REGISTRY_CANDIDATES = [
    "scripts/build_site_registry.py",
    "backend/site_registry_runtime.py",
    "site_discovery.py",
    "config/monitored_sites.json",
    "static/data/site_registry.json",
]

TARGET_MAP = {
    "scripts/build_site_registry.py": "app/registry/site_registry_builder.py",
    "backend/site_registry_runtime.py": "app/registry/site_registry_runtime.py",
    "site_discovery.py": "app/registry/site_discovery.py",
    "config/monitored_sites.json": "config/monitored_sites.json",
    "static/data/site_registry.json": "static/data/site_registry.json",
}

PHASES = [
    {
        "phase": "phase_0_plan_only",
        "purpose": "Map registry source files and references. No files moved.",
        "candidates": [],
        "validation": [
            "git status clean before movement",
            "source reliability issue_count 0",
            "route/static validation ok",
        ],
    },
    {
        "phase": "phase_1_builder_only_with_wrapper",
        "purpose": "Move the site registry builder implementation only. Keep scripts/build_site_registry.py as wrapper.",
        "candidates": ["scripts/build_site_registry.py"],
        "validation": [
            "python scripts/build_site_registry.py",
            "python scripts/source_reliability_audit.py",
            "confirm static/data/site_registry.json still exists",
            "confirm monitored site list unchanged unless intentionally regenerated",
        ],
    },
    {
        "phase": "phase_2_runtime_adapter_with_shim",
        "purpose": "Move backend/site_registry_runtime.py after builder-only wrapper pattern is proven. Keep a backend compatibility shim.",
        "candidates": ["backend/site_registry_runtime.py"],
        "validation": [
            "python -m py_compile backend/site_registry_runtime.py app/registry/site_registry_runtime.py",
            "Flask import smoke test if web.py imports backend.site_registry_runtime",
            "python scripts/route_static_reference_validation.py",
        ],
    },
    {
        "phase": "phase_3_site_discovery_review",
        "purpose": "Review root site_discovery.py separately. This may be collector/registry hybrid and should not be moved until imports are mapped.",
        "candidates": ["site_discovery.py"],
        "validation": [
            "import smoke test",
            "site discovery report/update checks",
            "approval/onboarding safety boundary review",
        ],
    },
    {
        "phase": "phase_4_config_and_data_retain",
        "purpose": "Do not move config or static data contracts. Registry JSON and monitored-site config remain stable paths.",
        "candidates": ["config/monitored_sites.json", "static/data/site_registry.json"],
        "validation": [
            "path remains unchanged",
            "UI and runtime references remain valid",
        ],
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
    errors = []
    if path.suffix.lower() == ".py":
        try:
            tree = ast.parse(text)
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    imports.extend(alias.name for alias in node.names)
                elif isinstance(node, ast.ImportFrom) and node.module:
                    imports.append(node.module)
        except Exception as exc:
            errors.append(str(exc))
    root_patterns = []
    if "Path(__file__).resolve().parents[1]" in text: root_patterns.append("parents[1]")
    if "Path(__file__).resolve().parents[2]" in text: root_patterns.append("parents[2]")
    if "site_registry.json" in text: root_patterns.append("site_registry_json")
    if "monitored_sites" in text: root_patterns.append("monitored_sites")
    references = []
    for token in ["site_registry", "monitored_sites", "approved", "discovered", "onboarding", "web.py", "backend.site_registry_runtime"]:
        if token in text:
            references.append(token)
    return {
        "imports": sorted(set(imports)),
        "parse_errors": errors,
        "root_patterns": root_patterns,
        "reference_hints": sorted(set(references)),
        "line_count": len(text.splitlines()) if text else 0,
    }


def find_references(target_name: str) -> List[Dict[str, Any]]:
    refs = []
    skip = {".git", "__pycache__", ".venv", "venv", "node_modules"}
    for path in ROOT.rglob("*"):
        if not path.is_file() or any(part in skip for part in path.parts):
            continue
        if path.suffix.lower() not in {".py", ".html", ".js", ".css", ".ps1", ".cmd", ".md", ".txt", ".json"}:
            continue
        rp = rel(path)
        if rp == target_name:
            continue
        text = read_text(path)
        name = Path(target_name).name
        hits = []
        for token in {target_name, target_name.replace("/", "\\"), name, target_name.replace("backend/", "backend.").replace(".py", "").replace("/", ".")}:
            if token and token in text:
                hits.append(token)
        if hits:
            refs.append({"source": rp, "matched": sorted(set(hits))})
    return refs[:100]


def phase_for(candidate: str) -> str:
    for phase in PHASES:
        if candidate in phase.get("candidates", []):
            return phase["phase"]
    return "phase_0_plan_only"


def risk_for(candidate: str) -> str:
    if candidate == "scripts/build_site_registry.py": return "medium_registry_builder"
    if candidate == "backend/site_registry_runtime.py": return "medium_runtime_import_path"
    if candidate == "site_discovery.py": return "review_collector_registry_hybrid"
    if candidate in {"config/monitored_sites.json", "static/data/site_registry.json"}: return "retain_contract_path"
    return "review"


def candidate_row(candidate: str) -> Dict[str, Any]:
    path = ROOT / candidate
    return {
        "file": candidate,
        "exists": path.exists(),
        "recommended_target": TARGET_MAP.get(candidate, candidate),
        "phase": phase_for(candidate),
        "risk": risk_for(candidate),
        "analysis": parse_python(path) if path.exists() else {},
        "reference_count": len(find_references(candidate)) if path.exists() else 0,
        "references": find_references(candidate) if path.exists() else [],
    }


def write_md(payload: Dict[str, Any]) -> None:
    lines = ["# Registry Module Migration Plan", "", f"Generated: `{payload['generated_at_utc']}`", "", "## Mode", "", "Report-only. No files were moved and no imports were changed.", "", "## Summary", ""]
    for k, v in payload["summary"].items():
        lines.append(f"- {k}: **{v}**")
    lines += ["", "## Migration Phases", ""]
    for phase in payload["phases"]:
        lines.append(f"### {phase['phase']}")
        lines.append(phase["purpose"])
        if phase.get("candidates"):
            lines.append("")
            lines.append("Candidates:")
            for c in phase["candidates"]:
                lines.append(f"- `{c}` → `{TARGET_MAP.get(c, c)}`")
        lines.append("")
        lines.append("Validation:")
        for item in phase["validation"]:
            lines.append(f"- {item}")
        lines.append("")
    lines += ["## Candidate Map", ""]
    for row in payload["candidates"]:
        lines.append(f"- `{row['file']}` → `{row['recommended_target']}` | risk `{row['risk']}` | phase `{row['phase']}` | refs `{row['reference_count']}`")
    lines += ["", "## Safety Rules", ""]
    for rule in payload["safety_rules"]:
        lines.append(f"- {rule}")
    OUT_MD.parent.mkdir(parents=True, exist_ok=True)
    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    candidates = [candidate_row(c) for c in REGISTRY_CANDIDATES]
    risk_counts = Counter(row["risk"] for row in candidates)
    phase_counts = Counter(row["phase"] for row in candidates)
    payload = {
        "schema": "jom-registry-module-migration-plan-v1",
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
        "safety_rules": [
            "Keep static/data/site_registry.json path unchanged.",
            "Keep config/monitored_sites.json path unchanged.",
            "Move builder before runtime adapter.",
            "Keep scripts/build_site_registry.py as wrapper after migration.",
            "If backend/site_registry_runtime.py moves, leave backend compatibility shim until web.py imports are updated.",
            "Do not auto-approve or expand monitored site scope during migration.",
            "Validate monitored sites remain gli-it-project, gli-global-technology, gli-delivery-tm unless explicitly changed.",
        ],
        "next_action": "Build Registry Module Migration Pack v1 for scripts/build_site_registry.py only, after this report is committed.",
    }
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    write_md(payload)
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
