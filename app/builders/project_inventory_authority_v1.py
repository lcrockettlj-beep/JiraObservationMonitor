from __future__ import annotations
import json, os, time, urllib.error, urllib.parse, urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
ROOT=Path(__file__).resolve().parents[2]
OUTPUT=ROOT/'runtime/data/project_inventory_authority_v1.json'
REGISTRY=ROOT/'runtime/data/site_registry.json'

def now_utc(): return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00','Z')
def read_json(path:Path,default=None):
 try: return json.loads(path.read_text(encoding='utf-8-sig')) if path.exists() else default
 except Exception: return default
def write_json(path:Path,payload:dict):
 path.parent.mkdir(parents=True,exist_ok=True); tmp=path.with_suffix(path.suffix+'.tmp'); tmp.write_text(json.dumps(payload,indent=2,ensure_ascii=False),encoding='utf-8'); tmp.replace(path)
def load_env():
 env=dict(os.environ); p=ROOT/'.env'
 if p.exists():
  for raw in p.read_text(encoding='utf-8-sig',errors='ignore').splitlines():
   line=raw.strip()
   if line and not line.startswith('#') and '=' in line:
    k,v=line.split('=',1); env[k.strip()]=v.strip().strip('"').strip("'")
 return env
def save_token_payload(path:Path,original:dict,refreshed:dict):
 merged=dict(original); merged.update(refreshed); merged['expires_at_epoch']=int(time.time())+int(refreshed.get('expires_in') or 3600); merged['updated_at_utc']=now_utc(); path.write_text(json.dumps(merged,indent=2),encoding='utf-8'); return merged
def token_payload():
 env=load_env()
 for key in ('ATLASSIAN_TOKEN','ATLASSIAN_ACCESS_TOKEN','JOM_ATLASSIAN_ACCESS_TOKEN'):
  if env.get(key): return {'access_token':env[key],'source':'environment'}
 p=ROOT/'tokens.json'; payload=read_json(p,{}) or {}; token=str(payload.get('access_token') or '')
 expires=int(payload.get('expires_at_epoch') or 0)
 if token and (not expires or expires>int(time.time())+60): return payload
 refresh=str(payload.get('refresh_token') or ''); client=env.get('ATLASSIAN_OAUTH_CLIENT_ID') or env.get('ATLASSIAN_CLIENT_ID') or payload.get('client_id'); secret=env.get('ATLASSIAN_OAUTH_CLIENT_SECRET') or env.get('ATLASSIAN_CLIENT_SECRET')
 if not (refresh and client and secret): return payload
 body=urllib.parse.urlencode({'grant_type':'refresh_token','client_id':client,'client_secret':secret,'refresh_token':refresh}).encode()
 req=urllib.request.Request(env.get('ATLASSIAN_TOKEN_URL') or 'https://auth.atlassian.com/oauth/token',data=body,headers={'Accept':'application/json','Content-Type':'application/x-www-form-urlencoded','User-Agent':'JOM-project-inventory-authority/1.0'},method='POST')
 try:
  with urllib.request.urlopen(req,timeout=45) as r: refreshed=json.loads(r.read().decode('utf-8'))
  return save_token_payload(p,payload,refreshed)
 except Exception: return payload
def monitored(row:dict)->bool:
 state=str(row.get('lifecycle') or row.get('classification') or row.get('status') or '').lower()
 return row.get('is_monitored') is True or row.get('monitored') is True or row.get('approved_monitored') is True or state in {'monitored','monitoring_enabled'}
def monitored_sites():
 reg=read_json(REGISTRY,{}) or {}; rows=[]; seen=set()
 for row in reg.get('sites',[]):
  if not isinstance(row,dict) or not monitored(row): continue
  key=str(row.get('site_key') or row.get('key') or row.get('site_name') or '').strip().lower(); cloud=str(row.get('cloud_id') or '').strip(); url=str(row.get('site_url') or row.get('url') or '').rstrip('/')
  if key and cloud and key not in seen: rows.append({'site_key':key,'site_name':row.get('site_name') or row.get('name') or key,'site_url':url,'cloud_id':cloud}); seen.add(key)
 return rows
def request_json(url,token):
 req=urllib.request.Request(url,headers={'Authorization':'Bearer '+token,'Accept':'application/json','User-Agent':'JOM-project-inventory-authority/1.0'},method='GET')
 try:
  with urllib.request.urlopen(req,timeout=60) as r: raw=r.read().decode('utf-8',errors='replace'); return int(r.status),json.loads(raw) if raw else {}
 except urllib.error.HTTPError as exc: exc.read(); return int(exc.code),{}
 except Exception: return 0,{}
def category_value(value):
 if isinstance(value,dict): return {'id':value.get('id'),'name':value.get('name'),'description':value.get('description')}
 return None
