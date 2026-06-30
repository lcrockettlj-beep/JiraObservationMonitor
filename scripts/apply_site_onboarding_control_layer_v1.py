from __future__ import annotations

import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATUS = ROOT / "reports" / "site_onboarding_control_layer_v1_status.json"
CONTROL_MODULE = ROOT / "app" / "registry" / "site_onboarding_control.py"
REGISTRY_BUILDER = ROOT / "app" / "registry" / "site_registry_builder.py"
SNAPSHOT_SCRIPT = ROOT / "scripts" / "run_operational_snapshot.py"


def now_utc():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace") if path.exists() else ""


def read_json(path: Path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def write_json(path: Path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def run(cmd, timeout=420):
    try:
        p = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, timeout=timeout)
        return {"cmd": " ".join(cmd), "returncode": p.returncode, "stdout_tail": (p.stdout or "")[-4000:], "stderr_tail": (p.stderr or "")[-4000:]}
    except Exception as exc:
        return {"cmd": " ".join(cmd), "returncode": None, "error": str(exc)}


def patch_file_once(path: Path, marker: str, block: str):
    text = read_text(path)
    if marker in text:
        return {"path": str(path), "changed": False, "reason": "already patched"}
    if not text.strip():
        return {"path": str(path), "changed": False, "reason": "empty/missing file"}
    new_text = text.rstrip() + "\n\n" + block.strip() + "\n"
    path.write_text(new_text, encoding="utf-8")
    return {"path": str(path), "changed": True, "reason": "control hook appended"}


def main():
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_root = ROOT / "backups" / f"site_onboarding_control_layer_v1_{stamp}"
    backup_root.mkdir(parents=True, exist_ok=True)
    changes = []
    errors = []
    for path in [CONTROL_MODULE, REGISTRY_BUILDER, SNAPSHOT_SCRIPT]:
        if path.exists():
            backup = backup_root / path.relative_to(ROOT)
            backup.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, backup)
    registry_hook = """
# JOM_SITE_ONBOARDING_CONTROL_V1
try:
    from app.registry.site_onboarding_control import get_site_state, is_site_approved
except Exception:
    def get_site_state(site_key):
        return "pending"
    def is_site_approved(site_key):
        return False
"""
    snapshot_hook = """
# JOM_SITE_ONBOARDING_CONTROL_V1
try:
    from app.registry.site_onboarding_control import load_decisions, normalise_legacy_decisions
    _jom_onboarding_decisions = normalise_legacy_decisions(load_decisions())
except Exception:
    _jom_onboarding_decisions = None
"""
    try:
        changes.append(patch_file_once(REGISTRY_BUILDER, "JOM_SITE_ONBOARDING_CONTROL_V1", registry_hook))
    except Exception as exc:
        errors.append({"file": str(REGISTRY_BUILDER), "error": str(exc)})
    try:
        changes.append(patch_file_once(SNAPSHOT_SCRIPT, "JOM_SITE_ONBOARDING_CONTROL_V1", snapshot_hook))
    except Exception as exc:
        errors.append({"file": str(SNAPSHOT_SCRIPT), "error": str(exc)})
    decisions = read_json(ROOT / "config" / "site_onboarding_decisions.json", {})
    if not isinstance(decisions, dict):
        decisions = {}
    decisions.setdefault("schema", "jom-site-onboarding-decisions-v1")
    decisions.setdefault("generated_at_utc", now_utc())
    decisions.setdefault("sites", {})
    decisions.setdefault("approved", {})
    decisions.setdefault("ignored", {})
    decisions.setdefault("history", [])
    write_json(ROOT / "config" / "site_onboarding_decisions.json", decisions)
    validations = [
        run([sys.executable, "-m", "py_compile", "app/registry/site_onboarding_control.py", "app/registry/site_registry_builder.py", "scripts/run_operational_snapshot.py"]),
        run([sys.executable, "scripts/build_site_onboarding_review.py"]),
        run([sys.executable, "scripts/source_reliability_audit.py"]),
    ]
    reliability = read_json(ROOT / "static" / "data" / "source_reliability_status.json", {})
    summary = reliability.get("summary") or {}
    issue_count = summary.get("issue_count", reliability.get("issue_count"))
    validation_ok = all(v.get("returncode") == 0 for v in validations) and reliability.get("overall_status") == "ok" and issue_count == 0
    rollback = backup_root / "rollback_site_onboarding_control_layer_v1.ps1"
    rollback_content = '$ErrorActionPreference = "Stop"\n'
    rollback_content += f'$BackupRoot = "{backup_root}"\n'
    rollback_content += '$ProjectRoot = "C:\\Users\\Luke_C\\Desktop\\JiraObservationMonitor"\n'
    rollback_content += 'Copy-Item (Join-Path $BackupRoot "app\\registry\\site_registry_builder.py") (Join-Path $ProjectRoot "app\\registry\\site_registry_builder.py") -Force -ErrorAction SilentlyContinue\n'
    rollback_content += 'Copy-Item (Join-Path $BackupRoot "scripts\\run_operational_snapshot.py") (Join-Path $ProjectRoot "scripts\\run_operational_snapshot.py") -Force -ErrorAction SilentlyContinue\n'
    rollback_content += 'Remove-Item (Join-Path $ProjectRoot "app\\registry\\site_onboarding_control.py") -Force -ErrorAction SilentlyContinue\n'
    rollback_content += 'Write-Host "Site onboarding control layer rollback complete." -ForegroundColor Green\n'
    rollback.write_text(rollback_content, encoding="utf-8")
    status = {
        "schema": "jom-site-onboarding-control-layer-v1-status",
        "generated_at_utc": now_utc(),
        "status": "ok" if validation_ok and not errors else "attention",
        "mode": "backend-midend-control-layer-no-ui-interface-change",
        "backup_root": str(backup_root),
        "rollback_script": str(rollback),
        "changes": changes,
        "errors": errors,
        "validations": validations,
        "source_reliability_issue_count": issue_count,
        "validation_ok": validation_ok,
        "safety_note": "Backend/mid-end onboarding control only. No visual UI interface changes were made.",
    }
    write_json(STATUS, status)
    print(json.dumps({k: status[k] for k in ["status", "mode", "validation_ok", "source_reliability_issue_count", "backup_root", "rollback_script", "safety_note"]}, indent=2))
    return 0 if status["status"] == "ok" else 1

if __name__ == "__main__":
    raise SystemExit(main())
