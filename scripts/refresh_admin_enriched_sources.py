import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
STATUS_PATH = PROJECT_ROOT / "static" / "data" / "admin_enriched_refresh_status.json"
ADMIN_ENRICHED = PROJECT_ROOT / "latest_run_admin_enriched.json"
ADMIN_ENRICHED_PRETTY = PROJECT_ROOT / "latest_run_admin_enriched_pretty.json"
LATEST_RUN = PROJECT_ROOT / "latest_run.json"

# Candidate scripts are intentionally conservative. The pack will not invent admin-enriched data.
# It will run a detected existing project script only, otherwise it records manual action required.
CANDIDATES = [
    [sys.executable, "scripts/enrich_admin_runtime.py"],
    [sys.executable, "scripts/build_admin_enriched.py"],
    [sys.executable, "scripts/admin_enrichment.py"],
    [sys.executable, "admin_enrichment.py"],
    [sys.executable, "build_admin_enriched.py"],
]

REBUILD_STEPS = [
    {"key": "admin_truth_v2", "label": "Admin Truth v2 rebuild", "command": [sys.executable, "scripts/build_admin_truth_v2.py"], "required": False},
    {"key": "source_freshness", "label": "Source Freshness rebuild", "command": [sys.executable, "scripts/audit_source_freshness.py"], "required": False},
    {"key": "source_reliability", "label": "Source Reliability rebuild", "command": [sys.executable, "scripts/source_reliability_audit.py"], "required": False},
]


def now_dt():
    return datetime.now(timezone.utc)


def now_utc():
    return now_dt().isoformat().replace('+00:00', 'Z')


def parse_time(value):
    if not value:
        return None
    text = str(value).strip()
    if text.endswith('Z'):
        text = text[:-1] + '+00:00'
    try:
        dt = datetime.fromisoformat(text)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        pass
    try:
        return datetime.strptime(str(value).strip(), '%Y-%m-%d %H:%M:%S').replace(tzinfo=timezone.utc)
    except Exception:
        return None


def read_json(path):
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except Exception:
        return None


def nested(data, dotted):
    cur = data
    for part in dotted.split('.'):
        if not isinstance(cur, dict) or part not in cur:
            return None
        cur = cur[part]
    return cur


def file_freshness(path):
    payload = read_json(path)
    if not payload:
        return {"path": str(path.relative_to(PROJECT_ROOT)), "exists": path.exists(), "freshness_state": "MISSING" if not path.exists() else "UNKNOWN_TIMESTAMP", "age_hours": None, "timestamp": None}
    timestamp = nested(payload, 'raw_collection_summary.collected_at_utc') or payload.get('generated_at_utc') or payload.get('run_timestamp_local')
    parsed = parse_time(timestamp)
    if not parsed:
        return {"path": str(path.relative_to(PROJECT_ROOT)), "exists": True, "freshness_state": "UNKNOWN_TIMESTAMP", "age_hours": None, "timestamp": timestamp}
    age = round((now_dt() - parsed).total_seconds() / 3600, 2)
    if age <= 24:
        state = 'CURRENT'
    elif age <= 72:
        state = 'AGING'
    else:
        state = 'STALE'
    return {"path": str(path.relative_to(PROJECT_ROOT)), "exists": True, "freshness_state": state, "age_hours": age, "timestamp": parsed.isoformat().replace('+00:00','Z')}


def run_command(cmd, key, label):
    exists = Path(cmd[1]).exists() if len(cmd) > 1 else False
    record = {"key": key, "label": label, "command": " ".join(cmd), "exists": exists, "started_at_utc": now_utc(), "finished_at_utc": None, "status": "missing", "returncode": None, "stdout_tail": "", "stderr_tail": ""}
    if not exists:
        record["finished_at_utc"] = now_utc()
        return record
    proc = subprocess.run(cmd, cwd=PROJECT_ROOT, capture_output=True, text=True)
    record["finished_at_utc"] = now_utc()
    record["returncode"] = proc.returncode
    record["stdout_tail"] = (proc.stdout or "")[-4000:]
    record["stderr_tail"] = (proc.stderr or "")[-4000:]
    record["status"] = "ok" if proc.returncode == 0 else "failed"
    return record


def find_admin_script():
    for cmd in CANDIDATES:
        if Path(cmd[1]).exists():
            return cmd
    return None


def main():
    before = {
        "latest_run": file_freshness(LATEST_RUN),
        "latest_run_admin_enriched": file_freshness(ADMIN_ENRICHED),
        "latest_run_admin_enriched_pretty": file_freshness(ADMIN_ENRICHED_PRETTY),
    }
    steps = []
    admin_cmd = find_admin_script()
    if admin_cmd:
        steps.append(run_command(admin_cmd, 'admin_enriched_refresh', 'Admin enriched refresh'))
    else:
        steps.append({
            "key": "admin_enriched_refresh",
            "label": "Admin enriched refresh",
            "command": None,
            "exists": False,
            "started_at_utc": now_utc(),
            "finished_at_utc": now_utc(),
            "status": "manual_required",
            "returncode": None,
            "stdout_tail": "",
            "stderr_tail": "",
            "note": "No known admin-enrichment builder script found. The pack will not fake latest_run_admin_enriched.json."
        })

    for step in REBUILD_STEPS:
        steps.append(run_command(step['command'], step['key'], step['label']))

    after = {
        "latest_run": file_freshness(LATEST_RUN),
        "latest_run_admin_enriched": file_freshness(ADMIN_ENRICHED),
        "latest_run_admin_enriched_pretty": file_freshness(ADMIN_ENRICHED_PRETTY),
    }

    admin_state = after['latest_run_admin_enriched']['freshness_state']
    if any(s.get('status') == 'failed' for s in steps):
        overall = 'failed'
    elif admin_state == 'CURRENT':
        overall = 'ok'
    elif any(s.get('status') == 'manual_required' for s in steps):
        overall = 'manual_required'
    else:
        overall = 'attention'

    payload = {
        "schema": "jom-admin-enriched-refresh-status-v1",
        "generated_at_utc": now_utc(),
        "overall_status": overall,
        "before": before,
        "after": after,
        "steps": steps,
        "manual_next_action": None if overall == 'ok' else "Locate or build the admin enrichment collector that refreshes latest_run_admin_enriched.json from current admin/runtime data."
    }
    STATUS_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATUS_PATH.write_text(json.dumps(payload, indent=2), encoding='utf-8')
    print(json.dumps({"overall_status": overall, "admin_enriched_state": admin_state, "output": str(STATUS_PATH)}, indent=2))

if __name__ == '__main__':
    main()
