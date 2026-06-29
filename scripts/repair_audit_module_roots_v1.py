from __future__ import annotations

import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
STATUS = PROJECT_ROOT / "reports" / "audit_module_root_repair_status.json"

MIGRATED_MODULES = [
    "app/audits/project_alignment.py",
    "app/audits/project_ownership.py",
    "app/audits/route_static_reference.py",
    "app/audits/tree_final_sanity.py",
    "app/audits/cleanup_closeout.py",
]

BAD_ROOT_PATTERNS = [
    "ROOT = Path(__file__).resolve().parents[1]",
    "ROOT=Path(__file__).resolve().parents[1]",
]
GOOD_ROOT = "ROOT = Path(__file__).resolve().parents[2]"


def now_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    return path.relative_to(PROJECT_ROOT).as_posix()


def run(cmd: list[str]) -> dict:
    try:
        proc = subprocess.run(cmd, cwd=PROJECT_ROOT, capture_output=True, text=True, timeout=240)
        return {
            "cmd": " ".join(cmd),
            "returncode": proc.returncode,
            "stdout_tail": (proc.stdout or "")[-2200:],
            "stderr_tail": (proc.stderr or "")[-2200:],
        }
    except Exception as exc:
        return {"cmd": " ".join(cmd), "returncode": None, "error": str(exc)}


def repair_file(path: Path, backup_root: Path) -> dict:
    if not path.exists():
        return {"file": rel(path), "status": "missing"}
    original = path.read_text(encoding="utf-8", errors="replace")
    updated = original
    changed = False
    for pattern in BAD_ROOT_PATTERNS:
        if pattern in updated:
            updated = updated.replace(pattern, GOOD_ROOT)
            changed = True
    if not changed:
        return {"file": rel(path), "status": "unchanged", "reason": "expected ROOT pattern not found or already repaired"}
    backup = backup_root / rel(path)
    backup.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(path, backup)
    path.write_text(updated, encoding="utf-8")
    return {"file": rel(path), "status": "repaired", "backup": rel(backup)}


def remove_app_reports(backup_root: Path) -> dict:
    app_reports = PROJECT_ROOT / "app" / "reports"
    if not app_reports.exists():
        return {"status": "not_present"}
    backup = backup_root / "app" / "reports"
    backup.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(app_reports, backup, dirs_exist_ok=True)
    shutil.rmtree(app_reports)
    return {"status": "removed", "backup": rel(backup)}


def main() -> int:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_root = PROJECT_ROOT / "backups" / f"audit_module_root_repair_v1_{stamp}"
    backup_root.mkdir(parents=True, exist_ok=True)

    repairs = [repair_file(PROJECT_ROOT / item, backup_root) for item in MIGRATED_MODULES]
    app_reports_cleanup = remove_app_reports(backup_root)

    validation_runs = [
        run([sys.executable, "scripts/project_alignment_audit.py"]),
        run([sys.executable, "scripts/project_ownership_map.py"]),
        run([sys.executable, "scripts/route_static_reference_validation.py"]),
        run([sys.executable, "scripts/tree_final_sanity_report.py"]),
        run([sys.executable, "scripts/cleanup_closeout_handover.py"]),
        run([sys.executable, "scripts/source_reliability_audit.py"]),
        run([sys.executable, "-m", "py_compile"] + MIGRATED_MODULES),
    ]

    root_report_checks = {
        "reports/project_alignment_audit.json": (PROJECT_ROOT / "reports" / "project_alignment_audit.json").exists(),
        "reports/project_ownership_map.json": (PROJECT_ROOT / "reports" / "project_ownership_map.json").exists(),
        "reports/route_static_reference_validation.json": (PROJECT_ROOT / "reports" / "route_static_reference_validation.json").exists(),
        "reports/tree_final_sanity_report.json": (PROJECT_ROOT / "reports" / "tree_final_sanity_report.json").exists(),
        "reports/cleanup_closeout_handover.json": (PROJECT_ROOT / "reports" / "cleanup_closeout_handover.json").exists(),
        "app/reports_exists": (PROJECT_ROOT / "app" / "reports").exists(),
    }

    rollback = backup_root / "rollback_audit_module_root_repair_v1.ps1"
    lines = [
        'param([string]$ProjectRoot = "C:\\Users\\Luke_C\\Desktop\\JiraObservationMonitor")',
        '$ErrorActionPreference = "Stop"',
    ]
    for item in repairs:
        if item.get("status") == "repaired":
            lines.append(f'$backup = Join-Path $ProjectRoot "{item["backup"].replace("/", "\\\\")}"')
            lines.append(f'$target = Join-Path $ProjectRoot "{item["file"].replace("/", "\\\\")}"')
            lines.append('if (Test-Path $backup) { Copy-Item $backup $target -Force; Write-Host "Restored $target" -ForegroundColor Green }')
    if app_reports_cleanup.get("status") == "removed":
        lines.append(f'$backupReports = Join-Path $ProjectRoot "{app_reports_cleanup["backup"].replace("/", "\\\\")}"')
        lines.append('$targetReports = Join-Path $ProjectRoot "app\\reports"')
        lines.append('if (Test-Path $backupReports) { Copy-Item $backupReports $targetReports -Recurse -Force; Write-Host "Restored app\\reports" -ForegroundColor Green }')
    lines.append('Write-Host "Audit module root repair rollback complete." -ForegroundColor Green')
    rollback.write_text("\n".join(lines) + "\n", encoding="utf-8")

    validation_ok = all(item.get("returncode") == 0 for item in validation_runs)
    root_ok = all(value is True for key, value in root_report_checks.items() if key != "app/reports_exists") and root_report_checks["app/reports_exists"] is False
    status = {
        "schema": "jom-audit-module-root-repair-status-v1",
        "generated_at_utc": now_utc(),
        "mode": "repair-migrated-audit-root-path",
        "backup_root": str(backup_root),
        "repairs": repairs,
        "app_reports_cleanup": app_reports_cleanup,
        "validation_runs": validation_runs,
        "root_report_checks": root_report_checks,
        "validation_ok": validation_ok,
        "root_ok": root_ok,
        "rollback_script": str(rollback),
    }
    STATUS.parent.mkdir(parents=True, exist_ok=True)
    STATUS.write_text(json.dumps(status, indent=2), encoding="utf-8")
    print(json.dumps({
        "status": "ok" if validation_ok and root_ok else "attention",
        "repaired_count": sum(1 for item in repairs if item.get("status") == "repaired"),
        "validation_ok": validation_ok,
        "root_ok": root_ok,
        "app_reports_exists": root_report_checks["app/reports_exists"],
        "status_file": str(STATUS),
    }, indent=2))
    return 0 if validation_ok and root_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
