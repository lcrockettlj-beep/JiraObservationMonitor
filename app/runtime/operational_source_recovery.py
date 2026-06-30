import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
STATUS = ROOT / "static" / "data" / "operational_source_recovery_status.json"

def now(): return datetime.now(timezone.utc).isoformat().replace('+00:00','Z')

def run(script, key, label):
    path = Path(script)
    rec = {"key":key,"label":label,"script":script,"exists":path.exists(),"started_at_utc":now(),"finished_at_utc":None,"status":"missing","returncode":None,"stdout_tail":"","stderr_tail":""}
    if not path.exists(): rec["finished_at_utc"]=now(); return rec
    proc=subprocess.run([sys.executable, script], cwd=ROOT, capture_output=True, text=True)
    rec["finished_at_utc"]=now(); rec["returncode"]=proc.returncode; rec["stdout_tail"]=(proc.stdout or '')[-4000:]; rec["stderr_tail"]=(proc.stderr or '')[-4000:]
    rec["status"]='ok' if proc.returncode==0 else 'failed'
    return rec

def main():
    steps=[]
    steps.append(run('scripts/refresh_admin_enriched_chain.py','admin_enriched_refresh','Refresh admin-enriched runtime + admin truth'))
    steps.append(run('scripts/refresh_product_access_sources.py','product_access_refresh','Refresh estate product/access truth'))
    steps.append(run('scripts/build_named_access_recovery_plan.py','named_access_recovery_plan','Build named access recovery plan'))
    if Path('scripts/audit_source_freshness.py').exists(): steps.append(run('scripts/audit_source_freshness.py','source_freshness','Rebuild source freshness audit'))
    if Path('scripts/build_user_footprint_source.py').exists(): steps.append(run('scripts/build_user_footprint_source.py','user_footprint_guard','Rebuild guarded user footprint source'))
    if Path('scripts/source_reliability_audit.py').exists(): steps.append(run('scripts/source_reliability_audit.py','source_reliability','Rebuild source reliability status'))
    overall = 'ok' if all(s['status']=='ok' for s in steps if s['exists']) else 'attention'
    payload={"schema":"jom-operational-source-recovery-status-v1","generated_at_utc":now(),"overall_status":overall,"steps":steps}
    STATUS.parent.mkdir(parents=True, exist_ok=True); STATUS.write_text(json.dumps(payload, indent=2), encoding='utf-8')
    print(json.dumps({"overall_status":overall,"output":str(STATUS)}, indent=2))

if __name__=='__main__': main()
