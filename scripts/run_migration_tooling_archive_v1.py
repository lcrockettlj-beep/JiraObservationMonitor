from __future__ import annotations

import json
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATUS = ROOT / "reports" / "migration_tooling_archive_status.json"
REVIEW = ROOT / "reports" / "migration_tooling_archive_review.json"
ARCHIVE_ROOT_BASE = ROOT / "backups" / "_migration_tooling_archive"

# Hard safety allow-list. Only these known one-off migration/review helpers may be archived by v1.
ALLOWED_ARCHIVE_NAMES = {
    "audit_module_migration_plan.py",
    "builder_module_migration_plan.py",
    "folder_structure_refactor_plan.py",
    "registry_module_migration_plan.py",
    "site_discovery_migration_review.py",
    "repair_audit_module_roots_v1.py",
    "run_audit_module_migration_v1.py",
    "run_audit_module_migration_v2.py",
    "run_builder_module_migration_v1.py",
    "run_builder_module_migration_v2.py",
    "run_builder_module_migration_v3.py",
    "run_registry_module_migration_v1.py",
    "run_registry_module_migration_v2.py",
}

PROTECTED_NAMES = {
    "run_operational_snapshot.py",
    "run_sync_for_scheduler.cmd",
    "sync_runtime.py",
    "build_site_registry.py",
    "build_named_access_truth_v2.py",
    "build_user_footprint_source.py",
    "source_reliability_audit.py",
    "audit_source_freshness.py",
    "_project_bootstrap.py",
}


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


def read_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"_read_error": str(exc)}


def discover_candidates_from_review() -> list[dict]:
    review = read_json(REVIEW)
    rows = review.get("rows", []) if isinstance(review, dict) else []
    candidates = []
    for row in rows:
        path_value = row.get("path")
        action = row.get("recommended_action", "")
        name = Path(path_value or "").name
        if not path_value or not action.startswith("archive"):
            continue
        if name not in ALLOWED_ARCHIVE_NAMES:
            continue
        if name in PROTECTED_NAMES:
            continue
        candidates.append({
            "path": path_value,
            "category": row.get("category"),
            "recommended_action": action,
            "reason": row.get("reason"),
        })
    return candidates


def fallback_candidates() -> list[dict]:
    candidates = []
    for name in sorted(ALLOWED_ARCHIVE_NAMES):
        path = ROOT / "scripts" / name
        if path.exists() and name not in PROTECTED_NAMES:
            candidates.append({
                "path": rel(path),
                "category": "fallback_allow_list",
                "recommended_action": "archive_later_after_checkpoint",
                "reason": "Known one-off migration/review helper from hard safety allow-list.",
            })
    return candidates


def main() -> int:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    archive_root = ARCHIVE_ROOT_BASE / stamp
    archive_root.mkdir(parents=True, exist_ok=True)

    review_available = REVIEW.exists()
    candidates = discover_candidates_from_review() if review_available else fallback_candidates()

    archived = []
    skipped = []
    errors = []

    for item in candidates:
        source = ROOT / item["path"]
        name = source.name
        if name in PROTECTED_NAMES:
            skipped.append({"path": item["path"], "reason": "protected name"})
            continue
        if name not in ALLOWED_ARCHIVE_NAMES:
            skipped.append({"path": item["path"], "reason": "not in hard allow-list"})
            continue
        if not source.exists():
            skipped.append({"path": item["path"], "reason": "source missing"})
            continue
        try:
            target = archive_root / item["path"]
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(source), str(target))
            archived.append({
                "source": item["path"],
                "target": rel(target),
                "category": item.get("category"),
                "reason": item.get("reason"),
            })
        except Exception as exc:
            errors.append({"path": item["path"], "error": str(exc)})

    rollback = archive_root / "rollback_migration_tooling_archive_v1.ps1"
    lines = [
        'param([string]$ProjectRoot = "C:\\Users\\Luke_C\\Desktop\\JiraObservationMonitor")',
        '$ErrorActionPreference = "Stop"',
    ]
    for item in archived:
        lines.append(f'$archived = Join-Path $ProjectRoot "{item["target"].replace("/", "\\\\")}"')
        lines.append(f'$restore = Join-Path $ProjectRoot "{item["source"].replace("/", "\\\\")}"')
        lines.append('if (Test-Path $archived) { New-Item -ItemType Directory -Path (Split-Path -Parent $restore) -Force | Out-Null; Move-Item $archived $restore -Force; Write-Host "Restored $restore" -ForegroundColor Green }')
    lines.append('Write-Host "Migration tooling archive rollback complete." -ForegroundColor Green')
    rollback.write_text("\n".join(lines) + "\n", encoding="utf-8")

    status = {
        "schema": "jom-migration-tooling-archive-status-v1",
        "generated_at_utc": now_utc(),
        "mode": "archive-known-migration-tooling-only",
        "review_available": review_available,
        "archive_root": str(archive_root),
        "candidate_count": len(candidates),
        "archived_count": len(archived),
        "skipped_count": len(skipped),
        "error_count": len(errors),
        "archived": archived,
        "skipped": skipped,
        "errors": errors,
        "rollback_script": str(rollback),
        "git_status_short_after": git(["status", "--short"]).get("stdout"),
        "safety": {
            "hard_allow_list_used": True,
            "protected_names_used": True,
            "deleted_files": False,
            "moved_to_backup_archive": True,
        },
    }
    STATUS.parent.mkdir(parents=True, exist_ok=True)
    STATUS.write_text(json.dumps(status, indent=2), encoding="utf-8")

    print(json.dumps({
        "status": "ok" if not errors else "attention",
        "archived_count": len(archived),
        "skipped_count": len(skipped),
        "error_count": len(errors),
        "archive_root": str(archive_root),
        "status_file": str(STATUS),
        "rollback_script": str(rollback),
    }, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
