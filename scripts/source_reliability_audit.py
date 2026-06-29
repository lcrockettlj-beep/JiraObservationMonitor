import json
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUT_PATH = PROJECT_ROOT / "static" / "data" / "source_reliability_status.json"
INPUTS = {
    "source_freshness": PROJECT_ROOT / "static" / "data" / "source_freshness_audit.json",
    "runtime_refresh": PROJECT_ROOT / "static" / "data" / "runtime_refresh_status.json",
    "user_footprint": PROJECT_ROOT / "static" / "data" / "user_footprint.json",
    "site_registry": PROJECT_ROOT / "static" / "data" / "site_registry.json",
}

def now_utc():
    return datetime.now(timezone.utc).isoformat().replace('+00:00','Z')

def read_json(path):
    if not path.exists(): return None
    try: return json.loads(path.read_text(encoding='utf-8'))
    except Exception as exc: return {"_read_error": str(exc)}

def main():
    data = {k: read_json(v) for k, v in INPUTS.items()}
    issues = []
    freshness = data.get('source_freshness') or {}
    runtime = data.get('runtime_refresh') or {}
    footprint = data.get('user_footprint') or {}
    runtime_overall = runtime.get('overall_status')

    # Runtime collector status is now authoritative for latest_run.json, so avoid duplicate Latest Jira Runtime issue.
    for src in freshness.get('sources', []):
        label = src.get('label')
        state = src.get('freshness_state')
        if label == 'Latest Jira Runtime Run' and runtime_overall == 'ok':
            continue
        if state in ('STALE', 'MISSING', 'UNKNOWN_TIMESTAMP'):
            issues.append({"source": label, "state": src.get('operator_label') or state, "path": src.get('path')})

    if footprint.get('source_status') == 'unavailable':
        issues.append({"source":"User Footprint", "state":"GUARDED UNAVAILABLE", "path":"static/data/user_footprint.json", "reason":footprint.get('reason')})

    if runtime_overall in ('failed', 'attention', 'review'):
        # review is only an issue if latest_run was not current or collector script missing.
        steps = runtime.get('steps') or []
        collector = next((s for s in steps if s.get('key') == 'runtime_collector'), {})
        if runtime_overall != 'review' or collector.get('status') != 'ok':
            issues.append({"source":"Runtime Refresh", "state":runtime_overall, "path":"static/data/runtime_refresh_status.json", "reason":collector.get('note')})

    hard_states = {'STALE SNAPSHOT', 'MISSING SOURCE', 'UNAVAILABLE', 'failed', 'attention'}
    if any(i.get('state') in hard_states for i in issues): overall = 'attention'
    elif issues: overall = 'review'
    else: overall = 'ok'

    payload = {"schema":"jom-source-reliability-status-v1.1", "generated_at_utc":now_utc(), "overall_status":overall,
        "summary":{"issue_count":len(issues), "freshness_overall":(freshness.get('summary') or {}).get('overall_state'), "runtime_refresh_overall":runtime_overall, "user_footprint_status":footprint.get('source_status')},
        "issues":issues, "inputs":{k:str(v.relative_to(PROJECT_ROOT)) for k,v in INPUTS.items()}}
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(payload, indent=2), encoding='utf-8')
    print(json.dumps(payload['summary'], indent=2)); print('Output:', OUT_PATH)
if __name__ == '__main__': main()
