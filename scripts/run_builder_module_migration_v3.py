from __future__ import annotations

import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATUS = ROOT / "reports" / "builder_module_migration_v3_status.json"

MIGRATIONS = [
    ("scripts/run_user_footprint_unlock.py", "app/access/user_footprint_unlock_runner.py", "user_footprint_unlock_runner"),
    ("scripts/run_group_expansion_recovery.py", "app/access/group_expansion_recovery_runner.py", "group_expansion_recovery_runner"),
    ("scripts/run_named_access_recovery_implementation.py", "app/access/named_access_recovery_runner.py", "named_access_recovery_runner"),
]

WRAPPER_TEMPLATE = """from __future__ import annotations

from _project_bootstrap import ensure_project_root_on_path
ensure_project_root_on_path()

from app.access.{module_name} import main


if __name__ == \"__main__\":
    raise SystemExit(main())
"""

ROOT_PATTERNS = [
    ("ROOT = Path(__file__).resolve().parents[1]", "ROOT = Path(__file__).resolve().parents[2]"),
    ("ROOT=Path(__file__).resolve().parents[1]", "ROOT = Path(__file__).resolve().parents[2]"),
    ("PROJECT_ROOT = Path(__file__).resolve().parents[1]", "PROJECT_ROOT = Path(__file__).resolve().parents[2]"),
    ("PROJECT_ROOT=Path(__file__).resolve().parents[1]", "PROJECT_ROOT = Path(__file__).resolve().parents[2]"),
]


def now_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def run(cmd: list[str]) -> dict:
    try:
        proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, timeout=300)
        return {
            "cmd": " ".join(cmd),
            "returncode": proc.returncode,
            "stdout_tail": (proc.stdout or "")[-3000:],
            "stderr_tail": (proc.stderr or "")[-3000:],
        }
    except Exception as exc:
        return {"cmd": " ".join(cmd), "returncode": None, "error": str(exc)}


def repair_root_in_module(path: Path) -> bool:
    text = path.read_text(encoding="utf-8", errors="replace")
    updated = text
    for old, new in ROOT_PATTERNS:
        updated = updated.replace(old, new)
    if updated != text:
        path.write_text(updated, encoding="utf-8")
        return True
    return False


def read_json(path: Path):
    if not path.exists(): return None
    try: return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc: return {"_read_error": str(exc)}


def main() -> int:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_root = ROOT / "backups" / f"builder_module_migration_v3_{stamp}"
    backup_root.mkdir(parents=True, exist_ok=True)
    moved, missing, errors = [], [], []
    (ROOT / "app" / "access").mkdir(parents=True, exist_ok=True)
    init = ROOT / "app" / "access" / "__init__.py"
    if not init.exists(): init.write_text('"""JOM access package."""\n', encoding="utf-8")

    for src_rel, dst_rel, module_name in MIGRATIONS:
        src = ROOT / src_rel
        dst = ROOT / dst_rel
        if not src.exists():
            missing.append(src_rel)
            continue
        try:
            backup = backup_root / src_rel
            backup.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, backup)
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
            root_repaired = repair_root_in_module(dst)
            src.write_text(WRAPPER_TEMPLATE.format(module_name=module_name), encoding="utf-8")
            moved.append({"script": src_rel, "module": dst_rel, "backup": rel(backup), "wrapper_module": module_name, "root_repaired": root_repaired})
        except Exception as exc:
            errors.append({"file": src_rel, "error": str(exc)})

    validation_runs = []
    # Use compile validation first; runner scripts may execute recovery logic, so do not force live recovery routines here.
    validation_runs.append(run([sys.executable, "-m", "py_compile"] + [m[0] for m in MIGRATIONS] + [m[1] for m in MIGRATIONS]))
    validation_runs.append(run([sys.executable, "scripts/source_reliability_audit.py"]))
    validation_runs.append(run([sys.executable, "scripts/audit_source_freshness.py"]))
    validation_runs.append(run([sys.executable, "scripts/project_ownership_map.py"]))

    reliability = read_json(ROOT / "static" / "data" / "source_reliability_status.json") or {}
    issue_count = (reliability.get("summary") or {}).get("issue_count", reliability.get("issue_count"))
    freshness_overall = (reliability.get("summary") or {}).get("freshness_overall", reliability.get("freshness_overall"))
    user_footprint_status = (reliability.get("summary") or {}).get("user_footprint_status", reliability.get("user_footprint_status"))

    rollback = backup_root / "rollback_builder_module_migration_v3.ps1"
    lines = ['param([string]$ProjectRoot = "C:\\Users\\Luke_C\\Desktop\\JiraObservationMonitor")', '$ErrorActionPreference = "Stop"']
    for item in moved:
        lines.append(f'$backup = Join-Path $ProjectRoot "{item["backup"].replace("/", "\\\\")}"')
        lines.append(f'$script = Join-Path $ProjectRoot "{item["script"].replace("/", "\\\\")}"')
        lines.append('if (Test-Path $backup) { Copy-Item $backup $script -Force; Write-Host "Restored $script" -ForegroundColor Green }')
        lines.append(f'$module = Join-Path $ProjectRoot "{item["module"].replace("/", "\\\\")}"')
        lines.append('if (Test-Path $module) { Remove-Item $module -Force; Write-Host "Removed migrated module $module" -ForegroundColor Yellow }')
    lines.append('Write-Host "Builder module migration v3 rollback complete." -ForegroundColor Green')
    rollback.write_text("\n".join(lines) + "\n", encoding="utf-8")

    validation_ok = all(v.get("returncode") == 0 for v in validation_runs)
    ok = validation_ok and not errors and issue_count == 0 and user_footprint_status == "generated"
    status = {
        "schema": "jom-builder-module-migration-v3-status",
        "generated_at_utc": now_utc(),
        "mode": "phase_3_access_runner_modules_with_wrappers",
        "backup_root": str(backup_root),
        "migration_count": len(MIGRATIONS),
        "moved_count": len(moved),
        "missing_count": len(missing),
        "error_count": len(errors),
        "moved": moved,
        "missing": missing,
        "errors": errors,
        "validation_runs": validation_runs,
        "source_reliability_summary": reliability,
        "issue_count": issue_count,
        "freshness_overall": freshness_overall,
        "user_footprint_status": user_footprint_status,
        "validation_ok": validation_ok,
        "rollback_script": str(rollback),
        "note": "Runner modules are compiled and reliability-checked. Live recovery runner execution is intentionally not forced by install to avoid unnecessary source refresh side effects.",
    }
    STATUS.parent.mkdir(parents=True, exist_ok=True)
    STATUS.write_text(json.dumps(status, indent=2), encoding="utf-8")
    print(json.dumps({"status": "ok" if ok else "attention", "moved_count": len(moved), "missing_count": len(missing), "error_count": len(errors), "validation_ok": validation_ok, "issue_count": issue_count, "freshness_overall": freshness_overall, "user_footprint_status": user_footprint_status, "status_file": str(STATUS)}, indent=2))
    return 0 if ok else 1

if __name__ == "__main__":
    raise SystemExit(main())
