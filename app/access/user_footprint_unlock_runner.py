import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
STATUS = ROOT / "static" / "data" / "user_footprint_unlock_status.json"


def now_utc():
    return datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')


def run(script, key, label):
    path = Path(script)
    rec = {
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
        rec['finished_at_utc'] = now_utc()
        return rec
    proc = subprocess.run([sys.executable, script], cwd=ROOT, capture_output=True, text=True)
    rec['finished_at_utc'] = now_utc()
    rec['returncode'] = proc.returncode
    rec['stdout_tail'] = (proc.stdout or '')[-4000:]
    rec['stderr_tail'] = (proc.stderr or '')[-4000:]
    rec['status'] = 'ok' if proc.returncode == 0 else 'failed'
    return rec


def read_json(path, default=None):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except Exception as exc:
        return {"_read_error": str(exc)}


def main():
    steps = []
    steps.append(run('scripts/build_user_footprint_source.py', 'user_footprint', 'Build user footprint from named access truth v2'))
    if Path('scripts/audit_source_freshness.py').exists():
        steps.append(run('scripts/audit_source_freshness.py', 'source_freshness', 'Rebuild source freshness audit'))
    if Path('scripts/source_reliability_audit.py').exists():
        steps.append(run('scripts/source_reliability_audit.py', 'source_reliability', 'Rebuild source reliability status'))

    footprint = read_json(ROOT / 'static' / 'data' / 'user_footprint.json', {}) or {}
    safe = bool(footprint.get('safe_to_show_named_access_ui'))
    generated = footprint.get('source_status') == 'generated'
    overall = 'ok' if all(step.get('status') == 'ok' for step in steps if step.get('exists')) and safe and generated else 'attention'
    payload = {
        "schema": "jom-user-footprint-unlock-status-v1",
        "generated_at_utc": now_utc(),
        "overall_status": overall,
        "source_status": footprint.get('source_status'),
        "safe_to_show_named_access_ui": safe,
        "summary": footprint.get('summary', {}),
        "steps": steps,
    }
    STATUS.parent.mkdir(parents=True, exist_ok=True)
    STATUS.write_text(json.dumps(payload, indent=2), encoding='utf-8')
    print(json.dumps({"overall_status": overall, "source_status": footprint.get('source_status'), "safe": safe, "output": str(STATUS)}, indent=2))


if __name__ == '__main__':
    main()
