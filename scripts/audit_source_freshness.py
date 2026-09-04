from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];DATA=ROOT/'runtime'/'data';OUT=DATA/'source_freshness_audit.json'
SOURCES=[('runtime_refresh_status','runtime_refresh_status.json','Canonical Runtime Refresh','EXECUTION_STATUS','execution_finish'),('admin_enriched_refresh_status','admin_enriched_refresh_status.json','Admin Enriched Refresh','CHILD_EXECUTION_STATUS','execution_finish'),('site_registry','site_registry.json','Site Registry','DERIVED_RUNTIME_AUTHORITY','contract_generation'),('admin_truth_v2','admin_truth_v2.json','Admin Truth Layer v2','DERIVED_RUNTIME_AUTHORITY','contract_generation'),('estate_product_access','estate_product_access.json','Estate Product Access','LIVE_COLLECTION','contract_generation'),('product_access_refresh_status','product_access_refresh_status.json','Product Access Refresh','EXECUTION_STATUS','status_generation'),('estate_admin_contacts','estate_admin_contacts_v1.json','Estate Admin Contacts','DERIVED_RUNTIME_AUTHORITY','contract_generation'),('estate_monitored_products','estate_monitored_product_authority_v1.json','Estate Monitored Products','DERIVED_RUNTIME_AUTHORITY','contract_generation'),('named_site_access','named_site_access_authority_v1.json','Named Site Access','DERIVED_RUNTIME_AUTHORITY','contract_generation'),('named_user_display_identity','named_user_display_identity_v1.json','Named User Display Identity','DERIVED_RUNTIME_AUTHORITY','contract_generation'),('user_footprint','user_footprint.json','User Footprint','DERIVED_RUNTIME_AUTHORITY','contract_generation'),('users_access_actionable','users_access_actionable_drilldown_v1.json','Users Access Actionable Drilldown','DERIVED_RUNTIME_AUTHORITY','contract_generation'),('verified_active_jira_users','verified_active_jira_users_v1.json','Verified Active Jira Users','LIVE_DERIVED_ACTIVITY_AUTHORITY','contract_generation'),('project_inventory','project_inventory_authority_v1.json','Project Inventory','LIVE_COLLECTION','contract_generation'),('project_governance_identity','project_governance_named_identity_authority_v1.json','Project Governance Named Identity','LIVE_DERIVED_AUTHORITY','contract_generation'),('project_lead','project_lead_authority_v1.json','Project Lead Authority','DERIVED_RUNTIME_AUTHORITY','contract_generation'),('project_owner','project_owner_authority_v1.json','Project Owner Authority','GOVERNANCE_DERIVED_AUTHORITY','contract_generation')]
def now():return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00','Z')
def read(p):
 try:return json.loads(p.read_text(encoding='utf-8-sig'))
 except Exception as e:return {'_json_error':str(e)}
def parse(v):
 if not v:return None
 s=str(v);s=s[:-1]+'+00:00' if s.endswith('Z') else s
 try:
  d=datetime.fromisoformat(s);return (d.replace(tzinfo=timezone.utc) if d.tzinfo is None else d).astimezone(timezone.utc)
 except:return None
def main():
 rows=[];issues=[];counts={}
 for key,name,label,kind,meaning in SOURCES:
  p=DATA/name;d=read(p) if p.exists() else {};running=d.get('running') is True;field='finished_at_utc' if meaning=='execution_finish' else next((x for x in ('generated_at_utc','updated_at_utc','collected_at_utc') if d.get(x)),None);value=d.get(field) if field else None;dt=parse(value);age=round((datetime.now(timezone.utc)-dt).total_seconds()/3600,2) if dt else None;decl=str(d.get('status') or d.get('overall_status') or '').lower()
  if not p.exists():state='MISSING'
  elif d.get('_json_error'):state='INVALID_JSON'
  elif running:state='IN_PROGRESS'
  elif age is None:state='UNKNOWN_TIMESTAMP'
  elif age>72:state='STALE'
  elif age>24:state='AGING'
  elif decl in {'failed','error','unavailable'}:state='FAILED_OR_UNAVAILABLE'
  elif decl in {'partial','review','attention'}:state='CURRENT_WITH_REVIEW'
  else:state='CURRENT'
  row={'key':key,'label':label,'path':str(p.relative_to(ROOT)).replace('\\','/'),'exists':p.exists(),'state':state,'freshness_state':state,'operator_label':state.replace('_',' '),'timestamp_field':field,'timestamp_value':value or '','timestamp_meaning':meaning,'parsed_timestamp_utc':dt.isoformat().replace('+00:00','Z') if dt else None,'age_hours':age,'declared_status':decl or None,'source_class':kind};rows.append(row);counts[state]=counts.get(state,0)+1
  if state!='CURRENT':issues.append({'source':label,'path':row['path'],'state':state,'declared_status':row['declared_status']})
 payload={'schema':'jom-source-freshness-audit-v3.1-runtime-finalization-aligned','generated_at_utc':now(),'coverage':{'scope':'website_authority_contracts','expected_source_count':len(SOURCES),'checked_source_count':len(rows),'complete':len(rows)==len(SOURCES)},'policy':{'current_hours':24,'aging_hours':72,'whole_platform_ok_requires_complete_coverage':True,'partial_review_is_not_healthy':True,'in_progress_is_not_unknown':True,'file_mtime_is_not_collection_time':True},'sources':rows,'summary':{'source_count':len(rows),'counts':counts,'issue_count':len(issues),'overall_state':'OK' if not issues else 'ATTENTION'},'issues':issues}
 t=OUT.with_suffix('.json.tmp');t.write_text(json.dumps(payload,indent=2),encoding='utf-8');t.replace(OUT);print(json.dumps(payload['summary'],indent=2));return 0
if __name__=='__main__':raise SystemExit(main())
