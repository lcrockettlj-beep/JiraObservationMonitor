import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
STATUS = ROOT / "static" / "data" / "product_access_refresh_status.json"

def now(): return datetime.now(timezone.utc).isoformat().replace('+00:00','Z')

def run(cmd, key, label):
    exists = Path(cmd[1]).exists() if len(cmd) > 1 else True
    rec = {"key": key, "label": label, "command": " ".join(cmd), "exists": exists, "started_at_utc": now(), "finished_at_utc": None, "status": "missing", "returncode": None, "stdout_tail": "", "stderr_tail": ""}
    if not exists:
        rec["finished_at_utc"] = now(); return rec
    proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    rec["finished_at_utc"] = now(); rec["returncode"] = proc.returncode
    rec["stdout_tail"]=(proc.stdout or "")[-4000:]; rec["stderr_tail"]=(proc.stderr or "")[-4000:]
    rec["status"]="ok" if proc.returncode == 0 else "failed"
    return rec

def source(path):
    if not path.exists(): return {"exists": False, "timestamp": None}
    try: data=json.loads(path.read_text(encoding='utf-8'))
    except Exception: return {"exists": True, "timestamp": None, "error":"invalid json"}
    return {"exists": True, "timestamp": data.get('generated_at_utc'), "schema": data.get('schema')}

def main():
    steps=[]
    builder = Path('scripts/build_estate_product_access.py')
    if builder.exists():
        steps.append(run([sys.executable, 'scripts/build_estate_product_access.py'], 'estate_product_access', 'Refresh Estate Product Access and Estate Access Truth'))
    else:
        steps.append({"key":"estate_product_access", "label":"Refresh Estate Product Access and Estate Access Truth", "command":None, "exists":False, "started_at_utc":now(), "finished_at_utc":now(), "status":"manual_required", "returncode":None, "stdout_tail":"", "stderr_tail":"", "note":"scripts/build_estate_product_access.py was not found. Product access data was not faked."})
    if Path('scripts/build_admin_truth_layer_v2.py').exists(): steps.append(run([sys.executable,'scripts/build_admin_truth_layer_v2.py'], 'admin_truth_v2', 'Rebuild Admin Truth v2 after product access refresh'))
    if Path('scripts/audit_source_freshness.py').exists(): steps.append(run([sys.executable,'scripts/audit_source_freshness.py'], 'source_freshness', 'Rebuild source freshness audit'))
    if Path('scripts/source_reliability_audit.py').exists(): steps.append(run([sys.executable,'scripts/source_reliability_audit.py'], 'source_reliability', 'Rebuild source reliability status'))
    if any(s['status']=='failed' for s in steps): overall='failed'
    elif any(s['status'] in ('manual_required','missing') for s in steps if s['key']=='estate_product_access'): overall='manual_required'
    else: overall='ok'
    payload={"schema":"jom-product-access-refresh-status-v1", "generated_at_utc":now(), "overall_status":overall, "sources":{"estate_product_access":source(ROOT/'static/data/estate_product_access.json'), "estate_access_truth":source(ROOT/'static/data/estate_access_truth.json')}, "steps":steps}
    STATUS.parent.mkdir(parents=True, exist_ok=True)
    STATUS.write_text(json.dumps(payload, indent=2), encoding='utf-8')
    print(json.dumps({"overall_status":overall,"output":str(STATUS)}, indent=2))

if __name__=='__main__': main()
