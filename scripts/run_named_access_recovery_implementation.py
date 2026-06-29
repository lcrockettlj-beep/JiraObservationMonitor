import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATUS = ROOT / "static" / "data" / "named_access_recovery_status.json"


def now_utc():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def run(script, key, label):
    path = Path(script)
    record = {
        "key": key,
        "label": label,
        "script": script,
        "exists": path.exists(),
        "started_at_utc": now_utc(),
        "finished_at_utc": None,
        "status": "missing",
        "returncode": None,
        "stdout_tail": "",
        "stderr_tail": "",
    }
    if not path.exists():
        record["finished_at_utc"] = now_utc()
        return record
    proc = subprocess.run([sys.executable, script], cwd=ROOT, capture_output=True, text=True)
    record["finished_at_utc"] = now_utc()
    record["returncode"] = proc.returncode
    record["stdout_tail"] = (proc.stdout or "")[-4000:]
    record["stderr_tail"] = (proc.stderr or "")[-4000:]
    record["status"] = "ok" if proc.returncode == 0 else "failed"
    return record


def read_json(path, default=None):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"_read_error": str(exc)}


def main():
    steps = []
    steps.append(run("scripts/build_named_access_truth_v2.py", "named_access_truth_v2", "Build Named Access Truth v2"))
    steps.append(run("scripts/reconcile_named_access_truth_v2.py", "named_access_reconciliation_v2", "Reconcile Named Access Truth v2"))
    if Path("scripts/build_user_footprint_source.py").exists():
        steps.append(run("scripts/build_user_footprint_source.py", "user_footprint_guard", "Rebuild guarded user footprint source"))
    if Path("scripts/source_reliability_audit.py").exists():
        steps.append(run("scripts/source_reliability_audit.py", "source_reliability", "Rebuild source reliability"))

    reconciliation = read_json(ROOT / "reports" / "named_access_reconciliation_v2.json", {}) or {}
    safe = bool(reconciliation.get("safe_to_enable_named_access_ui"))
    overall = "ok" if all(step["status"] == "ok" for step in steps if step["exists"]) else "attention"

    payload = {
        "schema": "jom-named-access-recovery-status-v1",
        "generated_at_utc": now_utc(),
        "overall_status": overall,
        "safe_to_enable_named_access_ui": safe,
        "reconciliation_status": reconciliation.get("status"),
        "steps": steps,
    }
    STATUS.parent.mkdir(parents=True, exist_ok=True)
    STATUS.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps({"overall_status": overall, "safe_to_enable_named_access_ui": safe, "output": str(STATUS)}, indent=2))


if __name__ == "__main__":
    main()
