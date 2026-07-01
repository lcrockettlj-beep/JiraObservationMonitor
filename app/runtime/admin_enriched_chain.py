from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parents[2]
STATUS = ROOT / "static" / "data" / "admin_enriched_refresh_status.json"


def now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _tail(value: str, limit: int = 1200) -> str:
    text = value or ""
    return text[-limit:]


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
    """
    Resolve and execute the first available command candidate.

    Candidate forms:
      {"type": "module", "value": "app.builders.example"}
      {"type": "script", "value": "scripts/example.py"}
    """
    for candidate in candidates:
        ctype = candidate.get("type")
        value = candidate.get("value", "")
        if ctype == "module" and value and _module_exists(value):
            return _run_command([sys.executable, "-m", value], key, label, exists=True)
        if ctype == "script" and value:
            path = ROOT / value
            if path.exists():
                return _run_command([sys.executable, value], key, label, exists=True)

    missing_rec = {
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
    return missing_rec


def freshness(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {"exists": False, "state": "MISSING"}
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return {"exists": True, "state": "INVALID_JSON"}
    ts = data.get("generated_at_utc") or data.get("generated_at") or data.get("timestamp") or data.get("updated_at")
    return {"exists": True, "state": "PRESENT", "timestamp": ts}


def main() -> Dict[str, Any]:
    steps: List[Dict[str, Any]] = []

    steps.append(run([
        {"type": "module", "value": "app.builders.admin_enriched_sources"},
        {"type": "script", "value": "admin_api_enrichment.py"},
    ], "admin_api_enrichment", "Refresh latest_run_admin_enriched from current latest_run"))

    steps.append(run([
        {"type": "module", "value": "app.builders.admin_truth_layer_v2"},
        {"type": "script", "value": "scripts/build_admin_truth_layer_v2.py"},
    ], "admin_truth_v2", "Rebuild Admin Truth Layer v2"))

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
        "schema": "jom-admin-enriched-refresh-status-v2",
        "generated_at_utc": now(),
        "overall_status": overall,
        "latest_run_admin_enriched": freshness(ROOT / "latest_run_admin_enriched.json"),
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
