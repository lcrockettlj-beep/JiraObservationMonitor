from __future__ import annotations

import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATUS = ROOT / "reports" / "registry_module_migration_v1_status.json"

SOURCE_SCRIPT = "scripts/build_site_registry.py"
TARGET_MODULE = "app/registry/site_registry_builder.py"
WRAPPER_MODULE = "site_registry_builder"

WRAPPER_TEMPLATE = """from __future__ import annotations

from _project_bootstrap import ensure_project_root_on_path
ensure_project_root_on_path()

from app.registry.{module_name} import main


if __name__ == \"__main__\":
    raise SystemExit(main())
"""

ROOT_REPAIRS = [
    ("ROOT = Path(__file__).resolve().parents[1]", "ROOT = Path(__file__).resolve().parents[2]"),
    ("ROOT=Path(__file__).resolve().parents[1]", "ROOT = Path(__file__).resolve().parents[2]"),
    ("PROJECT_ROOT = Path(__file__).resolve().parents[1]", "PROJECT_ROOT = Path(__file__).resolve().parents[2]"),
    ("PROJECT_ROOT=Path(__file__).resolve().parents[1]", "PROJECT_ROOT = Path(__file__).resolve().parents[2]"),
]

EXPECTED_MONITORED = {"gli-it-project", "gli-global-technology", "gli-delivery-tm"}


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


def read_json(path: Path):
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"_read_error": str(exc)}


def repair_root(path: Path) -> bool:
    text = path.read_text(encoding="utf-8", errors="replace")
    updated = text
    for old, new in ROOT_REPAIRS:
        updated = updated.replace(old, new)
    if updated != text:
        path.write_text(updated, encoding="utf-8")
        return True
    return False


def extract_site_key(item):
    if isinstance(item, str):
        return item
    if isinstance(item, dict):
        for key in ("site_key", "key", "slug", "site", "name"):
            value = item.get(key)
            if isinstance(value, str):
                return value
    return None


def monitored_site_snapshot() -> dict:
    config = read_json(ROOT / "config" / "monitored_sites.json")
    registry = read_json(ROOT / "static" / "data" / "site_registry.json")
    keys = set()

    if isinstance(config, list):
        for item in config:
            k = extract_site_key(item)
            if k:
                keys.add(k)
    elif isinstance(config, dict):
        for container_key in ("monitored_sites", "sites", "approved_sites", "monitored"):
            value = config.get(container_key)
            if isinstance(value, list):
                for item in value:
                    k = extract_site_key(item)
                    if k:
                        keys.add(k)
        for k, v in config.items():
            if isinstance(v, bool) and v:
                keys.add(k)

    registry_keys = set()
    if isinstance(registry, dict):
        for container_key in ("monitored_sites", "sites", "approved_sites", "registry"):
            value = registry.get(container_key)
            if isinstance(value, list):
                for item in value:
                    if isinstance(item, dict):
                        monitored = item.get("monitored") or item.get("approved") or item.get("is_monitored")
                        k = extract_site_key(item)
                        if k and monitored is True:
                            registry_keys.add(k)
                    else:
                        k = extract_site_key(item)
                        if k:
                            registry_keys.add(k)
    return {
        "config_monitored_keys": sorted(keys),
        "registry_monitored_keys": sorted(registry_keys),
        "expected_monitored_keys": sorted(EXPECTED_MONITORED),
    }


