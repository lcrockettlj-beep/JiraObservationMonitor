from __future__ import annotations

import ast
import json
import os
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[2]
REPORT_JSON = ROOT / "reports" / "project_alignment_audit.json"
REPORT_MD = ROOT / "reports" / "project_alignment_audit.md"

SKIP_DIRS = {".git", "__pycache__", ".pytest_cache", ".mypy_cache", "node_modules", ".venv", "venv"}
TEXT_EXTS = {".py", ".ps1", ".cmd", ".html", ".css", ".js", ".json", ".md", ".txt", ".yml", ".yaml"}
CODE_EXTS = {".py", ".js", ".css", ".html", ".ps1", ".cmd"}
RUNTIME_DATA = {
    "latest_run.json",
    "latest_run_admin_enriched.json",
    "latest_run_admin_enriched_pretty.json",
    "latest_run_pretty.json",
    "latest_run_safe_partial.json",
    "latest_snapshot.json",
    "snapshot_index.json",
}
CORE_PAGES = {"home.html", "estate.html", "reference.html", "admin.html", "_nav.html"}


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


def file_bucket(path: Path) -> str:
    r = rel(path)
    parts = path.relative_to(ROOT).parts
    if not parts:
        return "root"
    first = parts[0]
    if first == "templates": return "templates"
    if first == "static":
        if len(parts) > 1:
            return f"static/{parts[1]}"
        return "static"
    if first == "scripts": return "scripts"
    if first == "backend": return "backend"
    if first == "reports": return "reports"
    if first == "backups": return "backups"
    if first == "docs": return "docs"
    if first == "config": return "config"
    if first == "snapshots": return "snapshots"
    if first == "_cleanup_archive": return "cleanup_archive"
    if first.endswith("_pack_v1") or "pack" in first.lower(): return "pack_extracts"
    return "root"


