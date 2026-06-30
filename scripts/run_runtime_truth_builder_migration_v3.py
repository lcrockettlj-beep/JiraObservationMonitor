from __future__ import annotations

import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATUS = ROOT / "reports" / "runtime_truth_builder_migration_v3_status.json"

MIGRATIONS = [
    ("scripts/refresh_admin_enriched_chain.py", "app/runtime/admin_enriched_chain.py"),
    ("scripts/run_operational_source_recovery.py", "app/runtime/operational_source_recovery.py"),
    ("scripts/backup_runtime_chain.py", "app/runtime/runtime_backup_chain.py"),
]

ROOT_REPAIRS = [
    ("ROOT = Path(__file__).resolve().parents[1]", "ROOT = Path(__file__).resolve().parents[2]"),
    ("ROOT=Path(__file__).resolve().parents[1]", "ROOT = Path(__file__).resolve().parents[2]"),
    ("PROJECT_ROOT = Path(__file__).resolve().parents[1]", "PROJECT_ROOT = Path(__file__).resolve().parents[2]"),
    ("PROJECT_ROOT=Path(__file__).resolve().parents[1]", "PROJECT_ROOT = Path(__file__).resolve().parents[2]"),
]

IMPORT_MAIN_WRAPPER = 'from __future__ import annotations\n\nfrom _project_bootstrap import ensure_project_root_on_path\nensure_project_root_on_path()\n\nfrom {import_path} import main\n\n\nif __name__ == "__main__":\n    raise SystemExit(main())\n'

RUNPY_WRAPPER = 'from __future__ import annotations\n\nfrom _project_bootstrap import ensure_project_root_on_path\nensure_project_root_on_path()\n\nimport runpy\n\n\nif __name__ == "__main__":\n    runpy.run_module("{module_path}", run_name="__main__")\n'

EXPECTED_MONITORED = {"gli-it-project", "gli-global-technology", "gli-delivery-tm"}


