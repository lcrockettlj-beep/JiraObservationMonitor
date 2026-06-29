from __future__ import annotations

import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATUS = ROOT / "reports" / "registry_module_migration_v2_status.json"
SOURCE = "backend/site_registry_runtime.py"
TARGET = "app/registry/site_registry_runtime.py"
SHIM = 'from __future__ import annotations\n\nfrom app.registry.site_registry_runtime import *  # noqa: F401,F403\n'
ROOT_REPAIRS = [
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
        p = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, timeout=300)
        return {"cmd": " ".join(cmd), "returncode": p.returncode, "stdout_tail": (p.stdout or "")[-3000:], "stderr_tail": (p.stderr or "")[-3000:]}
    except Exception as exc:
        return {"cmd": " ".join(cmd), "returncode": None, "error": str(exc)}


def read_json(path: Path):
    if not path.exists(): return None
    try: return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc: return {"_read_error": str(exc)}


def repair_root(path: Path) -> bool:
    text = path.read_text(encoding="utf-8", errors="replace")
    updated = text
    for old, new in ROOT_REPAIRS:
        updated = updated.replace(old, new)
    if updated != text:
        path.write_text(updated, encoding="utf-8")
        return True
    return False


def monitored_snapshot() -> dict:
    reg = read_json(ROOT / "static" / "data" / "site_registry.json") or {}
    monitored = []
    if isinstance(reg, dict):
        for item in reg.get("sites", []):
            if isinstance(item, dict) and item.get("is_monitored") is True:
                monitored.append(item.get("site_key") or item.get("key") or item.get("site"))
    return {"monitored_keys": sorted([x for x in monitored if x]), "site_registry_exists": (ROOT / "static" / "data" / "site_registry.json").exists()}


def main() -> int:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_root = ROOT / "backups" / f"registry_module_migration_v2_{stamp}"
    backup_root.mkdir(parents=True, exist_ok=True)
    source = ROOT / SOURCE
    target = ROOT / TARGET
    errors, moved = [], []
    before = monitored_snapshot()

    if not source.exists():
        errors.append({"file": SOURCE, "error": "source missing"})
    else:
        text = source.read_text(encoding="utf-8", errors="replace")
        if "from app.registry.site_registry_runtime import" in text:
            errors.append({"file": SOURCE, "error": "source already appears to be shim; refusing to copy shim into app module"})
        else:
            backup = backup_root / SOURCE
            backup.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, backup)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
            root_repaired = repair_root(target)
            source.write_text(SHIM, encoding="utf-8")
            moved.append({"source": SOURCE, "module": TARGET, "backup": rel(backup), "root_repaired": root_repaired, "shim": SOURCE})

    validation_runs = []
    validation_runs.append(run([sys.executable, "-m", "py_compile", SOURCE, TARGET]))
    validation_runs.append(run([sys.executable, "-c", "import backend.site_registry_runtime; import app.registry.site_registry_runtime; print('site registry runtime imports ok')"]))
    validation_runs.append(run([sys.executable, "scripts/route_static_reference_validation.py"]))
    validation_runs.append(run([sys.executable, "scripts/source_reliability_audit.py"]))

    after = monitored_snapshot()
    reliability = read_json(ROOT / "static" / "data" / "source_reliability_status.json") or {}
    issue_count = (reliability.get("summary") or {}).get("issue_count", reliability.get("issue_count"))
    validation_ok = all(v.get("returncode") == 0 for v in validation_runs)
    monitored_unchanged = before == after

    rollback = backup_root / "rollback_registry_module_migration_v2.ps1"
    lines = ['param([string]$ProjectRoot = "C:\\Users\\Luke_C\\Desktop\\JiraObservationMonitor")', '$ErrorActionPreference = "Stop"']
    for item in moved:
        lines.append(f'$backup = Join-Path $ProjectRoot "{item["backup"].replace("/", "\\\\")}"')
        lines.append(f'$source = Join-Path $ProjectRoot "{item["source"].replace("/", "\\\\")}"')
        lines.append('if (Test-Path $backup) { Copy-Item $backup $source -Force; Write-Host "Restored $source" -ForegroundColor Green }')
        lines.append(f'$module = Join-Path $ProjectRoot "{item["module"].replace("/", "\\\\")}"')
        lines.append('if (Test-Path $module) { Remove-Item $module -Force; Write-Host "Removed migrated module $module" -ForegroundColor Yellow }')
    lines.append('Write-Host "Registry module migration v2 rollback complete." -ForegroundColor Green')
    rollback.write_text("\n".join(lines) + "\n", encoding="utf-8")

    ok = validation_ok and not errors and issue_count == 0 and monitored_unchanged
    status = {
        "schema": "jom-registry-module-migration-v2-status",
        "generated_at_utc": now_utc(),
        "mode": "phase_2_registry_runtime_adapter_with_backend_shim",
        "backup_root": str(backup_root),
        "moved_count": len(moved),
        "error_count": len(errors),
        "moved": moved,
        "errors": errors,
        "validation_runs": validation_runs,
        "source_reliability_summary": reliability,
        "issue_count": issue_count,
        "before_monitored": before,
        "after_monitored": after,
        "monitored_unchanged": monitored_unchanged,
        "validation_ok": validation_ok,
        "rollback_script": str(rollback),
        "note": "backend/site_registry_runtime.py is retained as a compatibility shim. web.py import paths should continue to work.",
    }
    STATUS.parent.mkdir(parents=True, exist_ok=True)
    STATUS.write_text(json.dumps(status, indent=2), encoding="utf-8")
    print(json.dumps({"status": "ok" if ok else "attention", "moved_count": len(moved), "error_count": len(errors), "validation_ok": validation_ok, "issue_count": issue_count, "monitored_unchanged": monitored_unchanged, "status_file": str(STATUS)}, indent=2))
    return 0 if ok else 1

if __name__ == "__main__":
    raise SystemExit(main())
