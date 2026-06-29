from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT_JSON = ROOT / "reports" / "migration_tooling_archive_review.json"
OUT_MD = ROOT / "reports" / "migration_tooling_archive_review.md"

KNOWN_OPERATIONAL_KEEP = {
    "scripts/run_operational_snapshot.py",
    "scripts/run_sync_for_scheduler.cmd",
    "scripts/sync_runtime.py",
    "scripts/register_scheduled_sync.ps1",
    "scripts/unregister_scheduled_sync.ps1",
    "scripts/check_scheduled_sync.ps1",
    "scripts/view_sync_log.ps1",
    "scripts/source_reliability_audit.py",
    "scripts/audit_source_freshness.py",
    "scripts/build_site_registry.py",
    "scripts/build_named_access_truth_v2.py",
    "scripts/build_user_footprint_source.py",
    "scripts/build_named_access_reconciliation.py",
    "scripts/build_named_access_recovery_plan.py",
    "scripts/reconcile_named_access_truth_v2.py",
    "scripts/run_user_footprint_unlock.py",
    "scripts/run_group_expansion_recovery.py",
    "scripts/run_named_access_recovery_implementation.py",
    "scripts/project_alignment_audit.py",
    "scripts/project_ownership_map.py",
    "scripts/route_static_reference_validation.py",
    "scripts/tree_final_sanity_report.py",
    "scripts/cleanup_closeout_handover.py",
    "scripts/health_check.ps1",
    "scripts/jom_health_check.ps1",
}

MIGRATION_ARCHIVE_PATTERNS = (
    "run_audit_module_migration_",
    "run_builder_module_migration_",
    "run_registry_module_migration_",
    "repair_audit_module_roots_",
)

PLAN_REVIEW_PATTERNS = (
    "folder_structure_refactor_plan.py",
    "audit_module_migration_plan.py",
    "builder_module_migration_plan.py",
    "registry_module_migration_plan.py",
    "site_discovery_migration_review.py",
)

SAFE_ARCHIVE_PATTERNS = (
    "safe_archive_candidates.py",
    "safe_review_archive.py",
)


def now_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def git(args: list[str]) -> dict:
    try:
        proc = subprocess.run(["git"] + args, cwd=ROOT, capture_output=True, text=True, timeout=60)
        return {"returncode": proc.returncode, "stdout": proc.stdout.strip(), "stderr": proc.stderr.strip()}
    except Exception as exc:
        return {"returncode": None, "error": str(exc)}


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return ""


def classify(path: Path) -> dict:
    rp = rel(path)
    name = path.name
    text = read_text(path)
    suffix = path.suffix.lower()

    if rp in KNOWN_OPERATIONAL_KEEP:
        category = "keep_operational"
        action = "keep"
        reason = "Known operational wrapper, runtime entry point, or active validation script."
    elif any(name.startswith(p) for p in MIGRATION_ARCHIVE_PATTERNS):
        category = "archive_candidate_migration_runner"
        action = "archive_later_after_checkpoint"
        reason = "One-off migration runner; likely no longer needed in active scripts once rollback backups and commits exist."
    elif name in PLAN_REVIEW_PATTERNS:
        category = "archive_candidate_plan_or_review_tool"
        action = "archive_later_after_checkpoint"
        reason = "Report-only planning/review tool; useful history but not normal daily operation."
    elif name in SAFE_ARCHIVE_PATTERNS:
        category = "keep_or_archive_policy_tool"
        action = "review"
        reason = "Cleanup/archive policy tooling; keep until cleanup process is fully settled."
    elif suffix in {".ps1", ".cmd"} and "scheduled" in name.lower():
        category = "keep_scheduler_control"
        action = "keep"
        reason = "Scheduler control script."
    elif "migration" in name.lower() or "repair_" in name.lower():
        category = "review_possible_migration_tooling"
        action = "review"
        reason = "Name suggests migration/repair tooling but pattern is not explicitly known."
    elif "build_" in name or "refresh_" in name or "run_" in name:
        category = "review_runtime_or_builder"
        action = "review"
        reason = "Builder/runtime script; may be active wrapper or legacy entry point."
    else:
        category = "review_unclassified"
        action = "review"
        reason = "Not enough evidence to archive automatically."

    wrapper_hint = "from app." in text or "runpy.run_module(\"app." in text
    app_ref_count = text.count("app.")

    return {
        "path": rp,
        "name": name,
        "suffix": suffix,
        "category": category,
        "recommended_action": action,
        "reason": reason,
        "line_count": len(text.splitlines()) if text else 0,
        "wrapper_hint": wrapper_hint,
        "app_ref_count": app_ref_count,
    }


