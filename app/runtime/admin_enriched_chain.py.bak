import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
STATUS = ROOT / "static" / "data" / "admin_enriched_refresh_status.json"

def now():
    return datetime.now(timezone.utc).isoformat().replace('+00:00','Z')

def run(cmd, key, label):
    exists = Path(cmd[1]).exists() if len(cmd) > 1 else True
    rec = {"key": key, "label": label, "command": " ".join(cmd), "exists": exists, "started_at_utc": now(), "finished_at_utc": None, "status": "missing", "returncode": None, "stdout_tail": "", "stderr_tail": ""}
    if not exists:
        rec["finished_at_utc"] = now(); return rec
    proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    rec["finished_at_utc"] = now(); rec["returncode"] = proc.returncode
    rec["stdout_tail"] = (proc.stdout or "")[-4000:]; rec["stderr_tail"] = (proc.stderr or "")[-4000:]
    rec["status"] = "ok" if proc.returncode == 0 else "failed"
    return rec

def freshness(path):
    if not path.exists():
        return {"exists": False, "state": "MISSING"}
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
    except Exception:
        return {"exists": True, "state": "INVALID_JSON"}
    ts = ((data.get('raw_collection_summary') or {}).get('collected_at_utc') or data.get('generated_at_utc') or data.get('run_timestamp_local'))
    return {"exists": True, "state": "PRESENT", "timestamp": ts}

def main():
    steps = []
    steps.append(run([sys.executable, 'admin_api_enrichment.py'], 'admin_api_enrichment', 'Refresh latest_run_admin_enriched from current latest_run'))
    steps.append(run([sys.executable, 'scripts/build_admin_truth_layer_v2.py'], 'admin_truth_v2', 'Rebuild Admin Truth Layer v2'))
    if Path('scripts/audit_source_freshness.py').exists():
        steps.append(run([sys.executable, 'scripts/audit_source_freshness.py'], 'source_freshness', 'Rebuild source freshness audit'))
    if Path('scripts/build_user_footprint_source.py').exists():
        steps.append(run([sys.executable, 'scripts/build_user_footprint_source.py'], 'user_footprint_guard', 'Rebuild guarded user footprint source'))
    if Path('scripts/source_reliability_audit.py').exists():
        steps.append(run([sys.executable, 'scripts/source_reliability_audit.py'], 'source_reliability', 'Rebuild source reliability status'))
    overall = 'ok' if all(s['status'] == 'ok' for s in steps if s['exists']) else 'attention'
    payload = {"schema":"jom-admin-enriched-refresh-status-v1.1", "generated_at_utc": now(), "overall_status": overall, "latest_run_admin_enriched": freshness(ROOT/'latest_run_admin_enriched.json'), "steps": steps}
    STATUS.parent.mkdir(parents=True, exist_ok=True)
    STATUS.write_text(json.dumps(payload, indent=2), encoding='utf-8')
    print(json.dumps({"overall_status": overall, "output": str(STATUS)}, indent=2))

if __name__ == '__main__':
    main()