def normalise_project(site,row):
 return {'site_key':site['site_key'],'site_name':site['site_name'],'site_url':site['site_url'],'project_id':str(row.get('id') or ''),'project_key':str(row.get('key') or ''),'project_name':str(row.get('name') or ''),'project_type_key':row.get('projectTypeKey'),'style':row.get('style'),'simplified':row.get('simplified') if isinstance(row.get('simplified'),bool) else None,'is_private':row.get('isPrivate') if isinstance(row.get('isPrivate'),bool) else None,'project_category':category_value(row.get('projectCategory')),'source':'jira_cloud_rest_api_v3_project_search'}
def unavailable(reason,sites):
 return {'schema':'jom-project-inventory-authority-v1','generated_at_utc':now_utc(),'status':'unavailable','read_only':True,'authority':{'safe_to_publish_project_inventory':False,'reason':reason,'fabricated_projects':False},'capabilities':capabilities(False),'summary':{'monitored_site_count':len(sites),'successful_site_count':0,'failed_site_count':len(sites),'visible_project_count':None},'sites':[],'projects':[]}
def capabilities(inventory):
 reason='Not proven by the current Project Inventory Authority v1 collector.'
 return {'project_inventory':{'available':inventory,'authority':'Jira Cloud REST API v3 project search' if inventory else None},'project_leads':{'available':False,'reason':reason},'project_owners':{'available':False,'reason':'Project owner semantics are not proven and are not inferred from project lead.'},'archived_projects':{'available':False,'reason':reason},'inactive_projects':{'available':False,'reason':'No validated project activity contract exists.'},'project_permissions':{'available':False,'reason':'Permission scheme and role completeness are not proven.'},'project_governance':{'available':False,'reason':'Governance requires separately proven ownership, lifecycle, activity and permissions authorities.'}}
def collect():
 sites=monitored_sites(); token=str(token_payload().get('access_token') or '')
 if not sites: return unavailable('No monitored sites with cloud identity are available in runtime Site Registry.',sites)
 if not token: return unavailable('No Atlassian OAuth access token is available.',sites)
 all_projects=[]; site_results=[]
 for site in sites:
  start=0; pages=0; rows=[]; statuses=[]; complete=False
  while pages<200:
   pages+=1; query=urllib.parse.urlencode({'startAt':start,'maxResults':50,'orderBy':'key'})
   url=f"https://api.atlassian.com/ex/jira/{site['cloud_id']}/rest/api/3/project/search?{query}"
   status,payload=request_json(url,token); statuses.append(status)
   if status!=200 or not isinstance(payload,dict): break
   values=payload.get('values') if isinstance(payload.get('values'),list) else []
   rows.extend(normalise_project(site,row) for row in values if isinstance(row,dict))
   total=payload.get('total'); is_last=payload.get('isLast') is True
   if is_last or not values or (isinstance(total,int) and start+len(values)>=total): complete=True; break
   start+=len(values)
  all_projects.extend(rows)
  site_results.append({'site_key':site['site_key'],'site_name':site['site_name'],'site_url':site['site_url'],'status':'ok' if complete and statuses and all(x==200 for x in statuses) else 'failed','http_statuses':statuses,'pagination_complete':complete,'page_count':pages,'visible_project_count':len(rows) if complete else None,'projects_collected':len(rows),'raw_responses_stored':False})
 successful=[x for x in site_results if x['status']=='ok']; safe=len(successful)==len(sites) and bool(sites)
 return {'schema':'jom-project-inventory-authority-v1','generated_at_utc':now_utc(),'status':'ok' if safe else 'review','read_only':True,'scope':{'definition':'Visible Jira projects across current monitored Site Registry sites.','site_scope':'runtime/data/site_registry.json monitored sites only','endpoint':'Jira Cloud REST API v3 project search','historical_expected_count_used':False},'authority':{'safe_to_publish_project_inventory':safe,'fabricated_projects':False,'inferred_fields':False,'pagination_complete_all_sites':safe,'reason':'All monitored sites returned complete paginated project-search results.' if safe else 'One or more monitored sites did not return a complete project-search result.'},'privacy':{'authorization_headers_stored':False,'tokens_stored':False,'raw_responses_stored':False,'project_lead_identity_stored':False,'cloud_ids_in_project_rows':False},'capabilities':capabilities(safe),'summary':{'monitored_site_count':len(sites),'successful_site_count':len(successful),'failed_site_count':len(sites)-len(successful),'visible_project_count':len(all_projects) if safe else None,'collected_project_rows':len(all_projects),'duplicate_site_project_key_count':len(all_projects)-len({(x['site_key'],x['project_key']) for x in all_projects})},'sites':site_results,'projects':sorted(all_projects,key=lambda x:(x['site_key'],x['project_key'])),'notes':['Visible project count is operational visibility, not proof of every historical or inaccessible project.','Project lead, owner, archive, activity, permissions and governance remain unavailable until separately proven.']}
def main():
 payload=collect(); write_json(OUTPUT,payload); print(json.dumps({'status':payload['status'],'summary':payload['summary'],'output':str(OUTPUT)},indent=2)); return 0 if payload['status']=='ok' else 2
if __name__=='__main__': raise SystemExit(main())