def now_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def run(cmd: list[str], timeout: int = 600) -> dict:
    try:
        proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, timeout=timeout)
        return {
            "cmd": " ".join(cmd),
            "returncode": proc.returncode,
            "stdout_tail": (proc.stdout or "")[-6000:],
            "stderr_tail": (proc.stderr or "")[-6000:],
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


def module_import_path(dst_rel: str) -> str:
    return dst_rel.replace("/", ".").replace("\\", ".").removesuffix(".py")


def wrapper_for(module_path: Path, dst_rel: str) -> tuple[str, str]:
    text = module_path.read_text(encoding="utf-8", errors="replace")
    import_path = module_import_path(dst_rel)
    if "def main" in text:
        return "import_main", IMPORT_MAIN_WRAPPER.format(import_path=import_path)
    return "runpy", RUNPY_WRAPPER.format(module_path=import_path)


def monitored_scope() -> dict:
    reg = read_json(ROOT / "static" / "data" / "site_registry.json") or {}
    monitored, discovered = [], []
    if isinstance(reg, dict):
        for site in reg.get("sites", []):
            if not isinstance(site, dict):
                continue
            key = site.get("site_key") or site.get("key") or site.get("site")
            if site.get("is_monitored") is True or site.get("classification") == "monitored":
                monitored.append(key)
            elif site.get("classification") == "discovered":
                discovered.append(key)
    monitored = sorted([x for x in monitored if x])
    discovered = sorted([x for x in discovered if x])
    return {
        "monitored": monitored,
        "discovered": discovered,
        "expected_monitored": sorted(EXPECTED_MONITORED),
        "monitored_matches_expected": set(monitored) == EXPECTED_MONITORED,
    }


def main() -> int:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_root = ROOT / "backups" / f"runtime_truth_builder_migration_v3_{stamp}"
    backup_root.mkdir(parents=True, exist_ok=True)

    before_scope = monitored_scope()
    moved, missing, errors = [], [], []

    (ROOT / "app" / "runtime").mkdir(parents=True, exist_ok=True)
    init = ROOT / "app" / "runtime" / "__init__.py"
    if not init.exists():
        init.write_text('"""JOM runtime modules."""\n', encoding="utf-8")

    for src_rel, dst_rel in MIGRATIONS:
        src = ROOT / src_rel
        dst = ROOT / dst_rel
        if not src.exists():
            missing.append(src_rel)
            continue
        try:
            src_text = src.read_text(encoding="utf-8", errors="replace")
            import_path = module_import_path(dst_rel)
            if f"from {import_path} import main" in src_text or f'runpy.run_module("{import_path}"' in src_text:
                errors.append({"file": src_rel, "error": "source already appears to be wrapper; refusing to copy wrapper into app module"})
                continue
            backup = backup_root / src_rel
            backup.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, backup)
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
            root_repaired = repair_root(dst)
            wrapper_style, wrapper_text = wrapper_for(dst, dst_rel)
            src.write_text(wrapper_text, encoding="utf-8")
            moved.append({
                "script": src_rel,
                "module": dst_rel,
                "backup": rel(backup),
                "wrapper_style": wrapper_style,
                "root_repaired": root_repaired,
            })
        except Exception as exc:
            errors.append({"file": src_rel, "error": str(exc)})

    validation_runs = []
    # v3 scripts are orchestration/recovery/backup scripts, so do not force-run recovery by default during install.
    validation_runs.append(run([sys.executable, "-m", "py_compile"] + [m[0] for m in MIGRATIONS] + [m[1] for m in MIGRATIONS]))
    validation_runs.append(run([sys.executable, "scripts/source_reliability_audit.py"]))
    validation_runs.append(run([sys.executable, "scripts/run_operational_snapshot.py"]))
    validation_runs.append(run([sys.executable, "scripts/source_reliability_audit.py"]))

    reliability = read_json(ROOT / "static" / "data" / "source_reliability_status.json") or {}
    summary = reliability.get("summary") or {}
    issue_count = summary.get("issue_count", reliability.get("issue_count"))
    freshness_overall = summary.get("freshness_overall", reliability.get("freshness_overall"))
    runtime_refresh_overall = summary.get("runtime_refresh_overall", reliability.get("runtime_refresh_overall"))
    after_scope = monitored_scope()
    monitored_unchanged = before_scope == after_scope

    rollback = backup_root / "rollback_runtime_truth_builder_migration_v3.ps1"
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
    lines.append('Write-Host "Runtime truth builder migration v3 rollback complete." -ForegroundColor Green')
    rollback.write_text("\n".join(lines) + "\n", encoding="utf-8")

    validation_ok = all(v.get("returncode") == 0 for v in validation_runs)
    ok = validation_ok and not errors and not missing and issue_count == 0 and monitored_unchanged and after_scope.get("monitored_matches_expected") is True

    status = {
        "schema": "jom-runtime-truth-builder-migration-v3-status",
        "generated_at_utc": now_utc(),
        "mode": "phase_3_runtime_chain_orchestration_with_wrappers_compile_only",
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
        "runtime_refresh_overall": runtime_refresh_overall,
        "before_monitored_scope": before_scope,
        "after_monitored_scope": after_scope,
        "monitored_unchanged": monitored_unchanged,
        "validation_ok": validation_ok,
        "rollback_script": str(rollback),
        "note": "v3 only compiles orchestration/recovery/backup wrappers and runs snapshot/reliability. It intentionally does not force-run source recovery or backup chain scripts during install.",
    }
    STATUS.parent.mkdir(parents=True, exist_ok=True)
    STATUS.write_text(json.dumps(status, indent=2), encoding="utf-8")

    print(json.dumps({
        "status": "ok" if ok else "attention",
        "moved_count": len(moved),
        "missing_count": len(missing),
        "error_count": len(errors),
        "validation_ok": validation_ok,
        "issue_count": issue_count,
        "freshness_overall": freshness_overall,
        "runtime_refresh_overall": runtime_refresh_overall,
        "monitored_unchanged": monitored_unchanged,
        "status_file": str(STATUS),
    }, indent=2))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