def main() -> int:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_root = ROOT / "backups" / f"registry_module_migration_v1_{stamp}"
    backup_root.mkdir(parents=True, exist_ok=True)

    errors = []
    moved = []
    source = ROOT / SOURCE_SCRIPT
    target = ROOT / TARGET_MODULE

    before_monitored = monitored_site_snapshot()

    if not source.exists():
        errors.append({"file": SOURCE_SCRIPT, "error": "source script missing"})
    else:
        text = source.read_text(encoding="utf-8", errors="replace")
        if f"from app.registry.{WRAPPER_MODULE} import main" in text:
            errors.append({"file": SOURCE_SCRIPT, "error": "source script already appears to be a wrapper; refusing to copy wrapper into app module"})
        else:
            backup = backup_root / SOURCE_SCRIPT
            backup.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, backup)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
            root_repaired = repair_root(target)
            source.write_text(WRAPPER_TEMPLATE.format(module_name=WRAPPER_MODULE), encoding="utf-8")
            moved.append({"script": SOURCE_SCRIPT, "module": TARGET_MODULE, "backup": rel(backup), "root_repaired": root_repaired})

    validation_runs = []
    if not errors:
        validation_runs.append(run([sys.executable, SOURCE_SCRIPT]))
    validation_runs.append(run([sys.executable, "scripts/source_reliability_audit.py"]))
    validation_runs.append(run([sys.executable, "scripts/route_static_reference_validation.py"]))
    validation_runs.append(run([sys.executable, "-m", "py_compile", SOURCE_SCRIPT, TARGET_MODULE]))

    after_monitored = monitored_site_snapshot()
    reliability = read_json(ROOT / "static" / "data" / "source_reliability_status.json") or {}
    issue_count = (reliability.get("summary") or {}).get("issue_count", reliability.get("issue_count"))
    freshness_overall = (reliability.get("summary") or {}).get("freshness_overall", reliability.get("freshness_overall"))

    rollback = backup_root / "rollback_registry_module_migration_v1.ps1"
    lines = [
        'param([string]$ProjectRoot = "C:\\Users\\Luke_C\\Desktop\\JiraObservationMonitor")',
        '$ErrorActionPreference = "Stop"',
    ]
    for item in moved:
        lines.append(f'$backup = Join-Path $ProjectRoot "{item["backup"].replace("/", "\\\\")}"')
        lines.append(f'$script = Join-Path $ProjectRoot "{item["script"].replace("/", "\\\\")}"')
        lines.append('if (Test-Path $backup) { Copy-Item $backup $script -Force; Write-Host "Restored $script" -ForegroundColor Green }')
        lines.append(f'$module = Join-Path $ProjectRoot "{item["module"].replace("/", "\\\\")}"')
        lines.append('if (Test-Path $module) { Remove-Item $module -Force; Write-Host "Removed migrated module $module" -ForegroundColor Yellow }')
    lines.append('Write-Host "Registry module migration v1 rollback complete." -ForegroundColor Green')
    rollback.write_text("\n".join(lines) + "\n", encoding="utf-8")

    validation_ok = all(v.get("returncode") == 0 for v in validation_runs)
    monitored_unchanged = before_monitored == after_monitored
    ok = validation_ok and not errors and issue_count == 0 and (ROOT / "static" / "data" / "site_registry.json").exists()

    status = {
        "schema": "jom-registry-module-migration-v1-status",
        "generated_at_utc": now_utc(),
        "mode": "phase_1_registry_builder_only_with_wrapper",
        "backup_root": str(backup_root),
        "moved_count": len(moved),
        "error_count": len(errors),
        "moved": moved,
        "errors": errors,
        "validation_runs": validation_runs,
        "source_reliability_summary": reliability,
        "issue_count": issue_count,
        "freshness_overall": freshness_overall,
        "before_monitored": before_monitored,
        "after_monitored": after_monitored,
        "monitored_unchanged": monitored_unchanged,
        "site_registry_exists": (ROOT / "static" / "data" / "site_registry.json").exists(),
        "validation_ok": validation_ok,
        "rollback_script": str(rollback),
        "note": "Only scripts/build_site_registry.py was migrated. Config and static data paths are intentionally unchanged.",
    }
    STATUS.parent.mkdir(parents=True, exist_ok=True)
    STATUS.write_text(json.dumps(status, indent=2), encoding="utf-8")
    print(json.dumps({
        "status": "ok" if ok else "attention",
        "moved_count": len(moved),
        "error_count": len(errors),
        "validation_ok": validation_ok,
        "issue_count": issue_count,
        "freshness_overall": freshness_overall,
        "monitored_unchanged": monitored_unchanged,
        "site_registry_exists": status["site_registry_exists"],
        "status_file": str(STATUS),
    }, indent=2))
    return 0 if ok else 1

if __name__ == "__main__":
    raise SystemExit(main())
