from pathlib import Path
from datetime import datetime, timezone
import json
ROOT=Path(__file__).resolve().parents[2]; OUT=ROOT/'runtime/data/source_reliability_status.json'
STATUS_INPUTS={
'runtime_refresh':ROOT/'runtime/data/runtime_refresh_status.json',
'admin_enriched_refresh':ROOT/'runtime/data/admin_enriched_refresh_status.json',
'product_access_refresh':ROOT/'runtime/data/product_access_refresh_status.json',
'estate_resource_authority_refresh':ROOT/'runtime/data/estate_resource_authority_refresh_status_v1.json',
'admin_group_expansion':ROOT/'runtime/data/admin_group_expansion_status.json',
'backend_final_truth_chain':ROOT/'runtime/data/backend_final_truth_chain_status.json',
'group_expansion_recovery':ROOT/'runtime/data/group_expansion_recovery_status.json',
}
def now():return datetime.now(timezone.utc).isoformat().replace('+00:00','Z')
def read(p):
 try:return json.loads(p.read_text(encoding='utf-8-sig'))
 except Exception:return None
def state(d):
 if not isinstance(d,dict):return 'MISSING'
 return str(d.get('overall_status') or d.get('status') or 'UNAVAILABLE').upper()
def main():
 freshness=read(ROOT/'runtime/data/source_freshness_audit.json') or {}; issues=[]
 inv=freshness.get('inventory') or {}; summary=freshness.get('summary') or {}
 if inv.get('coverage_complete') is not True:issues.append({'source':'Source Health Inventory','state':'INCOMPLETE','reason':'Expected primary authority coverage is not complete.'})
 for row in freshness.get('sources') or []:
  if row.get('freshness_state')!='CURRENT':issues.append({'source':row.get('label'),'state':row.get('freshness_state'),'path':row.get('path'),'reason':'Expected authority is not current.'})
  if row.get('declared_state') in {'PARTIAL','REVIEW','UNAVAILABLE','ERROR','FAILED','CRITICAL'}:issues.append({'source':row.get('label'),'state':row.get('declared_state'),'path':row.get('path'),'reason':'Authority contract publishes a non-healthy state.'})
 status_rows=[]
 for key,path in STATUS_INPUTS.items():
  payload=read(path); st=state(payload); status_rows.append({'key':key,'path':str(path.relative_to(ROOT)).replace('\\','/'),'exists':path.exists(),'state':st})
  if not path.exists() or st in {'MISSING','UNAVAILABLE','FAILED','ERROR','CRITICAL','TIMEOUT','EXCEPTION','BLOCKED'}:issues.append({'source':key,'state':st,'path':str(path.relative_to(ROOT)).replace('\\','/'),'reason':'Reliability status input is not healthy.'})
 overall='ok' if inv.get('coverage_complete') is True and summary.get('overall_state')=='OK' and not issues else 'attention'
 payload={'schema':'jom-source-reliability-status-v2-canonical-inventory','generated_at_utc':now(),'overall_status':overall,'summary':{'issue_count':len(issues),'freshness_overall':summary.get('overall_state'),'expected_source_coverage_complete':inv.get('coverage_complete') is True,'status_input_count':len(status_rows)},'issues':issues,'status_inputs':status_rows,'inputs':{'source_freshness':'runtime/data/source_freshness_audit.json',**{k:str(v.relative_to(ROOT)).replace('\\','/') for k,v in STATUS_INPUTS.items()}}}
 tmp=OUT.with_suffix('.json.tmp');tmp.write_text(json.dumps(payload,indent=2),encoding='utf-8');tmp.replace(OUT);print(json.dumps({'overall_status':overall,'issues':len(issues),'output':str(OUT)},indent=2));return payload
if __name__=='__main__':main()
