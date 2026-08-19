from __future__ import annotations
import json, subprocess, sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List
ROOT=Path(__file__).resolve().parents[2]
STATUS=ROOT/'runtime/data/runtime_refresh_status.json'

def now(): return datetime.now(timezone.utc).isoformat().replace('+00:00','Z')
def tail(v,n=2000): return (v or '')[-n:]
def write(payload):
 STATUS.parent.mkdir(parents=True,exist_ok=True); tmp=STATUS.with_suffix('.json.tmp'); tmp.write_text(json.dumps(payload,indent=2,ensure_ascii=False),encoding='utf-8'); tmp.replace(STATUS)
def ev(name):
 p=ROOT/'runtime/data'/name
 if not p.exists(): return {'exists':False,'state':'MISSING'}
 try: d=json.loads(p.read_text(encoding='utf-8-sig'))
 except Exception as exc: return {'exists':True,'state':'INVALID_JSON','error':str(exc)}
 return {'exists':True,'state':'PRESENT','schema':d.get('schema'),'status':d.get('status') or d.get('overall_status'),'timestamp':d.get('generated_at_utc') or d.get('updated_at_utc')}
def run(cmd:List[str],key:str,label:str,required:bool,steps:List[Dict[str,Any]],blocked_by=None,timeout=3600):
 blockers=sorted({s.get('key') for s in steps if s.get('status')!='ok'}.intersection(blocked_by or []))
 if blockers: return {'key':key,'label':label,'command':' '.join(cmd),'required':required,'status':'blocked','started_at_utc':now(),'finished_at_utc':now(),'returncode':None,'blocked_by':blockers,'stdout_tail':'','stderr_tail':''}
 rec={'key':key,'label':label,'command':' '.join(cmd),'required':required,'status':'running','started_at_utc':now(),'finished_at_utc':None,'returncode':None,'stdout_tail':'','stderr_tail':''}
 try:
  p=subprocess.run(cmd,cwd=ROOT,capture_output=True,text=True,timeout=timeout)
  rec.update(status='ok' if p.returncode==0 else 'failed',finished_at_utc=now(),returncode=p.returncode,stdout_tail=tail(p.stdout),stderr_tail=tail(p.stderr))
 except subprocess.TimeoutExpired as exc: rec.update(status='timeout',finished_at_utc=now(),error=f'timeout_after_{timeout}_seconds',stdout_tail=tail(exc.stdout or ''),stderr_tail=tail(exc.stderr or ''))
 except BaseException as exc: rec.update(status='exception',finished_at_utc=now(),error=f'{type(exc).__name__}: {exc}')
 return rec

def main()->Dict[str,Any]:
 started=now(); steps=[]; overall='failed'
 payload={'schema':'jom-runtime-refresh-status-v2','generated_at_utc':started,'started_at_utc':started,'finished_at_utc':None,'running':True,'overall_status':'running','current_step':None,'automatic_refresh_contract':{'maximum_interval_hours':12,'fail_closed':True,'dependency_order_enforced':True},'contracts':{},'steps':steps}
 write(payload)
 definitions=[
  ([sys.executable,'-m','app.runtime.admin_enriched_chain'],'admin_enriched_chain','Refresh complete Admin authority chain',True,[]),
  ([sys.executable,'scripts/build_site_registry.py','--project-root','.'],'site_registry','Rebuild Site Registry',True,[]),
  ([sys.executable,'-m','app.builders.product_access_sources'],'product_access','Refresh Product Access',False,[]),
  ([sys.executable,'scripts/audit_source_freshness.py'],'source_freshness','Rebuild Source Freshness',False,['admin_enriched_chain'])]
 try:
  for cmd,key,label,required,blocked in definitions:
   payload['current_step']=key; payload['generated_at_utc']=now(); write(payload); print('START '+key,flush=True)
   rec=run(cmd,key,label,required,steps,blocked_by=blocked); steps.append(rec); payload['steps']=steps; payload['generated_at_utc']=now(); write(payload); print('FINISH '+key+'='+rec['status'],flush=True)
  required_steps=[s for s in steps if s.get('required')]; overall='ok' if required_steps and all(s.get('status')=='ok' for s in required_steps) else 'attention'
 except BaseException as exc:
  payload['fatal_error']=f'{type(exc).__name__}: {exc}'; overall='failed'
 finally:
  names=['admin_enriched_refresh_status.json','users_access_actionable_drilldown_v1.json','named_user_display_identity_v1.json','verified_active_jira_users_v1.json','admin_directory_users.json']
  payload.update(generated_at_utc=now(),finished_at_utc=now(),running=False,current_step=None,overall_status=overall,contracts={n:ev(n) for n in names}); write(payload)
 return payload

def run_pipeline(): return main()
if __name__=='__main__':
 result=main(); raise SystemExit(0 if result.get('overall_status')=='ok' else 2)
