from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
OUT_JSON = ROOT / "reports" / "script_folder_rationalisation_review_v1.json"
OUT_MD = ROOT / "reports" / "script_folder_rationalisation_review_v1.md"

ACTIVE_ENTRYPOINTS = {
    "run_operational_snapshot.py",
    "source_reliability_audit.py",
    "audit_source_freshness.py",
    "build_site_registry.py",
    "build_named_access_truth_v2.py",
    "build_user_footprint_source.py",
    "build_admin_truth_layer_v2.py",
    "build_estate_product_access.py",
    "refresh_runtime_sources.py",
    "refresh_admin_enriched_sources.py",
    "refresh_product_access_sources.py",
    "refresh_admin_enriched_chain.py",
    "run_operational_source_recovery.py",
    "backup_runtime_chain.py",
    "run_site_onboarding_action_v1.py",
    "build_site_onboarding_review.py",
    "build_operational_console_status.py",
    "build_operational_console_ui_view.py",
    "build_operational_console_enhancements.py",
}

SCHEDULER_ENTRYPOINTS = {
    "register_scheduled_sync.ps1",
    "check_scheduled_sync.ps1",
    "unregister_scheduled_sync.ps1",
    "view_sync_log.ps1",
}

LEGACY_OR_REVIEW = {
    "sync_runtime.py",
    "snapshot_controller.py",
    "run_sync_for_scheduler.cmd",
    "run_morning_pipeline.ps1",
}

MIGRATION_TOOLING_PATTERNS = [
    r"migration", r"repair_", r"safe_archive", r"safe_review", r"root_repair", r"bootstrap", r"plan"
]

UI_BINDING_PATTERNS = [r"bind_", r"operational_console", r"site_onboarding"]

AUDIT_PATTERNS = [r"audit", r"validation", r"ownership", r"alignment", r"sanity", r"health_check"]

ACCESS_PATTERNS = [r"named_access", r"user_footprint", r"group_expansion"]


def now_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return ""


def is_wrapper(text: str) -> bool:
    return "ensure_project_root_on_path" in text and ("from app." in text or "runpy.run_module" in text)


def classify(path: Path) -> dict:
    name = path.name
    rel = path.relative_to(ROOT).as_posix()
    text = read_text(path)
    lower = name.lower()

    if name in ACTIVE_ENTRYPOINTS:
        category = "keep_root_active_entrypoint"
        target = rel
        reason = "Current runtime/build entry point used by snapshot, reliability, access, UI, or onboarding workflows."
    elif name in SCHEDULER_ENTRYPOINTS:
        category = "keep_root_scheduler_control"
        target = rel
        reason = "Scheduler control script; keep discoverable at scripts root."
    elif name in LEGACY_OR_REVIEW:
        category = "legacy_review_before_archive"
        target = "scripts/_legacy_review/" + name
        reason = "Legacy scheduler/runtime path. Review before archive because references may still exist in docs or operator habits."
    elif any(re.search(p, lower) for p in MIGRATION_TOOLING_PATTERNS):
        category = "archive_migration_tooling"
        target = "scripts/_archive_migration_tooling/" + name
        reason = "Migration/planning/one-off repair tooling; should not stay mixed with runtime scripts."
    elif any(re.search(p, lower) for p in UI_BINDING_PATTERNS):
        category = "group_ui_tooling"
        target = "scripts/ui/" + name
        reason = "UI/status/binding helper. Candidate for scripts/ui with root wrapper retained only if externally called."
    elif any(re.search(p, lower) for p in AUDIT_PATTERNS):
        category = "group_audit_tooling"
        target = "scripts/audits/" + name
        reason = "Audit/report helper. Candidate for scripts/audits."
    elif any(re.search(p, lower) for p in ACCESS_PATTERNS):
        category = "group_access_tooling"
        target = "scripts/access/" + name
        reason = "Access/named-user helper. Candidate for scripts/access."
    elif path.suffix.lower() == ".ps1":
        category = "ops_review"
        target = "scripts/ops/" + name
        reason = "PowerShell operational helper. Keep only if used; otherwise archive."
    else:
        category = "needs_manual_review"
        target = rel
        reason = "No confident classification. Do not move automatically."

    imports_app = sorted(set(re.findall(r"from\s+(app\.[\w\.]+)\s+import|import\s+(app\.[\w\.]+)", text)))
    return {
        "name": name,
        "path": rel,
        "extension": path.suffix.lower(),
        "category": category,
        "recommended_target": target,
        "reason": reason,
        "line_count": len(text.splitlines()),
        "is_wrapper": is_wrapper(text),
        "imports_app": imports_app,
        "exists": path.exists(),
    }


def main() -> int:
    files = []
    for path in sorted(SCRIPTS.iterdir()):
        if path.is_file() and path.suffix.lower() in {".py", ".ps1", ".cmd"}:
            files.append(classify(path))

    by_category = {}
    for item in files:
        by_category.setdefault(item["category"], []).append(item)

    empty_dirs = []
    for path in sorted(SCRIPTS.iterdir()):
        if path.is_dir():
            try:
                if len(list(path.iterdir())) == 0:
                    empty_dirs.append(path.relative_to(ROOT).as_posix())
            except Exception:
                pass

    payload = {
        "schema": "jom-script-folder-rationalisation-review-v1",
        "generated_at_utc": now_utc(),
        "mode": "report_only_no_moves",
        "summary": {
            "script_file_count": len(files),
            "category_counts": {k: len(v) for k, v in sorted(by_category.items())},
            "empty_script_subdirs": empty_dirs,
            "root_active_entrypoints": len(by_category.get("keep_root_active_entrypoint", [])),
            "archive_candidates": len(by_category.get("archive_migration_tooling", [])) + len(by_category.get("legacy_review_before_archive", [])),
        },
        "files": files,
        "proposed_structure": {
            "scripts/root": "Only stable operator entry points and scheduler controls.",
            "scripts/audits": "Audit/report helpers.",
            "scripts/access": "Named access and user footprint helpers.",
            "scripts/ui": "Operational console and template binding helpers.",
            "scripts/ops": "PowerShell operational helpers.",
            "scripts/_legacy_review": "Legacy runtime/scheduler scripts pending final archive.",
            "scripts/_archive_migration_tooling": "Historical migration pack tools, safe to archive once no longer needed.",
        },
        "next_pack": "Script Folder Rationalisation Apply Pack v1 should only move category-safe files and preserve wrappers for active root entry points.",
    }

    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    lines = [
        "# Script Folder Rationalisation Review v1",
        "",
        f"Generated: `{payload['generated_at_utc']}`",
        "",
        "## Mode",
        "",
        "Report only. No files were moved.",
        "",
        "## Summary",
        "",
    ]
    for key, value in payload["summary"].items():
        lines.append(f"- {key}: **{value}**")
    lines += ["", "## Categories", ""]
    for category, items in sorted(by_category.items()):
        lines.append(f"### {category} ({len(items)})")
        for item in items:
            lines.append(f"- `{item['path']}` → `{item['recommended_target']}` — {item['reason']}")
        lines.append("")
    OUT_MD.write_text("\n".join(lines), encoding="utf-8")

    print(json.dumps({
        "status": "ok",
        "report_json": str(OUT_JSON),
        "report_md": str(OUT_MD),
        "summary": payload["summary"],
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
