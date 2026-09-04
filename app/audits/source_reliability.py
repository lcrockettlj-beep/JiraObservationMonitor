from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'runtime/data/source_reliability_status.json';INPUTS={'source_freshness':ROOT/'runtime/data/source_freshness_audit.json','runtime_refresh':ROOT/'runtime/data/runtime_refresh_status.json','user_footprint':ROOT/'runtime/data/user_footprint.json','site_registry':ROOT/'runtime/data/site_registry.json'}
def now():return datetime.now(timezone.utc).isoformat().replace('+00:00','Z')
def read(p):
 try:return json.loads(p.read_text(encoding='utf-8-sig')) if p.exists() else None
 except Exception as e:return {'_read_error':str(e)}
def main():
 data={k:read(v) for k,v in INPUTS.items()};f=data.get('source_freshness') or {};r=data.get('runtime_refresh') or {};fp=data.get('user_footprint') or {};issues=[]
 for src in f.get('sources',[]):
  state=src.get('state') or src.get('freshness_state')
  if state!='CURRENT':issues.append({'source':src.get('label'),'state':state,'path':src.get('path'),'reason':'Freshness source is not fully current.'})
 ro=r.get('overall_status');running=r.get('running') is True
 if running:issues.append({'source':'Runtime Refresh','state':'IN_PROGRESS','path':'runtime/data/runtime_refresh_status.json'})
 elif ro not in {'ok','ok_with_advisory'}:issues.append({'source':'Runtime Refresh','state':ro or 'UNAVAILABLE','path':'runtime/data/runtime_refresh_status.json'})
 if fp.get('source_status')=='unavailable':issues.append({'source':'User Footprint','state':'GUARDED_UNAVAILABLE','path':'runtime/data/user_footprint.json','reason':fp.get('reason')})
 fo=(f.get('summary') or {}).get('overall_state');overall='attention' if fo=='ATTENTION' or running or ro not in {'ok','ok_with_advisory'} else ('review' if issues else 'ok')
 payload={'schema':'jom-source-reliability-status-v1.2-runtime-finalization-aligned','generated_at_utc':now(),'overall_status':overall,'summary':{'issue_count':len(issues),'freshness_overall':fo,'runtime_refresh_overall':ro,'runtime_refresh_running':running,'user_footprint_status':fp.get('source_status')},'issues':issues,'inputs':{k:str(v.relative_to(ROOT)).replace('\\','/') for k,v in INPUTS.items()}}
 t=OUT.with_suffix('.json.tmp');t.write_text(json.dumps(payload,indent=2),encoding='utf-8');t.replace(OUT);print(json.dumps(payload['summary'],indent=2));return 0
if __name__=='__main__':raise SystemExit(main())
