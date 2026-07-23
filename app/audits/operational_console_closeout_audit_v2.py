from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT_JSON = ROOT / "reports" / "operational_console_closeout_audit_v2.json"
OUT_MD = ROOT / "reports" / "operational_console_closeout_audit_v2.md"


def now_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def exists(rel_path: str) -> bool:
    return (ROOT / rel_path).exists()


def read_json(path: Path, default=None):
    if default is None:
        default = {}
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"_read_error": str(exc)}


def run(cmd: list[str], timeout: int = 300) -> dict:
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


def snapshot_controller_is_compatibility_shim() -> bool:
    shim = ROOT / "scripts" / "snapshot_controller.py"
    if not shim.exists():
        return False
    text = shim.read_text(encoding="utf-8", errors="replace")
    return "scripts._legacy_review.snapshot_controller" in text and "compatibility" in text.lower()


def main() -> int:
    reliability = read_json(ROOT / "static" / "data" / "source_reliability_status.json")
    reliability_summary = reliability.get("summary") or {}

    scheduler_query = run(["schtasks", "/Query", "/TN", "JOM_Sync_Runtime", "/V", "/FO", "LIST"])
    scheduler_text = scheduler_query.get("stdout_tail", "")

    validations = {
        "py_compile": run([
            sys.executable,
            "-m",
            "py_compile",
            "web.py",
            "scripts/run_operational_snapshot.py",
            "scripts/source_reliability_audit.py",
            "scripts/snapshot_controller.py",
            "app/registry/site_onboarding_control.py",
        ]),
        "source_reliability_rerun": run([sys.executable, "scripts/source_reliability_audit.py"]),
        "web_import": run([sys.executable, "-c", "import web; print('web_import_ok')"]),
    }

    # Reload reliability after rerun because source_reliability_audit.py updates the JSON.
    reliability = read_json(ROOT / "static" / "data" / "source_reliability_status.json")
    reliability_summary = reliability.get("summary") or {}

    ui_files = [
        "static/data/live_operator_contract",
        "static/data/live_operator_contract",
        "static/data/live_operator_contract",
        "static/data/live_operator_contract",
        "static/data/live_operator_contract",
        "static/data/site_onboarding_review.json",
    ]
    active_scripts = [
        "scripts/run_operational_snapshot.py",
        "scripts/source_reliability_audit.py",
        "scripts/build_site_registry.py",
        "scripts/refresh_runtime_sources.py",
        "scripts/_project_bootstrap.py",
    ]
    legacy_archived = [
        "scripts/_legacy_review/sync_runtime.py",
        "scripts/_legacy_review/snapshot_controller.py",
        "scripts/_legacy_review/run_sync_for_scheduler.cmd",
    ]
    forbidden_legacy_root = [
        "scripts/sync_runtime.py",
        "scripts/run_sync_for_scheduler.cmd",
    ]

    checks = {
        "source_reliability_ok": reliability.get("overall_status") == "ok" and reliability_summary.get("issue_count") == 0,
        "runtime_advisory_present": reliability_summary.get("runtime_refresh_overall") == "ok_with_advisory",
        "scheduler_targets_operational_snapshot": "run_operational_snapshot.py" in scheduler_text and "sync_runtime.py" not in scheduler_text and "run_sync_for_scheduler.cmd" not in scheduler_text,
        "scheduler_start_in_project": str(ROOT) in scheduler_text,
        "ui_files_exist": all(exists(path) for path in ui_files),
        "active_scripts_exist": all(exists(path) for path in active_scripts),
        "snapshot_controller_root_is_shim": snapshot_controller_is_compatibility_shim(),
        "legacy_runtime_not_in_root": all(not exists(path) for path in forbidden_legacy_root),
        "legacy_archived": all(exists(path) for path in legacy_archived),
        "site_onboarding_control_exists": exists("app/registry/site_onboarding_control.py"),
        "py_compile_ok": validations["py_compile"].get("returncode") == 0,
        "reliability_rerun_ok": validations["source_reliability_rerun"].get("returncode") == 0,
        "web_import_ok": validations["web_import"].get("returncode") == 0 and "web_import_ok" in validations["web_import"].get("stdout_tail", ""),
    }

    overall_status = "ok" if all(checks.values()) else "attention"

    payload = {
        "schema": "jom-operational-console-closeout-audit-v2",
        "generated_at_utc": now_utc(),
        "overall_status": overall_status,
        "checks": checks,
        "scheduler_query": scheduler_query,
        "validations": validations,
        "source_reliability": {
            "overall_status": reliability.get("overall_status"),
            "summary": reliability_summary,
            "issues": reliability.get("issues", []),
            "advisories": reliability.get("advisories", []),
        },
        "safety_note": "v2 allows scripts/snapshot_controller.py as a compatibility shim while legacy runtime/scheduler files remain archived.",
    }

    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    md_lines = [
        "# Operational Console Closeout Audit v2",
        "",
        f"Generated: `{payload['generated_at_utc']}`",
        f"Overall status: **{overall_status}**",
        "",
        "## Checks",
    ]
    for key, value in checks.items():
        md_lines.append(f"- {key}: **{value}**")
    md_lines.append("")
    md_lines.append("## Safety Note")
    md_lines.append(payload["safety_note"])
    OUT_MD.write_text("\n".join(md_lines) + "\n", encoding="utf-8")

    print(json.dumps({
        "status": overall_status,
        "report_json": str(OUT_JSON),
        "report_md": str(OUT_MD),
        "checks": checks,
    }, indent=2))
    return 0 if overall_status == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
