from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[2]
STATUS = ROOT / "static" / "data" / "operational_source_recovery_status.json"


def now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _tail(value: str, limit: int = 1200) -> str:
    return (value or "")[-limit:]


def _module_exists(module_name: str) -> bool:
    try:
        return importlib.util.find_spec(module_name) is not None
    except Exception:
        return False


def _run_command(cmd: List[str], key: str, label: str, exists: bool = True) -> Dict[str, Any]:
    rec: Dict[str, Any] = {
        "key": key,
        "label": label,
        "command": " ".join(cmd),
        "exists": bool(exists),
        "started_at_utc": now(),
        "finished_at_utc": None,
        "status": "missing",
        "returncode": None,
        "stdout_tail": "",
        "stderr_tail": "",
    }
    if not exists:
        rec["finished_at_utc"] = now()
        return rec

    proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    rec["finished_at_utc"] = now()
    rec["returncode"] = proc.returncode
    rec["stdout_tail"] = _tail(proc.stdout)
    rec["stderr_tail"] = _tail(proc.stderr)
    rec["status"] = "ok" if proc.returncode == 0 else "failed"
    return rec


def run(candidates: List[Dict[str, str]], key: str, label: str) -> Dict[str, Any]:
    for candidate in candidates:
        ctype = candidate.get("type")
        value = candidate.get("value", "")
        if ctype == "module" and value and _module_exists(value):
            return _run_command([sys.executable, "-m", value], key, label, exists=True)
        if ctype == "script" and value:
            path = ROOT / value
            if path.exists():
                return _run_command([sys.executable, value], key, label, exists=True)

    return {
        "key": key,
        "label": label,
        "command": " | ".join(c.get("value", "") for c in candidates),
        "exists": False,
        "started_at_utc": now(),
        "finished_at_utc": now(),
        "status": "missing",
        "returncode": None,
        "stdout_tail": "",
        "stderr_tail": "No command candidate exists",
    }


def main() -> Dict[str, Any]:
    steps: List[Dict[str, Any]] = []

    steps.append(run([
        {"type": "module", "value": "app.runtime.admin_enriched_chain"},
        {"type": "script", "value": "scripts/refresh_admin_enriched_chain.py"},
    ], "admin_enriched_refresh", "Refresh admin-enriched runtime + admin truth"))

    steps.append(run([
        {"type": "module", "value": "app.builders.product_access_sources"},
        {"type": "script", "value": "scripts/refresh_product_access_sources.py"},
    ], "product_access_refresh", "Refresh estate product/access truth"))

    steps.append(run([
        {"type": "module", "value": "app.access.named_access_recovery_plan"},
        {"type": "script", "value": "scripts/build_named_access_recovery_plan.py"},
    ], "named_access_recovery_plan", "Build named access recovery plan"))

    steps.append(run([
        {"type": "module", "value": "app.audits.source_freshness"},
        {"type": "script", "value": "scripts/audit_source_freshness.py"},
    ], "source_freshness", "Rebuild source freshness audit"))

    steps.append(run([
        {"type": "module", "value": "app.access.user_footprint_source"},
        {"type": "script", "value": "scripts/build_user_footprint_source.py"},
    ], "user_footprint_guard", "Rebuild guarded user footprint source"))

    steps.append(run([
        {"type": "module", "value": "app.audits.source_reliability"},
        {"type": "script", "value": "scripts/source_reliability_audit.py"},
    ], "source_reliability", "Rebuild source reliability status"))

    existing_steps = [s for s in steps if s.get("exists")]
    overall = "ok" if existing_steps and all(s.get("status") == "ok" for s in existing_steps) else "attention"

    payload: Dict[str, Any] = {
        "schema": "jom-operational-source-recovery-status-v2",
        "generated_at_utc": now(),
        "overall_status": overall,
        "steps": steps,
    }
    STATUS.parent.mkdir(parents=True, exist_ok=True)
    STATUS.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return payload


def run_pipeline() -> Dict[str, Any]:
    """External API/runner entrypoint."""
    return main()


if __name__ == "__main__":
    main()
