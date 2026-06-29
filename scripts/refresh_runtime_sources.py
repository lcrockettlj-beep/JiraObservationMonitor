import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
STATUS_PATH = PROJECT_ROOT / "static" / "data" / "runtime_refresh_status.json"
LATEST_RUN_PATH = PROJECT_ROOT / "latest_run.json"
LATEST_ADMIN_ENRICHED_PATH = PROJECT_ROOT / "latest_run_admin_enriched.json"
FRESHNESS_PATH = PROJECT_ROOT / "static" / "data" / "source_freshness_audit.json"

CURRENT_HOURS = 24

STEPS = [
    {"key": "site_registry", "label": "Site Registry rebuild", "command": [sys.executable, "scripts/build_site_registry.py", "--project-root", "."], "required": True},
    {"key": "source_freshness", "label": "Source Freshness rebuild", "command": [sys.executable, "scripts/audit_source_freshness.py"], "required": False},
]

OPTIONAL_COLLECTOR_CANDIDATES = [
    [sys.executable, "data_collector.py"],
    [sys.executable, "scripts/data_collector.py"],
    [sys.executable, "collectors/data_collector.py"],
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


def latest_run_freshness(path):
    payload = read_json(path)
    if not payload:
        return {"exists": path.exists(), "freshness_state": "MISSING" if not path.exists() else "UNKNOWN_TIMESTAMP", "age_hours": None, "timestamp": None}
    timestamp = nested(payload, 'raw_collection_summary.collected_at_utc') or payload.get('generated_at_utc') or payload.get('run_timestamp_local')
    parsed = parse_time(timestamp)
    if not parsed:
        return {"exists": True, "freshness_state": "UNKNOWN_TIMESTAMP", "age_hours": None, "timestamp": timestamp}
    age = round((now_dt() - parsed).total_seconds() / 3600, 2)
    if age <= CURRENT_HOURS:
        state = 'CURRENT'
    elif age <= 72:
        state = 'AGING'
    else:
        state = 'STALE'
    return {"exists": True, "freshness_state": state, "age_hours": age, "timestamp": parsed.isoformat().replace('+00:00','Z')}


def run_step(step):
    cmd = step["command"]
    exists = Path(cmd[1]).exists() if len(cmd) > 1 else False
    record = {
        "key": step["key"], "label": step["label"], "command": " ".join(cmd), "exists": exists,
        "started_at_utc": now_utc(), "finished_at_utc": None, "status": "skipped",
        "returncode": None, "stdout_tail": "", "stderr_tail": "",
    }
    if not exists:
        record["status"] = "missing"; record["finished_at_utc"] = now_utc(); return record
    proc = subprocess.run(cmd, cwd=PROJECT_ROOT, capture_output=True, text=True)
    record["finished_at_utc"] = now_utc(); record["returncode"] = proc.returncode
    record["stdout_tail"] = (proc.stdout or "")[-4000:]; record["stderr_tail"] = (proc.stderr or "")[-4000:]
    record["status"] = "ok" if proc.returncode == 0 else "failed"
    return record


def find_collector():
    for cmd in OPTIONAL_COLLECTOR_CANDIDATES:
        if Path(cmd[1]).exists():
            return cmd
    return None


def collector_state_from_latest_run():
    runtime = latest_run_freshness(LATEST_RUN_PATH)
    admin = latest_run_freshness(LATEST_ADMIN_ENRICHED_PATH)
    state = 'review'
    note = 'Runtime collector was not requested. Status inferred from latest_run.json freshness.'
    if runtime.get('freshness_state') == 'CURRENT':
        state = 'ok'
        note = 'Runtime collector not requested, but latest_run.json is CURRENT; treating runtime source as refreshed.'
    elif runtime.get('freshness_state') == 'STALE':
        state = 'stale'
        note = 'Runtime collector not requested and latest_run.json is stale.'
    elif runtime.get('freshness_state') in ('MISSING', 'UNKNOWN_TIMESTAMP'):
        state = 'review'
        note = 'Runtime collector not requested and latest_run.json freshness cannot be proven.'
    return state, note, runtime, admin


def main(run_collector=False):
    results = [run_step(step) for step in STEPS]
    collector_cmd = find_collector()
    collector_record = {
        "key": "runtime_collector", "label": "Runtime collector", "command": " ".join(collector_cmd) if collector_cmd else None,
        "exists": bool(collector_cmd), "run_requested": bool(run_collector), "status": "not_requested",
        "started_at_utc": None, "finished_at_utc": None, "returncode": None, "stdout_tail": "", "stderr_tail": "", "note": ""
    }
    if run_collector and collector_cmd:
        collector_record.update(run_step({"key": "runtime_collector", "label": "Runtime collector", "command": collector_cmd, "required": False}))
    elif run_collector and not collector_cmd:
        collector_record["status"] = "missing"; collector_record["finished_at_utc"] = now_utc(); collector_record["note"] = "Collector requested but no collector script was found."
    else:
        inferred_state, note, runtime_freshness, admin_freshness = collector_state_from_latest_run()
        collector_record["status"] = inferred_state
        collector_record["note"] = note
        collector_record["latest_run_freshness"] = runtime_freshness
        collector_record["latest_admin_enriched_freshness"] = admin_freshness
        collector_record["finished_at_utc"] = now_utc()

    results.append(collector_record)

    if any(r.get('status') == 'failed' for r in results):
        overall = 'failed'
    elif collector_record.get('status') == 'ok' and all(r.get('status') in ('ok', 'skipped') for r in results if r.get('key') != 'runtime_collector'):
        overall = 'ok'
    elif collector_record.get('status') == 'stale':
        overall = 'attention'
    else:
        overall = 'review'

    payload = {"schema":"jom-runtime-refresh-status-v1.1", "generated_at_utc":now_utc(), "overall_status":overall, "run_collector_requested":bool(run_collector), "steps":results}
    STATUS_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATUS_PATH.write_text(json.dumps(payload, indent=2), encoding='utf-8')
    print(json.dumps({"overall_status": overall, "runtime_collector_status": collector_record.get('status'), "output": str(STATUS_PATH)}, indent=2))

if __name__ == '__main__':
    main(run_collector='--run-collector' in sys.argv)