def write_md(payload: dict) -> None:
    lines = []
    lines.append("# Migration Tooling Archive Review")
    lines.append("")
    lines.append(f"Generated: `{payload['generated_at_utc']}`")
    lines.append("")
    lines.append("## Mode")
    lines.append("")
    lines.append("Report-only. No files were moved, deleted, or archived.")
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    for key, value in payload["summary"].items():
        lines.append(f"- {key}: **{value}**")
    lines.append("")
    lines.append("## Archive Candidates")
    lines.append("")
    for row in payload["rows"]:
        if row["recommended_action"].startswith("archive"):
            lines.append(f"- `{row['path']}` — {row['category']} — {row['reason']}")
    lines.append("")
    lines.append("## Keep Operational")
    lines.append("")
    for row in payload["rows"]:
        if row["recommended_action"] == "keep":
            lines.append(f"- `{row['path']}` — {row['category']}")
    lines.append("")
    lines.append("## Review Required")
    lines.append("")
    for row in payload["rows"]:
        if row["recommended_action"] == "review":
            lines.append(f"- `{row['path']}` — {row['category']} — {row['reason']}")
    lines.append("")
    lines.append("## Safety Rules")
    lines.append("")
    for rule in payload["safety_rules"]:
        lines.append(f"- {rule}")
    OUT_MD.parent.mkdir(parents=True, exist_ok=True)
    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    scripts_dir = ROOT / "scripts"
    rows = []
    if scripts_dir.exists():
        for path in sorted(scripts_dir.iterdir()):
            if path.is_file() and path.suffix.lower() in {".py", ".ps1", ".cmd"}:
                rows.append(classify(path))

    counts = {}
    action_counts = {}
    for row in rows:
        counts[row["category"]] = counts.get(row["category"], 0) + 1
        action_counts[row["recommended_action"]] = action_counts.get(row["recommended_action"], 0) + 1

    payload = {
        "schema": "jom-migration-tooling-archive-review-v1",
        "generated_at_utc": now_utc(),
        "mode": "report-only-no-file-moves",
        "summary": {
            "script_file_count": len(rows),
            "category_counts": dict(sorted(counts.items())),
            "action_counts": dict(sorted(action_counts.items())),
            "git_status_short": git(["status", "--short"]).get("stdout"),
        },
        "rows": rows,
        "safety_rules": [
            "Do not archive or delete anything in this review pack.",
            "Do not archive operational wrappers that point into app/* modules.",
            "Do not archive scheduler/runtime scripts until scheduled execution path is reviewed.",
            "Only archive one-off migration runners after a clean git checkpoint.",
            "Keep rollback backups under backups/ untouched.",
            "Next pack, if approved, should move archive candidates to backups/_migration_tooling_archive/<timestamp>/, not delete them.",
        ],
        "next_action": "Review the report, commit it, then build Migration Tooling Archive Pack v1 only if the archive candidates look correct.",
    }

    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    write_md(payload)
    print(json.dumps({
        "status": "ok",
        "mode": payload["mode"],
        "script_file_count": len(rows),
        "json": str(OUT_JSON),
        "report": str(OUT_MD),
        "next_action": payload["next_action"],
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
