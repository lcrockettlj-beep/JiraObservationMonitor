import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATUS = ROOT / "static" / "data" / "group_expansion_recovery_status.json"

def now_utc():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

def run(cmd, key, label):
    exists = Path(cmd[1]).exists() if len(cmd) > 1 else True
    rec = {"key":key,"label":label,"command":" ".join(cmd),"exists":exists,"started_at_utc":now_utc(),"finished_at_utc":None,"status":"missing","returncode":None,"stdout_tail":"","stderr_tail":""}
    if not exists:
        rec["finished_at_utc"] = now_utc(); return rec
    proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    rec["finished_at_utc"] = now_utc(); rec["returncode"] = proc.returncode; rec["stdout_tail"]=(proc.stdout or "")[-4000:]; rec["stderr_tail"]=(proc.stderr or "")[-4000:]
    rec["status"] = "ok" if proc.returncode == 0 else "failed"
    return rec

def read_json(path, default=None):
    if not path.exists(): return default
    try: return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc: return {"_read_error": str(exc)}

def main():
    steps=[]
    steps.append(run([sys.executable,"scripts/collect_admin_group_expansion.py"],"group_expansion_collector","Collect group-derived product access with ARI mapping"))
    for script,key,label in [("scripts/build_named_access_truth_v2.py","named_access_truth_v2","Rebuild Named Access Truth v2"),("scripts/reconcile_named_access_truth_v2.py","named_access_reconciliation_v2","Reconcile Named Access Truth v2"),("scripts/build_user_footprint_source.py","user_footprint_guard","Rebuild guarded user footprint"),("scripts/audit_source_freshness.py","source_freshness","Rebuild source freshness"),("scripts/source_reliability_audit.py","source_reliability","Rebuild source reliability")]:
        if Path(script).exists(): steps.append(run([sys.executable,script],key,label))
    expansion=read_json(ROOT/"static"/"data"/"admin_group_expansion.json",{}) or {}
    reconciliation=read_json(ROOT/"reports"/"named_access_reconciliation_v2.json",{}) or {}
    safe=bool(reconciliation.get("safe_to_enable_named_access_ui")); expansion_safe=bool(expansion.get("safe_to_use_for_named_access"))
    overall="ok" if all(step.get("status")=="ok" for step in steps if step.get("exists")) else "attention"
    payload={"schema":"jom-group-expansion-recovery-status-v1.2","generated_at_utc":now_utc(),"overall_status":overall,"group_expansion_safe":expansion_safe,"safe_to_enable_named_access_ui":safe,"group_summary":expansion.get("summary",{}),"reconciliation_summary":reconciliation.get("summary",{}),"reconciliation_blockers":reconciliation.get("blockers",[]),"steps":steps}
    STATUS.parent.mkdir(parents=True, exist_ok=True); STATUS.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps({"overall_status":overall,"group_expansion_safe":expansion_safe,"safe_to_enable_named_access_ui":safe,"output":str(STATUS)}, indent=2))
if __name__=="__main__": main()
