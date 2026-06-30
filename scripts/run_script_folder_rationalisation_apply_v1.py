from __future__ import annotations

import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REVIEW = ROOT / "reports" / "script_folder_rationalisation_review_v1.json"
STATUS = ROOT / "reports" / "script_folder_rationalisation_apply_v1_status.json"

SAFE_MOVE_CATEGORIES = {
    "archive_migration_tooling",
    "legacy_review_before_archive",
}

ROOT_KEEP_CATEGORIES = {
    "keep_root_active_entrypoint",
    "keep_root_scheduler_control",
}

VALIDATION_COMMANDS = [
    [sys.executable, "-m", "py_compile", "scripts/run_operational_snapshot.py", "scripts/source_reliability_audit.py", "scripts/build_site_registry.py"],
    [sys.executable, "scripts/source_reliability_audit.py"],
]


def now_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def read_json(path: Path):
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"_read_error": str(exc)}


def write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def run(cmd: list[str], timeout: int = 420) -> dict:
    try:
        proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, timeout=timeout)
        return {
            "cmd": " ".join(cmd),
            "returncode": proc.returncode,
            "stdout_tail": (proc.stdout or "")[-5000:],
            "stderr_tail": (proc.stderr or "")[-5000:],
        }
    except Exception as exc:
        return {"cmd": " ".join(cmd), "returncode": None, "error": str(exc)}


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def main() -> int:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_root = ROOT / "backups" / f"script_folder_rationalisation_apply_v1_{stamp}"
    backup_root.mkdir(parents=True, exist_ok=True)

    review = read_json(REVIEW)
    if not isinstance(review, dict):
        raise SystemExit(f"Review file missing/unreadable: {REVIEW}")

    files = review.get("files") or []
    moved = []
    skipped = []
    errors = []
    protected_root = []

    for item in files:
        if not isinstance(item, dict):
            continue
        category = item.get("category")
        src_rel = item.get("path")
        target_rel = item.get("recommended_target")
        if not src_rel or not target_rel:
            continue

        if category in ROOT_KEEP_CATEGORIES:
            protected_root.append(src_rel)
            continue

        if category not in SAFE_MOVE_CATEGORIES:
            skipped.append({
                "path": src_rel,
                "category": category,
                "reason": "not in safe move categories for v1",
            })
            continue

        src = ROOT / src_rel
        dst = ROOT / target_rel
        if not src.exists():
            skipped.append({
                "path": src_rel,
                "category": category,
                "reason": "source file not found",
            })
            continue

        try:
            backup = backup_root / src_rel
            backup.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, backup)
            dst.parent.mkdir(parents=True, exist_ok=True)
            if dst.exists():
                dst_backup = backup_root / "existing_targets" / target_rel
                dst_backup.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(dst, dst_backup)
            shutil.move(str(src), str(dst))
            moved.append({
                "from": src_rel,
                "to": target_rel,
                "category": category,
                "backup": rel(backup),
            })
        except Exception as exc:
            errors.append({"path": src_rel, "target": target_rel, "error": str(exc)})

    # Remove empty legacy dirs if they were emptied by the move.
    removed_empty_dirs = []
    for candidate in [ROOT / "scripts" / "archive", ROOT / "scripts" / "installers"]:
        try:
            if candidate.exists() and candidate.is_dir() and len(list(candidate.iterdir())) == 0:
                candidate.rmdir()
                removed_empty_dirs.append(rel(candidate))
        except Exception as exc:
            errors.append({"path": rel(candidate), "error": f"empty-dir-remove failed: {exc}"})

    # Remove regenerated empty exports dir if currently empty. This is not part of scripts rationalisation but clears the known empty folder safely.
    exports_dir = ROOT / "static" / "data" / "exports"
    removed_empty_exports = False
    try:
        if exports_dir.exists() and exports_dir.is_dir() and len(list(exports_dir.iterdir())) == 0:
            exports_dir.rmdir()
            removed_empty_exports = True
    except Exception as exc:
        errors.append({"path": rel(exports_dir), "error": f"empty exports remove failed: {exc}"})

    validation_runs = [run(cmd) for cmd in VALIDATION_COMMANDS]

    reliability = read_json(ROOT / "static" / "data" / "source_reliability_status.json") or {}
    summary = reliability.get("summary") or {}
    issue_count = summary.get("issue_count", reliability.get("issue_count"))
    reliability_ok = reliability.get("overall_status") == "ok" and issue_count == 0
    validation_ok = all(v.get("returncode") == 0 for v in validation_runs) and reliability_ok

    rollback = backup_root / "rollback_script_folder_rationalisation_apply_v1.ps1"
    lines = [
        'param([string]$ProjectRoot = "C:\\Users\\Luke_C\\Desktop\\JiraObservationMonitor")',
        '$ErrorActionPreference = "Stop"',
    ]
    for item in moved:
        src_rel = item["from"].replace("/", "\\")
        dst_rel = item["to"].replace("/", "\\")
        backup_rel = item["backup"].replace("/", "\\")
        lines.append(f'$moved = Join-Path $ProjectRoot "{dst_rel}"')
        lines.append(f'$original = Join-Path $ProjectRoot "{src_rel}"')
        lines.append(f'$backup = Join-Path $ProjectRoot "{backup_rel}"')
        lines.append('New-Item -ItemType Directory -Path (Split-Path -Parent $original) -Force | Out-Null')
        lines.append('if (Test-Path $backup) { Copy-Item $backup $original -Force }')
        lines.append('if (Test-Path $moved) { Remove-Item $moved -Force }')
    lines.append('Write-Host "Script folder rationalisation v1 rollback complete." -ForegroundColor Green')
    rollback.write_text("\n".join(lines) + "\n", encoding="utf-8")

    status = {
        "schema": "jom-script-folder-rationalisation-apply-v1-status",
        "generated_at_utc": now_utc(),
        "mode": "move_safe_archive_and_legacy_candidates_only",
        "status": "ok" if validation_ok and not errors else "attention",
        "backup_root": str(backup_root),
        "rollback_script": str(rollback),
        "safe_move_categories": sorted(SAFE_MOVE_CATEGORIES),
        "protected_root_count": len(protected_root),
        "moved_count": len(moved),
        "skipped_count": len(skipped),
        "error_count": len(errors),
        "moved": moved,
        "skipped": skipped,
        "errors": errors,
        "removed_empty_dirs": removed_empty_dirs,
        "removed_empty_exports": removed_empty_exports,
        "validation_runs": validation_runs,
        "source_reliability_overall_status": reliability.get("overall_status"),
        "source_reliability_issue_count": issue_count,
        "validation_ok": validation_ok,
        "safety_note": "Only migration/legacy archive candidates were moved. Active runtime and scheduler entrypoints were preserved in scripts root.",
    }
    write_json(STATUS, status)

    print(json.dumps({
        "status": status["status"],
        "moved_count": status["moved_count"],
        "skipped_count": status["skipped_count"],
        "error_count": status["error_count"],
        "validation_ok": validation_ok,
        "source_reliability_issue_count": issue_count,
        "removed_empty_dirs": removed_empty_dirs,
        "removed_empty_exports": removed_empty_exports,
        "status_file": str(STATUS),
        "rollback_script": str(rollback),
    }, indent=2))
    return 0 if status["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
