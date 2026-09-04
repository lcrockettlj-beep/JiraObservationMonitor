from __future__ import annotations
import json, os, subprocess, sys, uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List
ROOT=Path(__file__).resolve().parents[2]; STATUS=ROOT/'runtime/data/runtime_refresh_status.json'
CONTRACT_NAMES=['site_registry.json','estate_product_access.json','product_access_refresh_status.json','admin_enriched_refresh_status.json','estate_monitored_product_authority_v1.json','users_access_actionable_drilldown_v1.json','named_user_display_identity_v1.json','verified_active_jira_users_v1.json','admin_directory_users.json','admin_truth_v2.json','estate_admin_contacts_v1.json','named_site_access_authority_v1.json','user_footprint.json','project_inventory_authority_v1.json','project_governance_named_identity_authority_v1.json','project_lead_authority_v1.json','project_owner_authority_v1.json','source_freshness_audit.json','source_reliability_status.json']
def now(): return datetime.now(timezone.utc).isoformat().replace('+00:00','Z')
def tail(v,n=2000): return (v or '')[-n:]
def write(p):
 STATUS.parent.mkdir(parents=True,exist_ok=True); t=STATUS.with_suffix('.json.tmp'); t.write_text(json.dumps(p,indent=2,ensure_ascii=False),encoding='utf-8'); t.replace(STATUS)
def ev(name):
 p=ROOT/'runtime/data'/name
 if not p.exists():return {'exists':False,'state':'MISSING'}
 try:d=json.loads(p.read_text(encoding='utf-8-sig'))
 except Exception as e:return {'exists':True,'state':'INVALID_JSON','error':str(e)}
 return {'exists':True,'state':'PRESENT','schema':d.get('schema'),'status':d.get('status') or d.get('overall_status'),'contract_generated_at_utc':d.get('generated_at_utc') or d.get('updated_at_utc'),'file_last_write_utc':datetime.fromtimestamp(p.stat().st_mtime,timezone.utc).isoformat().replace('+00:00','Z')}
def run(cmd,key,label,required,steps,eid,blocked_by=None,timeout=3600):
 done={s.get('key'):s for s in steps}; blockers=[k for k in (blocked_by or []) if k not in done or done[k].get('status') not in {'ok','advisory','ok_with_advisory'}]
 if blockers:return {'key':key,'label':label,'command':' '.join(cmd),'required':required,'scope':'canonical_runtime_refresh_step','parent_execution_id':eid,'status':'blocked','started_at_utc':now(),'finished_at_utc':now(),'returncode':None,'blocked_by':blockers,'stdout_tail':'','stderr_tail':''}
 rec={'key':key,'label':label,'command':' '.join(cmd),'required':required,'scope':'canonical_runtime_refresh_step','parent_execution_id':eid,'status':'running','started_at_utc':now(),'finished_at_utc':None,'returncode':None,'stdout_tail':'','stderr_tail':''}; env=dict(os.environ); env['JOM_REFRESH_EXECUTION_ID']=eid; env['JOM_REFRESH_SCOPE']='canonical_runtime_refresh'
 try:
  p=subprocess.run(cmd,cwd=ROOT,capture_output=True,text=True,timeout=timeout,env=env);rec.update(status='ok' if p.returncode==0 else 'failed',finished_at_utc=now(),returncode=p.returncode,stdout_tail=tail(p.stdout),stderr_tail=tail(p.stderr))
 except subprocess.TimeoutExpired as e:rec.update(status='timeout',finished_at_utc=now(),error=f'timeout_after_{timeout}_seconds')
 except BaseException as e:rec.update(status='exception',finished_at_utc=now(),error=f'{type(e).__name__}: {e}')
 return rec
def main()->Dict[str,Any]:
 eid='jom-refresh-'+uuid.uuid4().hex;started=now();steps=[];payload={'schema':'jom-runtime-refresh-status-v3.1','execution_id':eid,'execution_scope':'canonical_runtime_refresh','parent_execution_id':None,'generated_at_utc':started,'started_at_utc':started,'finished_at_utc':None,'running':True,'overall_status':'running','current_step':None,'automatic_refresh_contract':{'maximum_interval_hours':12,'fail_closed':True,'dependency_order_enforced':True,'normal_operation_trigger':'external_scheduler_or_explicit_runtime_refresh_route','trigger_proof':'REQUIRES_RUNTIME_OR_SCHEDULER_EVIDENCE'},'timestamp_semantics':{'started_at_utc':'canonical execution start','finished_at_utc':'canonical execution finish before final health assessment','generated_at_utc':'status document write time','contracts.contract_generated_at_utc':'producer generation time; not automatically source collection time','contracts.file_last_write_utc':'filesystem write evidence only'},'final_health_assessment':{'status':'pending','freshness':None,'reliability':None},'contracts':{},'steps':steps};write(payload)
 defs=[([sys.executable,'scripts/build_site_registry.py','--project-root','.'],'site_registry','Rebuild Site Registry',True,[]),([sys.executable,'-m','app.builders.product_access_sources'],'product_access','Refresh Product Access',True,['site_registry']),([sys.executable,'-m','app.runtime.admin_enriched_chain'],'admin_enriched_chain','Refresh complete Admin authority chain',True,['site_registry','product_access'])]
 for cmd,key,label,req,blocked in defs:
  payload['current_step']=key;payload['generated_at_utc']=now();write(payload);print('START '+key,flush=True);r=run(cmd,key,label,req,steps,eid,blocked);steps.append(r);payload['steps']=steps;write(payload);print('FINISH '+key+'='+r['status'],flush=True)
 required=[x for x in steps if x.get('required')];base_status='ok' if required and all(x.get('status')=='ok' for x in required) else 'attention'
 # Finalize canonical execution before health processes read it.
 finished=now();payload.update(generated_at_utc=finished,finished_at_utc=finished,running=False,current_step=None,overall_status=base_status,contracts={n:ev(n) for n in CONTRACT_NAMES});write(payload)
 health=[]
 if base_status=='ok':
  for cmd,key,label in [([sys.executable,'scripts/audit_source_freshness.py'],'source_freshness_final','Evaluate Freshness against finalized canonical execution'),([sys.executable,'-m','app.audits.source_reliability'],'source_reliability_final','Evaluate Reliability from finalized Freshness and Runtime')]:
   print('START '+key,flush=True);r=run(cmd,key,label,True,health,eid,[],600);health.append(r);print('FINISH '+key+'='+r['status'],flush=True)
 payload['final_health_assessment']={'status':'complete' if health and all(x.get('status')=='ok' for x in health) else 'attention','freshness':next((x for x in health if x['key']=='source_freshness_final'),None),'reliability':next((x for x in health if x['key']=='source_reliability_final'),None)}
 payload['contracts']={n:ev(n) for n in CONTRACT_NAMES};payload['generated_at_utc']=now();write(payload)
 return payload
def run_pipeline():return main()
if __name__=='__main__':
 r=main();raise SystemExit(0 if r.get('overall_status')=='ok' and r.get('final_health_assessment',{}).get('status')=='complete' else 2)