def scan_files() -> List[Dict[str, Any]]:
    rows = []
    for path in ROOT.rglob("*"):
        if not path.is_file() or is_skipped(path):
            continue
        try:
            stat = path.stat()
        except OSError:
            continue
        rows.append({
            "path": rel(path),
            "name": path.name,
            "suffix": path.suffix.lower(),
            "bucket": file_bucket(path),
            "size_bytes": stat.st_size,
            "modified_utc": datetime.fromtimestamp(stat.st_mtime, timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        })
    return sorted(rows, key=lambda x: x["path"])


def parse_python_imports(path: Path) -> Dict[str, Any]:
    text = read_text(path)
    imports = []
    errors = []
    try:
        tree = ast.parse(text)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append(alias.name.split('.')[0])
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imports.append(node.module.split('.')[0])
    except Exception as exc:
        errors.append(str(exc))
    return {"path": rel(path), "imports": sorted(set(imports)), "errors": errors}


def find_static_refs(path: Path) -> List[str]:
    text = read_text(path)
    refs = set()
    patterns = [
        r'/static/[^\'\"\s)>]+',
        r"url_for\('static',\s*filename='([^']+)'\)",
        r"url_for\(\"static\",\s*filename=\"([^\"]+)\"\)",
        r"fetch\(['\"]([^'\"]+\.json)['\"]",
        r"href=['\"]([^'\"]+\.(?:css|js))['\"]",
        r"src=['\"]([^'\"]+\.(?:css|js))['\"]",
    ]
    for pattern in patterns:
        for match in re.finditer(pattern, text):
            value = match.group(1) if match.groups() else match.group(0)
            value = value.replace("{{ ", "").replace(" }}", "")
            refs.add(value)
    return sorted(refs)


def referenced_static_files(files: List[Dict[str, Any]]) -> Dict[str, Any]:
    refs = defaultdict(list)
    for row in files:
        suffix = row["suffix"]
        if suffix not in {".html", ".js", ".css"}:
            continue
        path = ROOT / row["path"]
        for ref in find_static_refs(path):
            refs[ref].append(row["path"])
    return dict(sorted(refs.items()))


def infer_runtime_ownership(files: List[Dict[str, Any]]) -> Dict[str, Any]:
    outputs = {}
    for script_path in (ROOT / "scripts").glob("*.py") if (ROOT / "scripts").exists() else []:
        text = read_text(script_path)
        targets = sorted(set(re.findall(r"(?:static/data|reports|latest_run)[A-Za-z0-9_./\\-]*\.(?:json|md)", text)))
        if targets:
            outputs[rel(script_path)] = targets
    return outputs


def duplicate_names(files: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    by_name = defaultdict(list)
    for row in files:
        by_name[row["name"]].append(row["path"])
    return [{"name": name, "count": len(paths), "paths": sorted(paths)} for name, paths in sorted(by_name.items()) if len(paths) > 1]


def stale_or_legacy_candidates(files: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out = []
    patterns = [".bak", "backup", "archive", "old", "legacy", "copy", "safe_partial"]
    for row in files:
        p = row["path"].lower()
        if any(token in p for token in patterns):
            out.append(row)
    return out


def folder_proposal() -> Dict[str, Any]:
    return {
        "principle": "Do not move files automatically. This is a target structure for a later controlled refactor after runtime references are mapped.",
        "proposed_structure": {
            "app/backend": "Runtime adapters, registry runtime helpers, web service helpers.",
            "app/collectors": "API collectors such as Jira, Admin, group expansion, billing collectors.",
            "app/builders": "Source-build scripts producing static/data outputs.",
            "app/audits": "Freshness, reliability, health, alignment checks.",
            "templates/home": "Home page templates/components.",
            "templates/estate": "Estate page templates/components.",
            "templates/admin": "Admin/reference templates/components.",
            "templates/shared": "Navigation/shared partials.",
            "static/js/home": "Home-only JS.",
            "static/js/estate": "Estate-only JS including footprint/product truth.",
            "static/js/admin": "Admin/reference JS including registry and truth binding.",
            "static/js/shared": "Theme, guard, refresh, reliability/freshness shared modules.",
            "static/css/home": "Home-only CSS.",
            "static/css/estate": "Estate-only CSS.",
            "static/css/admin": "Admin/reference CSS.",
            "static/css/shared": "Theme tokens, nav, common cards, truth/freshness/reliability.",
            "static/data/runtime": "latest runtime snapshots and metadata.",
            "static/data/admin": "admin_truth, named_access, group_expansion.",
            "static/data/estate": "estate_product_access, estate_access_truth, user_footprint.",
            "static/data/reliability": "source freshness/reliability status.",
            "reports/access": "Named access and group expansion diagnostics/reconciliation.",
            "reports/reliability": "Freshness/reliability audit outputs.",
            "tools/installers": "Install/verify/rollback pack helpers.",
            "tools/maintenance": "Backup, cleanup, scheduled sync, health checks."
        }
    }


def route_surface_summary(files: List[Dict[str, Any]]) -> Dict[str, Any]:
    templates = {Path(row["path"]).name: row["path"] for row in files if row["bucket"] == "templates"}
    static_js = sorted(row["path"] for row in files if row["bucket"] == "static/js")
    static_css = sorted(row["path"] for row in files if row["bucket"] == "static/css")
    return {
        "core_templates_present": {name: templates.get(name) for name in sorted(CORE_PAGES)},
        "visible_admin_likely_reference": "templates/reference.html is the nav target for Admin based on _nav.html.",
        "static_js_count": len(static_js),
        "static_css_count": len(static_css),
    }


def risk_findings(files: List[Dict[str, Any]], refs: Dict[str, Any], imports: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    findings = []
    names = {row["path"] for row in files}
    if "templates/reference.html" in names and "templates/admin.html" in names:
        findings.append({"severity": "review", "area": "templates", "finding": "Both reference.html and admin.html exist; nav Admin route appears to target /reference, so admin.html may be secondary or legacy."})
    if "static/js/admin.js" in names:
        text = read_text(ROOT / "static/js/admin.js")
        if re.search(r"const\s+humanUsers\s*=\s*\d+", text):
            findings.append({"severity": "high", "area": "admin_js", "finding": "static/js/admin.js contains hardcoded admin numbers. Replace with live data binding."})
    for imp in imports:
        if imp["path"].startswith("scripts/") and "jira_client" in imp["imports"]:
            findings.append({"severity": "review", "area": "python_imports", "finding": f"{imp['path']} imports root-level jira_client; scripts may require PYTHONPATH or project bootstrap when run directly."})
    pack_dirs = [row for row in files if row["bucket"] == "pack_extracts"]
    if pack_dirs:
        findings.append({"severity": "review", "area": "pack_extracts", "finding": "Extracted pack folders exist in project root. Confirm whether these are intentional runtime assets or cleanup candidates."})
    backup_count = sum(1 for row in files if row["bucket"] == "backups")
    if backup_count > 100:
        findings.append({"severity": "review", "area": "backups", "finding": f"Large backup footprint detected ({backup_count} files). Consider retention policy after gold baseline is confirmed."})
    return findings


def write_markdown(payload: Dict[str, Any]) -> None:
    lines = []
    lines.append("# JOM Full Project Alignment Audit")
    lines.append("")
    lines.append(f"Generated: `{payload['generated_at_utc']}`")
    lines.append("")
    lines.append("## Executive Summary")
    lines.append("")
    s = payload["summary"]
    lines.append(f"- Total files scanned: **{s['total_files']}**")
    lines.append(f"- Python files: **{s['python_files']}**")
    lines.append(f"- Template files: **{s['template_files']}**")
    lines.append(f"- Static JS files: **{s['static_js_files']}**")
    lines.append(f"- Static CSS files: **{s['static_css_files']}**")
    lines.append(f"- Static data JSON files: **{s['static_data_files']}**")
    lines.append(f"- Findings: **{len(payload['findings'])}**")
    lines.append("")
    lines.append("## Key Findings")
    lines.append("")
    if payload["findings"]:
        for item in payload["findings"]:
            lines.append(f"- **{item['severity'].upper()} / {item['area']}**: {item['finding']}")
    else:
        lines.append("- No alignment findings detected by static scan.")
    lines.append("")
    lines.append("## Bucket Counts")
    lines.append("")
    for bucket, count in payload["summary"]["bucket_counts"].items():
        lines.append(f"- `{bucket}`: {count}")
    lines.append("")
    lines.append("## Duplicate Filename Hotspots")
    lines.append("")
    for item in payload["duplicate_names"][:30]:
        lines.append(f"- `{item['name']}` appears {item['count']} times")
    if not payload["duplicate_names"]:
        lines.append("- None detected.")
    lines.append("")
    lines.append("## Proposed Folder Direction")
    lines.append("")
    lines.append(payload["folder_proposal"]["principle"])
    lines.append("")
    for folder, purpose in payload["folder_proposal"]["proposed_structure"].items():
        lines.append(f"- `{folder}` — {purpose}")
    REPORT_MD.parent.mkdir(parents=True, exist_ok=True)
    REPORT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    files = scan_files()
    bucket_counts = Counter(row["bucket"] for row in files)
    imports = [parse_python_imports(ROOT / row["path"]) for row in files if row["suffix"] == ".py"]
    refs = referenced_static_files(files)
    payload: Dict[str, Any] = {
        "schema": "jom-full-project-alignment-audit-v1",
        "generated_at_utc": now_utc(),
        "summary": {
            "total_files": len(files),
            "python_files": sum(1 for row in files if row["suffix"] == ".py"),
            "template_files": sum(1 for row in files if row["bucket"] == "templates"),
            "static_js_files": sum(1 for row in files if row["bucket"] == "static/js"),
            "static_css_files": sum(1 for row in files if row["bucket"] == "static/css"),
            "static_data_files": sum(1 for row in files if row["bucket"] == "static/data"),
            "bucket_counts": dict(sorted(bucket_counts.items())),
        },
        "route_surface_summary": route_surface_summary(files),
        "files": files,
        "duplicate_names": duplicate_names(files),
        "legacy_or_backup_candidates": stale_or_legacy_candidates(files),
        "python_imports": imports,
        "static_references": refs,
        "runtime_output_ownership_candidates": infer_runtime_ownership(files),
        "findings": [],
        "folder_proposal": folder_proposal(),
    }
    payload["findings"] = risk_findings(files, refs, imports)
    REPORT_JSON.parent.mkdir(parents=True, exist_ok=True)
    REPORT_JSON.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    write_markdown(payload)
    print(json.dumps({
        "status": "ok",
        "files_scanned": len(files),
        "findings": len(payload["findings"]),
        "json": str(REPORT_JSON),
        "report": str(REPORT_MD),
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
