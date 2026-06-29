from __future__ import annotations
import json, shutil, subprocess, sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATUS = ROOT / "reports" / "audit_module_migration_v2_status.json"

MIGRATIONS = [
    ("scripts/audit_source_freshness.py", "app/audits/source_freshness.py", "source_freshness"),
    ("scripts/source_reliability_audit.py", "app/audits/source_reliability.py", "source_reliability"),
]

WRAPPER_TEMPLATE = """from __future__ import annotations

from _project_bootstrap import ensure_project_root_on_path
ensure_project_root_on_path()

from app.audits.{module_name} import main


if __name__ == \"__main__\":
    raise SystemExit(main())
"""

def now_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")

def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()

def run(cmd: list[str]) -> dict:
    try:
        p = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, timeout=240)
        return {"cmd": " ".join(cmd), "returncode": p.returncode, "stdout_tail": (p.stdout or "")[-2500:], "stderr_tail": (p.stderr or "")[-2500:]}
    except Exception as exc:
        return {"cmd": " ".join(cmd), "returncode": None, "error": str(exc)}

def repair_root_in_module(path: Path) -> bool:
    text = path.read_text(encoding="utf-8", errors="replace")
    updated = text.replace("ROOT = Path(__file__).resolve().parents[1]", "ROOT = Path(__file__).resolve().parents[2]")
    updated = updated.replace("ROOT=Path(__file__).resolve().parents[1]", "ROOT = Path(__file__).resolve().parents[2]")
    if updated != text:
        path.write_text(updated, encoding="utf-8")
        return True
    return False

def main() -> int:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_root = ROOT / "backups" / f"audit_module_migration_v2_{stamp}"
    backup_root.mkdir(parents=True, exist_ok=True)
    moved, missing, errors = [], [], []
    (ROOT / "app" / "audits").mkdir(parents=True, exist_ok=True)

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
    for src_rel, _, _ in MIGRATIONS:
        if (ROOT / src_rel).exists(): validation_runs.append(run([sys.executable, src_rel]))
    validation_runs.append(run([sys.executable, "scripts/project_ownership_map.py"]))
    validation_runs.append(run([sys.executable, "scripts/route_static_reference_validation.py"]))
    validation_runs.append(run([sys.executable, "-m", "py_compile"] + [m[0] for m in MIGRATIONS] + [m[1] for m in MIGRATIONS]))

    reliability_json = ROOT / "static" / "data" / "source_reliability_status.json"
    reliability = None
    if reliability_json.exists():
        try: reliability = json.loads(reliability_json.read_text(encoding="utf-8"))
        except Exception as exc: reliability = {"_read_error": str(exc)}

    freshness_json = ROOT / "static" / "data" / "source_freshness_audit.json"
    freshness = None
    if freshness_json.exists():
        try: freshness = json.loads(freshness_json.read_text(encoding="utf-8"))
        except Exception as exc: freshness = {"_read_error": str(exc)}

    rollback = backup_root / "rollback_audit_module_migration_v2.ps1"
    lines = ['param([string]$ProjectRoot = "C:\\Users\\Luke_C\\Desktop\\JiraObservationMonitor")', '$ErrorActionPreference = "Stop"']
    for item in moved:
        lines.append(f'$backup = Join-Path $ProjectRoot "{item["backup"].replace("/", "\\\\")}"')
        lines.append(f'$script = Join-Path $ProjectRoot "{item["script"].replace("/", "\\\\")}"')
        lines.append('if (Test-Path $backup) { Copy-Item $backup $script -Force; Write-Host "Restored $script" -ForegroundColor Green }')
        lines.append(f'$module = Join-Path $ProjectRoot "{item["module"].replace("/", "\\\\")}"')
        lines.append('if (Test-Path $module) { Remove-Item $module -Force; Write-Host "Removed migrated module $module" -ForegroundColor Yellow }')
    lines.append('Write-Host "Audit module migration v2 rollback complete." -ForegroundColor Green')
    rollback.write_text("\n".join(lines) + "\n", encoding="utf-8")

    validation_ok = all(v.get("returncode") == 0 for v in validation_runs)
    issue_count = ((reliability or {}).get("summary") or {}).get("issue_count", (reliability or {}).get("issue_count"))
    freshness_overall = ((reliability or {}).get("summary") or {}).get("freshness_overall", (reliability or {}).get("freshness_overall"))

    status = {
        "schema": "jom-audit-module-migration-v2-status",
        "generated_at_utc": now_utc(),
        "mode": "phase_2_source_truth_audits_with_wrappers",
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
        "source_freshness_summary": freshness,
        "issue_count": issue_count,
        "freshness_overall": freshness_overall,
        "validation_ok": validation_ok,
        "rollback_script": str(rollback),
    }
    STATUS.parent.mkdir(parents=True, exist_ok=True)
    STATUS.write_text(json.dumps(status, indent=2), encoding="utf-8")
    ok = validation_ok and not errors and issue_count == 0
    print(json.dumps({"status": "ok" if ok else "attention", "moved_count": len(moved), "missing_count": len(missing), "error_count": len(errors), "validation_ok": validation_ok, "issue_count": issue_count, "freshness_overall": freshness_overall, "status_file": str(STATUS)}, indent=2))
    return 0 if ok else 1

if __name__ == "__main__":
    raise SystemExit(main())
